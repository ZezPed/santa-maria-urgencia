"""Gera dashboard.html (autónomo, sem dependências) a partir de dados/santa_maria_geral.csv.

Uso:
  python gerar_dashboard.py                      # lê dados/santa_maria_geral.csv -> dashboard.html
  python gerar_dashboard.py entrada.csv saida.html
O santa_maria_agent.py chama isto automaticamente depois de cada recolha.
"""
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

AQUI = Path(__file__).parent
CSV_PATH = AQUI / "dados" / "santa_maria_geral.csv"
OUT_PATH = AQUI / "dashboard.html"
TEMPLATE = AQUI / "dashboard_template.html"

# coluna do CSV -> chave curta usada no HTML
CAMPOS = {
    "utentes_1a_obs": "n", "tempo_medio_1a_obs_min": "med", "tempo_max_1a_obs_min": "max",
    "laranja_n": "ln", "laranja_min": "lm", "amarelo_n": "an", "amarelo_min": "am",
    "verde_n": "vn", "verde_min": "vm", "azul_n": "bn", "azul_min": "bm",
}


def ler(csv_path: Path) -> list[dict]:
    if not csv_path.exists():
        return []
    linhas = []
    with csv_path.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            try:
                fonte = datetime.strptime(r["atualizacao_fonte"], "%Y-%m-%d %H:%M")
                linha = {"fonte": fonte.strftime("%Y-%m-%dT%H:%M")}
                linha.update({curto: int(r[col]) for col, curto in CAMPOS.items()})
            except (KeyError, ValueError):
                continue  # linha incompleta/antiga: ignora em vez de partir o painel
            linhas.append(linha)
    linhas.sort(key=lambda x: x["fonte"])
    return linhas


def gerar(csv_path: Path = CSV_PATH, out_path: Path = OUT_PATH) -> Path:
    dados = json.dumps(ler(csv_path), ensure_ascii=False).replace("</", "<\\/")
    html = (TEMPLATE.read_text(encoding="utf-8")
            .replace("__DATA__", dados)
            .replace("__GERADO__", datetime.now().strftime("%d/%m/%Y %H:%M")))
    out_path.write_text(html, encoding="utf-8")
    return out_path


if __name__ == "__main__":
    args = [Path(a) for a in sys.argv[1:]]
    print(gerar(*args))
