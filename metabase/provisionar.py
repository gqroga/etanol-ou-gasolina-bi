"""Cria (ou recria) o dashboard do projeto no Metabase pela API.

Uso: .venv/bin/python metabase/provisionar.py
Idempotente: na segunda execução arquiva a coleção antiga e monta tudo de novo.
Todas as consultas leem a camada mart com o usuário bi_reader, como o Power BI.
"""
import re
import time
import uuid
from pathlib import Path

import requests
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
cfg = dotenv_values(ROOT / ".env")
URL = f"http://localhost:{cfg.get('METABASE_PORT', '3000')}"
COLECAO = "Combustíveis MBA"
NOME_BANCO = "DW Combustíveis (mart)"

AZUL, LARANJA, VERDE_AGUA, CINZA = "#2A78D6", "#EB6834", "#1BAF7A", "#C3C2B7"

s = requests.Session()


def api(method, path, **kw):
    r = s.request(method, URL + "/api" + path, timeout=120, **kw)
    if not r.ok:
        raise RuntimeError(f"{method} {path} -> {r.status_code}: {r.text[:500]}")
    return r.json() if r.text else None


# ---------------------------------------------------------------- setup e login

def preparar():
    for _ in range(60):
        try:
            if requests.get(URL + "/api/health", timeout=5).json().get("status") == "ok":
                break
        except requests.RequestException:
            pass
        time.sleep(5)
    props = api("GET", "/session/properties")
    if not props.get("has-user-setup"):
        api("POST", "/setup", json={
            "token": props["setup-token"],
            "user": {"first_name": "Admin", "last_name": "MBA", "email": cfg["MB_ADMIN_EMAIL"],
                     "password": cfg["MB_ADMIN_PASSWORD"], "site_name": "Combustíveis MBA"},
            "prefs": {"site_name": "Combustíveis MBA", "site_locale": "pt_BR", "allow_tracking": False},
        })
    sessao = api("POST", "/session", json={"username": cfg["MB_ADMIN_EMAIL"], "password": cfg["MB_ADMIN_PASSWORD"]})
    s.headers["X-Metabase-Session"] = sessao["id"]
    api("PUT", "/setting/custom-formatting", json={"value": {
        "type/Number": {"number_separators": ",."},
        "type/Currency": {"currency": "BRL", "currency_style": "symbol"},
    }})


def banco():
    for db in api("GET", "/database")["data"]:
        if db["name"] == NOME_BANCO:
            return db["id"]
    return api("POST", "/database", json={
        "engine": "postgres", "name": NOME_BANCO,
        "details": {"host": "postgres", "port": 5432, "dbname": cfg["POSTGRES_DB"],
                    "user": "bi_reader", "password": cfg["BI_PASSWORD"], "ssl": False,
                    "schema-filters-type": "inclusion", "schema-filters-patterns": "mart"},
    })["id"]


def colecao_nova():
    for c in api("GET", "/collection"):
        if c.get("name") == COLECAO and not c.get("archived"):
            api("PUT", f"/collection/{c['id']}", json={"archived": True})
    return api("POST", "/collection", json={"name": COLECAO, "color": AZUL})["id"]


# ---------------------------------------------------------------- consultas

BASE = """FROM mart.vw_fato_preco f
JOIN mart.vw_dim_data d       ON d.sk_data = f.sk_data
JOIN mart.vw_dim_localidade l ON l.sk_localidade = f.sk_localidade
JOIN mart.vw_dim_produto p    ON p.sk_produto = f.sk_produto
JOIN mart.vw_dim_bandeira b   ON b.sk_bandeira = f.sk_bandeira
WHERE f.fl_outlier = 0"""
F_ANO = "\n  [[AND d.ano = {{ano}}]]"
F_UF = "\n  [[AND l.uf_sigla = {{uf}}]]"
PARIDADE = ("AVG(f.valor_venda) FILTER (WHERE p.produto = 'ETANOL') / "
            "AVG(f.valor_venda) FILTER (WHERE p.produto = 'GASOLINA')")

