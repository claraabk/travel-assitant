"""
Scraper da simulação de compra de milhas LATAM Pass.

A página https://latampass.com/facilidades/compra-milhas/lp?pt=pp é uma
Single Page Application (SPA) que renderiza os cartões de preço via
JavaScript. Por isso, uma requisição HTTP simples (requests/httpx) não
funciona -- precisamos de um navegador de verdade rodando em modo headless.

ESTRUTURA REAL DA PÁGINA (confirmada por inspeção do HTML renderizado):
- NÃO fica em iframe -- é direto na página principal.
- Os tiers de quantidade são <label> com id no formato
  `cdp_{quantidade}_pontos_cotacao` (ex: cdp_1000_pontos_cotacao),
  cada um contendo um <input type="radio" name="radio-values"> escondido
  visualmente (mas clicável via label).
- Existe TAMBÉM um radiogroup de perfil de comprador (Clube + Cartão,
  Cliente Clube, Cartão LATAM Pass Itaú, Cliente LATAM Pass) com
  name="radio-values-profile" e o MESMO sufixo de id -- por isso
  filtramos pelo atributo `name` do input, não só pelo id.
- O preço não fica colado no botão: aparece numa caixa de resumo
  separada, num <p> cujo texto é exatamente "Total", seguido por um
  <p> irmão com o valor (ex: "R$ 70,00").
- O perfil padrão já vem selecionado como "Cliente LATAM Pass" (o mais
  adequado para o perfil sem Clube nem cartão Itaú Insira aqui).
"""

import asyncio
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime

from playwright.async_api import async_playwright

LATAM_MILES_URL = "https://latampass.com/facilidades/compra-milhas/lp?pt=pp"

SELECTOR_COOKIE_BANNER_ACCEPT = "button.cookie-accept-all-btn"


@dataclass
class MilesTierQuote:
    miles: int
    price_brl: float | None
    price_per_thousand_brl: float | None
    raw_price_text: str | None


def _parse_brl(text: str) -> float | None:
    """Converte 'R$ 1.234,56' -> 1234.56"""
    if not text:
        return None
    cleaned = re.sub(r"[^\d,\.]", "", text)
    cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


