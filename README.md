# Agente – Urgência Geral do Hospital de Santa Maria

Regista, a cada execução, uma linha em `dados/santa_maria_geral.csv`:

| coluna | significado |
|---|---|
| `recolhido_em` | quando o agente correu |
| `atualizacao_fonte` | "Última atualização de dados" mostrada pelo site |
| `utentes_1a_obs` | nº de utentes à espera de 1ª observação |
| `tempo_medio_1a_obs_min` / `tempo_max_1a_obs_min` | espera média / máxima para 1ª observação (minutos) |
| `laranja_*`, `amarelo_*`, `verde_*`, `azul_*` | nº de utentes (`_n`) e tempo médio (`_min`) por cor |

Cores (Manchester, como o site as nomeia): laranja = Muito urgente, amarelo = Urgente,
verde = Pouco urgente, azul = Não urgente. (Vermelho/"Emergente" não é publicado.)

Se a fonte ainda não foi atualizada desde a última linha, não grava duplicados.

## Dashboard
`dashboard.html` (abre no browser, funciona offline, claro/escuro) é regenerado no fim de cada recolha.
Mostra a última leitura, a evolução da espera (média/máx e por cor), os utentes por cor e o padrão por
hora do dia, com filtro de período e tabela de dados. Também se gera à mão:
```
python gerar_dashboard.py
```
A página recarrega-se sozinha de 5 em 5 minutos.

## Na nuvem (GitHub Actions) – corre com o PC desligado
`.github/workflows/recolha.yml` corre o agente de ~10 em ~10 min nos servidores do GitHub, grava o CSV
no repositório e publica o dashboard no GitHub Pages (`https://<utilizador>.github.io/<repositório>/`).
- Settings → Pages → Source: **GitHub Actions** (obrigatório, uma vez).
- Correr à mão: separador Actions → "Recolha Santa Maria" → Run workflow.
- O GitHub pode atrasar ou saltar execuções agendadas; buracos pontuais nos dados são normais.
- Com a nuvem ligada, desativa a tarefa agendada local para não haver dois CSV diferentes.

## Requisitos
```
pip install playwright
playwright install chromium
```

## Correr
```
python santa_maria_agent.py            # uma recolha (~1-2 min: o Power BI demora a carregar)
python santa_maria_agent.py --debug    # mostra o texto lido, para diagnosticar mudanças no site
```

## Agendar (Windows) – a fonte atualiza de ~10 em ~10 min
```
schtasks /Create /SC MINUTE /MO 10 /TN "SantaMariaUrgencia" /TR "python C:\caminho\para\santa_maria_agent.py"
```

## Como funciona
O site não tem API de dados: mostra um relatório Power BI embebido. O agente abre
`https://tempos.min-saude.pt/instituicao/237?u=0` (237 = Hospital de Santa Maria, `u=0` = Urgência Geral)
num Chromium headless, espera que o relatório carregue e lê o texto. Só grava quando o cabeçalho e a
tabela por prioridade concordam entre si e duas leituras seguidas são iguais.
Se o site mudar de layout, o agente falha com erro em vez de gravar lixo.