TAGS = {
    "ano": {"name": "ano", "display-name": "Ano", "type": "number"},
    "uf": {"name": "uf", "display-name": "UF", "type": "text"},
}


def col(nome, **fmt):
    return {f'["name","{nome}"]': fmt}


def card(db, colecao, nome, sql, display, viz=None, desc=""):
    # Os filtros do card saem da própria SQL: {{ano}} / {{uf}} viram template tags e mapeamentos no dashboard
    tags = [t for t in TAGS if re.search(r"\{\{\s*" + t + r"\s*\}\}", sql)]
    template_tags = {t: {**TAGS[t], "id": str(uuid.uuid4())} for t in tags}
    c = api("POST", "/card", json={
        "name": nome, "description": desc or None, "collection_id": colecao, "display": display,
        "dataset_query": {"type": "native", "database": db,
                          "native": {"query": sql, "template-tags": template_tags}},
        "visualization_settings": viz or {},
    })
    c["_tags"] = tags
    return c


def cards(db, col_id):
    R = lambda nome, sql, display, viz=None, desc="": card(db, col_id, nome, sql, display, viz, desc)
    # Ano + UF: KPIs e detalhes. Comparações entre estados (manchete, paridade por UF) ficam só com Ano.
    preco = lambda prod: f"SELECT ROUND(AVG(f.valor_venda), 3) AS valor\n{BASE}\n  AND p.produto = '{prod}'{F_ANO}{F_UF}"
    brl = {"column_settings": col("valor", prefix="R$ ", decimals=3)}
    serie_cores = {"GASOLINA": {"color": AZUL}, "ETANOL": {"color": LARANJA}, "DIESEL S10": {"color": VERDE_AGUA}}
    meta70 = {"graph.show_goal": True, "graph.goal_value": 0.7, "graph.goal_label": "limite de 70%"}

    c = {}
    # --- Visão geral
    c["gas"] = R("Preço médio da gasolina", preco("GASOLINA"), "scalar", brl)
    c["eta"] = R("Preço médio do etanol", preco("ETANOL"), "scalar", brl)
    c["par"] = R("Paridade etanol ÷ gasolina",
                 f"SELECT ROUND({PARIDADE}, 3) AS valor\n{BASE}{F_ANO}{F_UF}", "scalar",
                 {"column_settings": col("valor", decimals=3)},
                 desc="Etanol rende ~70% da gasolina: paridade ≤ 0,70 → etanol compensa")
    c["postos"] = R("Postos pesquisados", f"SELECT COUNT(DISTINCT f.sk_revenda) AS valor\n{BASE}{F_ANO}{F_UF}", "scalar")
    c["tend"] = R("Gasolina subiu mais que o etanol entre 2023 e 2025",
                  f"""SELECT d.ano_mes AS mes, p.produto, ROUND(AVG(f.valor_venda), 3) AS preco
{BASE}
  AND p.produto IN ('GASOLINA', 'ETANOL', 'DIESEL S10')
GROUP BY 1, 2 ORDER BY 1""", "line",
                  {"graph.dimensions": ["mes", "produto"], "graph.metrics": ["preco"],
                   "series_settings": serie_cores, "graph.x_axis.title_text": "",
                   "graph.y_axis.title_text": "R$ por litro", "graph.y_axis.auto_range": False,
                   "graph.y_axis.min": 3.5, "graph.y_axis.max": 7})
    # --- O achado
    c["manchete"] = R("No Brasil (todas as UFs, não muda com o filtro UF)", f"""WITH uf AS (
  SELECT l.uf_sigla, {PARIDADE} AS paridade
  {BASE}{F_ANO}
  GROUP BY l.uf_sigla
)
SELECT format('No Brasil, o etanol compensou em %s de %s estados',
              COUNT(*) FILTER (WHERE paridade <= 0.70), COUNT(paridade)) AS valor
FROM uf""", "scalar")
    c["par_uf"] = R("Paridade por estado, todas as UFs (azul = etanol compensa)", f"""WITH uf AS (
  SELECT l.uf_sigla AS uf, {PARIDADE} AS paridade
  {BASE}{F_ANO}
  GROUP BY l.uf_sigla
)
SELECT uf,
       CASE WHEN paridade <= 0.70 THEN ROUND(paridade, 4) END AS "Etanol compensa",
       CASE WHEN paridade >  0.70 THEN ROUND(paridade, 4) END AS "Gasolina compensa"
FROM uf WHERE paridade IS NOT NULL
ORDER BY paridade""", "bar",
                   {"graph.dimensions": ["uf"], "graph.metrics": ["Etanol compensa", "Gasolina compensa"],
                    "stackable.stack_type": "stacked",
                    "series_settings": {"Etanol compensa": {"color": AZUL}, "Gasolina compensa": {"color": CINZA}},
                    "graph.y_axis.auto_range": False, "graph.y_axis.min": 0.5, "graph.y_axis.max": 0.95,
                    "graph.x_axis.title_text": "", "graph.y_axis.title_text": "etanol ÷ gasolina", **meta70})
    c["par_mes"] = R("Paridade nacional: etanol compensou de ago/2023 a dez/2024 (jul–ago/2024 no limite)",
                     f"""SELECT d.ano_mes AS mes, ROUND({PARIDADE}, 3) AS paridade
{BASE}
GROUP BY 1 ORDER BY 1""", "line",
                     {"graph.dimensions": ["mes"], "graph.metrics": ["paridade"],
                      "series_settings": {"paridade": {"color": AZUL}},
                      "graph.y_axis.auto_range": False, "graph.y_axis.min": 0.6, "graph.y_axis.max": 0.85,
                      "graph.x_axis.title_text": "", "graph.y_axis.title_text": "etanol ÷ gasolina", **meta70})
    c["pct_mun"] = R("Municípios onde o etanol compensou (Brasil ou UF do filtro)", f"""WITH m AS (
  SELECT l.municipio_uf, {PARIDADE} AS paridade
  {BASE}{F_ANO}{F_UF}
  GROUP BY l.municipio_uf
)
SELECT ROUND(AVG(CASE WHEN paridade <= 0.70 THEN 1.0 ELSE 0 END), 4) AS valor
FROM m WHERE paridade IS NOT NULL""", "scalar",
                     {"column_settings": col("valor", number_style="percent", decimals=1)})
    c["ufs_mes"] = R("Nº de estados em que o etanol compensava, mês a mês",
                     """SELECT ano_mes AS mes, COUNT(*) FILTER (WHERE etanol_compensa) AS ufs
FROM mart.vw_paridade_mensal_uf
GROUP BY 1 ORDER BY 1""", "bar",
                     {"graph.dimensions": ["mes"], "graph.metrics": ["ufs"],
                      "series_settings": {"ufs": {"color": AZUL}},
                      "graph.x_axis.title_text": "", "graph.y_axis.title_text": "UFs"})
    # --- Na sua cidade
    c["tab_mun"] = R("Etanol ou gasolina? Por município", f"""SELECT l.municipio_uf AS "Município",
       ROUND(AVG(f.valor_venda) FILTER (WHERE p.produto = 'ETANOL'), 3)   AS "Etanol (R$)",
       ROUND(AVG(f.valor_venda) FILTER (WHERE p.produto = 'GASOLINA'), 3) AS "Gasolina (R$)",
       ROUND({PARIDADE}, 4) AS "Paridade",
       CASE WHEN {PARIDADE} <= 0.70 THEN 'Etanol' ELSE 'Gasolina' END AS "Melhor escolha"
{BASE}{F_ANO}{F_UF}
GROUP BY l.municipio_uf
HAVING {PARIDADE} IS NOT NULL
ORDER BY "Paridade\"""", "table",
                     {"table.column_formatting": [{"columns": ["Melhor escolha"], "type": "single",
                                                   "operator": "=", "value": "Etanol", "color": AZUL,
                                                   "highlight_row": True}],
                      "column_settings": col("Paridade", decimals=4)})
    c["bandeira"] = R("Gasolina: bandeira branca × distribuidora, por região (ou UF do filtro)",
                      f"""SELECT l.regiao_nome AS regiao, b.tipo_bandeira AS tipo, ROUND(AVG(f.valor_venda), 3) AS preco
{BASE}
  AND p.produto = 'GASOLINA'{F_ANO}{F_UF}
GROUP BY 1, 2 ORDER BY 1, 2""", "bar",
                      {"graph.dimensions": ["regiao", "tipo"], "graph.metrics": ["preco"],
                       "series_settings": {"Bandeira branca": {"color": AZUL}, "Distribuidora": {"color": CINZA}},
                       "graph.show_values": True,
                       "graph.x_axis.title_text": "", "graph.y_axis.title_text": "R$ por litro"})
    # --- Qualidade
    c["log"] = R("Validações da última carga (dw.log_carga)",
                 "SELECT verificacao AS \"Verificação\", valor AS \"Valor\", ok AS \"OK\" FROM mart.vw_log_carga",
                 "table")
    c["coletas_mes"] = R("Coletas por mês (todas, inclusive outliers)",
                         """SELECT d.ano_mes AS mes, COUNT(*) AS coletas
FROM mart.vw_fato_preco f JOIN mart.vw_dim_data d ON d.sk_data = f.sk_data
GROUP BY 1 ORDER BY 1""", "bar",
                         {"graph.dimensions": ["mes"], "graph.metrics": ["coletas"],
                          "series_settings": {"coletas": {"color": AZUL}}, "graph.x_axis.title_text": ""})
    c["outliers"] = R("Outliers marcados (3×IQR, não apagados)",
                      """SELECT ROUND(AVG(fl_outlier::numeric), 4) AS valor FROM mart.vw_fato_preco""", "scalar",
                      {"column_settings": col("valor", number_style="percent", decimals=2)})
    c["produtos"] = R("Preço por produto", f"""SELECT p.produto AS "Produto", COUNT(*) AS "Coletas",
       ROUND(AVG(f.valor_venda), 3) AS "Preço médio",
       ROUND(percentile_cont(0.5) WITHIN GROUP (ORDER BY f.valor_venda)::numeric, 3) AS "Mediana",
       ROUND(STDDEV_SAMP(f.valor_venda) / AVG(f.valor_venda), 4) AS "Dispersão (CV)"
{BASE}{F_ANO}{F_UF}
GROUP BY 1 ORDER BY 3 DESC""", "table",
                      {"column_settings": col("Dispersão (CV)", number_style="percent", decimals=1)})
    return c


