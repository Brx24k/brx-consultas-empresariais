import streamlit as st
import pandas as pd
import requests
import re
import time
import math
import hashlib
from io import BytesIO

# ================= CONFIG INICIAL =================
st.set_page_config(
    page_title="Brx Consultas Empresariais",
    layout="centered"
)

# ================= LOGIN MULTIUSUÁRIO =================

def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def check_password(plain: str, hashed_hex: str) -> bool:
    return sha256_hex(plain) == hashed_hex

def login_screen():
    st.title("🏢 Brx Consultas Empresariais")
    st.subheader("Automação inteligente para localizar CNPJs a partir de listas de empresas")
    st.write("---")

    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")

    if st.button("Entrar", use_container_width=True):
        try:
            usuarios = st.secrets["USERS"]
        except Exception:
            st.error("Usuários não configurados nos Secrets.")
            st.stop()

        if usuario in usuarios and check_password(senha, usuarios[usuario]):
            st.session_state["auth"] = True
            st.session_state["user"] = usuario
            st.rerun()
        else:
            st.error("Usuário ou senha inválidos.")

def require_auth():
    if "auth" not in st.session_state:
        st.session_state["auth"] = False
    if "user" not in st.session_state:
        st.session_state["user"] = ""

    if not st.session_state["auth"]:
        login_screen()
        st.stop()

def logout_button():
    if st.button("Sair", use_container_width=True):
        st.session_state["auth"] = False
        st.session_state["user"] = ""
        st.rerun()

require_auth()

# ================= API KEY FIXA =================
try:
    SERPER_KEY = st.secrets["SERPER_KEY"]
except Exception:
    st.error("SERPER_KEY não configurada nos Secrets.")
    st.stop()

# ================= FUNÇÕES =================

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

def serper_search(query, num_results=10):
    url = "https://google.serper.dev/search"
    headers = {
        "X-API-KEY": SERPER_KEY,
        "Content-Type": "application/json",
    }
    payload = {"q": query, "num": num_results}
    r = requests.post(url, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()

def processar_planilha(df, uf_padrao, cidade_padrao, sleep_s, sites_alvo, top_n=2):
    if "CIDADE" not in df.columns:
        df["CIDADE"] = ""
    if "UF" not in df.columns:
        df["UF"] = ""

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

        status_ui.write(f"[{idx+1}/{total}] {empresa or '—'} | {cidade or '—'} | {uf_linha or '—'}")

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
                data = serper_search(query)
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

# ================= INTERFACE =================

st.title("🏢 Brx Consultas Empresariais")
st.subheader("Automação inteligente para localizar CNPJs a partir de listas de empresas")
st.caption(f"Usuário logado: **{st.session_state['user']}**")

logout_button()
st.write("---")

col1, col2, col3 = st.columns(3)
with col1:
    uf_padrao = st.text_input("UF (padrão)", value="MS")
with col2:
    cidade_padrao = st.text_input("Cidade (padrão, opcional)", value="")
with col3:
    sleep_s = st.number_input("Delay entre buscas (segundos)", min_value=0.0, value=0.4, step=0.1)

sites_default = ["econodata.com.br", "cnpj.biz", "solutudo.com.br", "cnpja.com"]
sites_txt = st.text_area("Sites (um por linha)", value="\n".join(sites_default), height=120)
sites_alvo = [s.strip() for s in sites_txt.splitlines() if s.strip()]

top_n = st.slider("Resultados analisados por site (TOP N)", 1, 10, 2)

arquivo = st.file_uploader("Upload do Excel (.xlsx)", type=["xlsx"])

if st.button("▶️ Rodar busca", use_container_width=True):
    if arquivo is None:
        st.error("Envie um arquivo Excel.")
    else:
        df = pd.read_excel(arquivo)
        df_saida = processar_planilha(
            df,
            uf_padrao.strip(),
            cidade_padrao.strip(),
            sleep_s,
            sites_alvo,
            top_n,
        )

        st.success("Busca finalizada com sucesso!")
        st.dataframe(df_saida, use_container_width=True)

        excel_bytes = df_para_excel_bytes(df_saida)
        st.download_button(
            "⬇️ Baixar cnpjs_encontrados.xlsx",
            excel_bytes,
            "cnpjs_encontrados.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
