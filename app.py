import streamlit as st
import pandas as pd
import requests
import re
import time
import math
from io import BytesIO

# ⚠️ SEMPRE no topo
st.set_page_config(
    page_title="Brx Consultas Empresariais",
    layout="centered"
)

# ================== FUNÇÕES ==================

CNPJ_REGEX = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}[\/]?\d{4}-?\d{2}\b")

def normalizar_texto(valor):
    if valor is None:
        return ""
    if isinstance(valor, float) and math.isnan(valor):
        return ""
    s = str(valor).strip()
    if s.lower() in ("nan", "none", ""):
        return ""
    return s

def extrair_cnpj(texto):
    if not texto:
        return None
    m = CNPJ_REGEX.search(texto)
    return m.group(0) if m else None

def serper_search(query, serper_key, num_results=10):
    url = "https://google.serper.dev/search"
    headers = {
        "X-API-KEY": serper_key,
        "Content-Type": "application/json",
    }
    payload = {"q": query, "num": num_results}
    r = requests.post(url, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()

def processar_planilha(df, serper_key, uf_padrao, cidade_padrao, sleep_s, sites_alvo, top_n=2):
    # colunas opcionais
    if "CIDADE" not in df.columns:
        df["CIDADE"] = ""
    if "UF" not in df.columns:
        df["UF"] = ""

    # coluna obrigatória
    if "EMPRESA" not in df.columns:
        raise ValueError("A planilha precisa ter a coluna 'EMPRESA'.")

    saida = []
    total = len(df)

    progresso = st.progress(0)
    status_ui = st.empty()

    for idx, row in df.iterrows():
        empresa = normalizar_texto(row.get("EMPRESA", ""))

        cidade = normalizar_texto(row.get("CIDADE", "")) or cidade_padrao
        uf_linha = normalizar_texto(row.get("UF", "")) or uf_padrao

        status_ui.write(
            f"[{idx+1}/{total}] {empresa or '—'} | {cidade or '—'} | {uf_linha or '—'}"
        )

        if not empresa:
            saida.append({
                "EMPRESA": "",
                "CIDADE": cidade,
                "UF": uf_linha,
                "CNPJ_ENCONTRADO": "",
                "STATUS": "SEM EMPRESA"
            })
            progresso.progress(int((idx + 1) / total * 100))
            continue

        base = f"{empresa} {cidade} {uf_linha}" if cidade else f"{empresa} {uf_linha}"

        cnpj = ""
        status = "NÃO ENCONTRADO"

        for site in sites_alvo:
            try:
                query = f"site:{site} {base} CNPJ"
                data = serper_search(query, serper_key, num_results=10)
                organic = data.get("organic") or []

                for item in organic[:top_n]:
                    texto = f"{item.get('title','')} {item.get('snippet','')}"
                    achou = extrair_cnpj(texto)
                    if achou:
                        cnpj = achou
                        status = "ENCONTRADO"
                        break

                if cnpj:
                    break

            except Exception:
                continue

        saida.append({
            "EMPRESA": empresa,
            "CIDADE": cidade,
            "UF": uf_linha,
            "CNPJ_ENCONTRADO": cnpj,
            "STATUS": status
        })

        time.sleep(float(sleep_s))
        progresso.progress(int((idx + 1) / total * 100))

    return pd.DataFrame(saida)

def df_para_excel_bytes(df_saida):
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_saida.to_excel(writer, index=False, sheet_name="resultado")
    buffer.seek(0)
    return buffer

# ================== INTERFACE ==================

st.title("🏢 Brx Consultas Empresariais")
st.subheader("Automação inteligente para localizar CNPJs a partir de listas de empresas")
st.caption("Envie sua planilha, clique em Rodar e baixe o resultado.")

serper_key = st.text_input("Serper API Key", type="password")

col1, col2, col3 = st.columns(3)
with col1:
    uf_padrao = st.text_input("UF (padrão)", value="MS")
with col2:
    cidade_padrao = st.text_input("Cidade (padrão, opcional)", value="")
with col3:
    sleep_s = st.number_input(
        "Delay entre buscas (segundos)",
        min_value=0.0,
        value=0.4,
        step=0.1
    )

sites_default = [
    "econodata.com.br",
    "cnpj.biz",
    "solutudo.com.br",
    "cnpja.com"
]
sites_txt = st.text_area(
    "Sites (um por linha)",
    value="\n".join(sites_default),
    height=120
)
sites_alvo = [s.strip() for s in sites_txt.splitlines() if s.strip()]

top_n = st.slider(
    "Quantos resultados analisar por site (TOP N)",
    min_value=1,
    max_value=10,
    value=2
)

arquivo = st.file_uploader(
    "Upload do Excel (.xlsx)",
    type=["xlsx"]
)

if st.button("▶️ Rodar busca", use_container_width=True):
    try:
        if not serper_key.strip():
            st.error("Cole sua Serper API Key.")
        elif arquivo is None:
            st.error("Envie um arquivo Excel (.xlsx).")
        elif not sites_alvo:
            st.error("Informe pelo menos 1 site.")
        else:
            df = pd.read_excel(arquivo)

            df_saida = processar_planilha(
                df=df,
                serper_key=serper_key.strip(),
                uf_padrao=uf_padrao.strip(),
                cidade_padrao=cidade_padrao.strip(),
                sleep_s=float(sleep_s),
                sites_alvo=sites_alvo,
                top_n=int(top_n),
            )

            st.success("Busca finalizada com sucesso!")
            st.dataframe(df_saida, use_container_width=True)

            excel_bytes = df_para_excel_bytes(df_saida)
            st.download_button(
                label="⬇️ Baixar cnpjs_encontrados.xlsx",
                data=excel_bytes,
                file_name="cnpjs_encontrados.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
    except Exception as e:
        st.error("Ocorreu um erro durante a execução.")
        st.exception(e)