# ---------------------------------------------------------------- dashboard

TEXTO = {
    "achado": "### Onde vale a pena abastecer com etanol?\n"
              "O etanol rende cerca de 70% da gasolina. Por isso ele só compensa quando custa **até 70%** do preço dela. "
              "Na média nacional, isso aconteceu de ago/2023 a dez/2024 (jul e ago/2024 ficaram no limite, em 0,70). Em 2025, só valeu a pena no cinturão "
              "produtor do Centro-Sul (MS, MT, SP e PR). **A regra dos 70% depende de onde você mora.**",
    "qualidade": "**Pipeline:** CSV ANP → Pentaho (staging → limpeza → modelo estrela) → views `mart` → Metabase / Power BI / notebook. "
                 "Regras do ETL: linhas vazias descartadas, CNPJ só com dígitos, unidade e bandeiras unificadas, "
                 "duplicatas removidas no grão, outliers marcados (não apagados).",
    "fonte": "**Fonte:** ANP, Série Histórica de Preços de Combustíveis, 2023–2025. "
             "2,6 milhões de coletas em 13,5 mil postos. Preços sem outliers (3×IQR).",
}
TITULOS = {
    "h_evidencia": "A evidência",
    "h_cidade": "Na sua cidade: escolha a UF no filtro (azul = etanol compensa)",
    "h_qualidade": "Qualidade dos dados e pipeline",
}

