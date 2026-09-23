"""Regista os tempos de espera da Urgência Geral do Hospital de Santa Maria (Lisboa).

Fonte: https://tempos.min-saude.pt/instituicao/237  (relatório Power BI embebido).
Cada execução acrescenta uma linha a dados/santa_maria_geral.csv com:
  - tempo médio / máximo de espera para 1ª observação
  - nº de utentes à espera de 1ª observação (total)
  - por cor de triagem (laranja, amarelo, verde, azul): nº de utentes e tempo médio

Mapeamento Manchester usado pelo site:
  Muito urgente = laranja | Urgente = amarelo | Pouco urgente = verde | Não urgente = azul

Uso:
  python santa_maria_agent.py            # uma recolha
  python santa_maria_agent.py --debug    # imprime o texto lido do relatório
"""
import csv
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

INSTITUTION_ID = 237          # Hospital de Santa Maria - Lisboa
TIPOLOGIA_GERAL = 0           # parâmetro ?u= do site (1=Obstétrica, 2=Pediátrica)
URL = f"https://tempos.min-saude.pt/instituicao/{INSTITUTION_ID}?t=0&u={TIPOLOGIA_GERAL}"
TIMEOUT_S = 240
CSV_PATH = Path(__file__).parent / "dados" / "santa_maria_geral.csv"

COLUNAS = [
    "recolhido_em", "atualizacao_fonte",
    "utentes_1a_obs", "tempo_medio_1a_obs_min", "tempo_max_1a_obs_min",
    "laranja_n", "laranja_min", "amarelo_n", "amarelo_min",
    "verde_n", "verde_min", "azul_n", "azul_min",
]

TEMPO = r"(?:\d+h\s*)?\d+m"


def para_minutos(txt: str) -> int:
    h = re.search(r"(\d+)h", txt)
    m = re.search(r"(\d+)m", txt)
    return (int(h.group(1)) * 60 if h else 0) + (int(m.group(1)) if m else 0)


def extrair(texto: str) -> dict | None:
    """Devolve o registo ou None se o relatório ainda não carregou por completo."""
    t = re.sub(r"\s*\n\s*", " | ", texto)
    if "Urgência Geral" not in t:
        return None

    # Blocos "Nº Utentes | Médio | tempo | Máx tempo" pela ordem do funil:
    # [0] espera para triagem, [1] espera para 1ª observação, [2] em observação
    blocos = re.findall(
        rf"(\d+)\s*\|\s*Nº Utentes\s*\|\s*Médio\s*\|\s*({TEMPO})\s*\|\s*Máx\s*({TEMPO})", t
    )
    if len(blocos) < 2:
        return None
    n_obs, medio, maximo = blocos[1]

    # Tabela-resumo final: "Urgência Geral | ..." seguida das linhas por prioridade
    # (termina onde começa a "Urgência Obstétrica / Ginecológica").
    i = t.find("Tipologia de Urgência")
    j = t.find("Urgência Obstétrica", i)
    if i < 0 or j < 0:
        return None
    tabela = t[i:j]

    # Os visuais do Power BI carregam de forma independente: só aceita se a tabela-resumo
    # concordar com o bloco principal (mesmo tempo médio de 1ª observação).
    total = re.search(rf"Urgência Geral\s*\|\s*(\d+)\s*\|\s*({TEMPO})", tabela)
    if not total or para_minutos(total.group(2)) != para_minutos(medio):
        return None

    cores = {}
    for chave, nome in (("laranja", "Muito urgente"), ("amarelo", "Urgente"),
                        ("verde", "Pouco Urgente"), ("azul", "Não Urgente")):
        # "\| Urgente" não deve apanhar "Pouco Urgente"/"Não Urgente": exige o separador antes
        m = re.search(rf"\|\s*{nome}\s*\|\s*(\d+)\s*\|\s*({TEMPO})", tabela)
        if not m:
            return None
        cores[chave] = (int(m.group(1)), para_minutos(m.group(2)))

    fonte = re.search(r"atualização de dados a\s*(\d{2})/(\d{2})/(\d{4})\s*(\d{1,2})h\s*(\d{2})m", t)
    if not fonte:
        return None
    d, mth, y, hh, mm = fonte.groups()
    registo = {
        "atualizacao_fonte": f"{y}-{mth}-{d} {int(hh):02d}:{mm}",
        "utentes_1a_obs": int(n_obs),
        "tempo_medio_1a_obs_min": para_minutos(medio),
        "tempo_max_1a_obs_min": para_minutos(maximo),
    }
    for chave, (n, minutos) in cores.items():
        registo[f"{chave}_n"] = n
        registo[f"{chave}_min"] = minutos
    return registo


def recolher(debug: bool = False) -> dict:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 2200}, locale="pt-PT")
        page.goto(URL, wait_until="domcontentloaded")
        fim = time.time() + TIMEOUT_S
        texto = ""
        anterior = None
        while time.time() < fim:
            page.wait_for_timeout(4000)
            for frame in page.frames:
                if "powerbi.com" not in frame.url:
                    continue
                try:
                    t = frame.inner_text("body", timeout=3000)
                except Exception:
                    continue
                if "ESPERA PARA TRIAGEM" not in t:
                    continue  # outros relatórios (Consulta/Cirurgia) embebidos na página
                texto = t
                registo = extrair(texto)
                if debug:
                    print("leitura:", registo)
                # só confia numa leitura que se repita (os visuais estabilizaram)
                if registo and registo == anterior:
                    if debug:
                        print(texto.replace("\n", " | "))
                    browser.close()
                    return registo
                anterior = registo
        browser.close()
        if debug:
            print(texto)
        raise RuntimeError("O relatório não carregou a tempo (ou o formato da página mudou).")


def gravar(registo: dict) -> bool:
    """Acrescenta ao CSV. Devolve False se a fonte não foi actualizada desde a última linha."""
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    existe = CSV_PATH.exists()
    if existe and registo["atualizacao_fonte"]:
        with CSV_PATH.open(encoding="utf-8", newline="") as f:
            linhas = list(csv.DictReader(f))
        if linhas and linhas[-1]["atualizacao_fonte"] == registo["atualizacao_fonte"]:
            return False
    linha = {"recolhido_em": datetime.now().isoformat(timespec="seconds"), **registo}
    with CSV_PATH.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS)
        if not existe:
            w.writeheader()
        w.writerow(linha)
    return True


def main() -> int:
    debug = "--debug" in sys.argv
    try:
        registo = recolher(debug)
    except Exception as e:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] ERRO: {e}", file=sys.stderr)
        return 1
    novo = gravar(registo)
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {'gravado' if novo else 'sem alterações (mesma actualização da fonte)'}: {registo}")
    try:  # o painel nunca deve fazer falhar a recolha
        from gerar_dashboard import gerar
        gerar()
    except Exception as e:
        print(f"aviso: não consegui atualizar dashboard.html: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