async def fetch_all_miles_tiers(headless: bool = True) -> list[MilesTierQuote]:
    """
    Abre a página de compra de milhas, itera por cada tier de quantidade
    (clicando no label correspondente) e lê o preço total exibido na
    caixa de resumo depois de cada seleção.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        page = None
        try:
            page = await browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            )
            await page.goto(LATAM_MILES_URL, wait_until="domcontentloaded", timeout=30000)

            try:
                await page.click(SELECTOR_COOKIE_BANNER_ACCEPT, timeout=3000)
            except Exception:
                pass  # banner pode não existir -- tudo bem

            # Espera o radiogroup de QUANTIDADE (não o de perfil) aparecer.
            await page.wait_for_selector('input[name="radio-values"]', timeout=20000)

            # Coleta os tiers de quantidade, distinguindo do radiogroup de
            # perfil pelo atributo name do input associado.
            tier_data = await page.evaluate(
                """
                () => {
                  const inputs = Array.from(
                    document.querySelectorAll('input[name="radio-values"]')
                  );
                  return inputs
                    .map((input) => {
                      const label = input.closest('label');
                      return { id: label ? label.id : null, value: input.value };
                    })
                    .filter((t) => t.id);
                }
                """
            )

            if not tier_data:
                raise RuntimeError(
                    "Nenhum input com name='radio-values' foi encontrado -- "
                    "a estrutura da página pode ter mudado. Veja debug_page.html."
                )

            results: list[MilesTierQuote] = []
            for tier in tier_data:
                try:
                    miles = int(tier["value"])
                except (TypeError, ValueError):
                    continue
                label_id = tier["id"]

                # Clica no label (o input em si é visualmente escondido,
                # mas o clique no label ativa o input normalmente).
                await page.locator(f'[id="{label_id}"]').click()
                await page.wait_for_timeout(800)

                raw_price_text = await page.evaluate(
                    """
                    () => {
                      const totalP = Array.from(document.querySelectorAll('p'))
                        .find((p) => p.textContent.trim() === 'Total');
                      if (!totalP) return null;
                      const sibling = totalP.nextElementSibling;
                      return sibling ? sibling.textContent.trim() : null;
                    }
                    """
                )

                price = _parse_brl(raw_price_text or "")
                per_thousand = (
                    round(price / (miles / 1000), 2) if price and miles else None
                )
                results.append(
                    MilesTierQuote(
                        miles=miles,
                        price_brl=price,
                        price_per_thousand_brl=per_thousand,
                        raw_price_text=raw_price_text,
                    )
                )

            results.sort(key=lambda r: r.miles)
            return results
        except Exception:
            if page is not None:
                try:
                    await page.screenshot(path="debug_screenshot.png", full_page=True)
                    html = await page.content()
                    with open("debug_page.html", "w", encoding="utf-8") as f:
                        f.write(html)
                except Exception:
                    pass
            raise
        finally:
            await browser.close()


async def fetch_miles_price(miles_amount: int, headless: bool = True) -> MilesTierQuote:
    """
    Retorna o preço do tier que bate exatamente com miles_amount, ou o
    tier mais próximo disponível se não houver um exato.
    """
    tiers = await fetch_all_miles_tiers(headless=headless)
    if not tiers:
        raise RuntimeError("Nenhum tier de milhas foi encontrado na página.")

    exact = next((t for t in tiers if t.miles == miles_amount), None)
    if exact:
        return exact

    closest = min(tiers, key=lambda t: abs(t.miles - miles_amount))
    return closest


def _build_state_json(tiers: list[MilesTierQuote]) -> dict:
    """
    Monta o dicionário exatamente no schema de state/latam_miles_price.json
    documentado em docs/scraper-local-setup.md.
    """
    tiers_out = [
        {
            "milhas": t.miles,
            "preco_brl": t.price_brl,
            "cpm_brl": t.price_per_thousand_brl,
        }
        for t in tiers
    ]

    priced = [t for t in tiers_out if t["cpm_brl"] is not None]
    melhor_tier = min(priced, key=lambda t: t["cpm_brl"]) if priced else None

    return {
        "atualizado_em": datetime.now().astimezone().isoformat(timespec="seconds"),
        "fonte": "scraper local (cron)",
        "url_origem": LATAM_MILES_URL,
        # Sem um preço de referência "cheio" confiável para comparar, não dá
        # para calcular a % de desconto aqui -- deixar para o agente cruzar
        # com o que ele achar via busca web/página de ofertas.
        "desconto_pct_aplicado": None,
        "tiers": tiers_out,
        "melhor_tier": melhor_tier,
        "erro": None,
    }


def main() -> None:
    """
    Ponto de entrada para o cron (docs/scraper-local-setup.md): roda o
    scraper, imprime o JSON no schema esperado em stdout, e sai com
    código != 0 em caso de erro -- sem imprimir nada em stdout nesse caso,
    para o wrapper (run-latam-scraper.sh) nunca sobrescrever o arquivo
    anterior com dado inválido.

    IMPORTANTE: headless=True costuma ser detectado pelo Akamai do site
    da LATAM (fingerprint de Chromium headless), que responde com uma
    página de desafio -- daí o timeout esperando 'input[name="radio-values"]'.
    Por isso o padrão aqui é headless=False (navegador visível), igual ao
    teste manual que já funcionava. Em servidor sem display, rode via
    `xvfb-run -a python3 latam_scraper.py` em vez de forçar headless=True
    -- ver docs/scraper-local-setup.md.
    """
    headless = os.environ.get("LATAM_SCRAPER_HEADLESS", "false").strip().lower() == "true"
    try:
        tiers = asyncio.run(fetch_all_miles_tiers(headless=headless))
        if not tiers:
            raise RuntimeError("Nenhum tier de milhas foi encontrado na página.")
        state = _build_state_json(tiers)
        print(json.dumps(state, ensure_ascii=False, indent=2))
    except Exception as exc:  # noqa: BLE001 -- reportar qualquer falha ao cron
        print(f"latam_scraper falhou: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()