# Página única, na ordem da narrativa: pergunta → KPIs → achado → evidência → detalhe → qualidade.
# (chave, col, linha, largura, altura), grade de 24 colunas. "#" = texto, "=" = título de seção.
LAYOUT = [
    ("#achado", 0, 0, 24, 3),
    ("gas", 0, 3, 6, 3), ("eta", 6, 3, 6, 3), ("par", 12, 3, 6, 3), ("postos", 18, 3, 6, 3),
    ("manchete", 0, 6, 16, 3), ("pct_mun", 16, 6, 8, 3),
    ("par_uf", 0, 9, 24, 8),
    ("=h_evidencia", 0, 17, 24, 1),
    ("par_mes", 0, 18, 12, 7), ("ufs_mes", 12, 18, 12, 7),
    ("tend", 0, 25, 24, 7),
    ("=h_cidade", 0, 32, 24, 1),
    ("tab_mun", 0, 33, 14, 10), ("bandeira", 14, 33, 10, 10),
    ("=h_qualidade", 0, 43, 24, 1),
    ("#qualidade", 0, 44, 24, 2),
    ("log", 0, 46, 10, 8), ("outliers", 10, 46, 14, 3), ("coletas_mes", 10, 49, 14, 5),
    ("produtos", 0, 54, 24, 7),
    ("#fonte", 0, 61, 24, 2),
]


def texto(display, conteudo):
    return {"virtual_card": {"name": None, "display": display, "visualization_settings": {},
                             "dataset_query": {}, "archived": False}, "text": conteudo}


def opcoes(db, sql):
    """Valores distintos lidos do DW, para as listas de seleção dos filtros."""
    r = api("POST", "/dataset", json={"database": db, "type": "native", "native": {"query": sql}})
    return [str(linha[0]) for linha in r["data"]["rows"]]


def lista(valores):
    # Lista fechada: o usuário escolhe um valor, sem campo de digitação
    return {"values_query_type": "list", "values_source_type": "static-list",
            "values_source_config": {"values": valores}, "isMultiSelect": False}


def dashboard(db, col_id, c):
    anos = opcoes(db, "SELECT DISTINCT ano FROM mart.vw_dim_data ORDER BY 1")
    ufs = opcoes(db, "SELECT DISTINCT uf_sigla FROM mart.vw_dim_localidade WHERE sk_localidade > 0 ORDER BY 1")
    params = [
        {"id": "ano", "name": "Ano", "slug": "ano", "type": "number/=", "sectionId": "number",
         "default": [int(anos[-1])], **lista(anos)},
        {"id": "uf", "name": "UF", "slug": "uf", "type": "string/=", "sectionId": "string", **lista(ufs)},
    ]
    d = api("POST", "/dashboard", json={
        "name": "Etanol ou gasolina? Preços de combustíveis 2023–2025", "collection_id": col_id,
        "description": "Projeto integrador MBA: Pentaho → Postgres (mart) → Metabase", "parameters": params,
        "width": "full",
    })
    dashcards = []
    for i, (chave, x, y, w, h) in enumerate(LAYOUT):
        dc = {"id": -(i + 1), "col": x, "row": y, "size_x": w, "size_y": h, "parameter_mappings": [], "series": []}
        if chave.startswith("#"):
            dc.update(card_id=None, visualization_settings=texto("text", TEXTO[chave[1:]]))
        elif chave.startswith("="):
            dc.update(card_id=None, visualization_settings=texto("heading", TITULOS[chave[1:]]))
        else:
            card_ = c[chave]
            dc.update(card_id=card_["id"], visualization_settings={}, parameter_mappings=[
                {"parameter_id": t, "card_id": card_["id"], "target": ["variable", ["template-tag", t]]}
                for t in card_["_tags"]])
        dashcards.append(dc)
    api("PUT", f"/dashboard/{d['id']}", json={"dashcards": dashcards, "parameters": params})
    return d["id"]


if __name__ == "__main__":
    preparar()
    db = banco()
    col_id = colecao_nova()
    c = cards(db, col_id)
    dash = dashboard(db, col_id, c)
    print(f"Dashboard pronto: {URL}/dashboard/{dash}  ({len(c)} perguntas)")
