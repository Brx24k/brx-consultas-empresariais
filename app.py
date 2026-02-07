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
    layout="wide"
)

# ================= LOGIN MULTIUSUÁRIO (HASH) =================

def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def check_password(plain: str, hashed_hex: str) -> bool:
    return sha256_hex(plain) == hashed_hex

def login_screen():
    st.markdown(
        """
        <div style="padding: 10px 0 0 0">
          <h1 style="margin:0">🏢 Brx Consultas Empresariais</h1>
          <p style="opacity:0.8; margin-top:6px">
            Automação inteligente para localizar CNPJs a partir de listas de empresas
          </p>
        </div>
        <hr/>
        """,
        unsafe_allow_html=True
    )

    st.markdown("### 🔐 Acesso")
    usuario = st.text_input("Usuário", placeholder="Ex: admin")
    senha = st.text_input("Senha", type="password", placeholder="Sua senha")

    c1, c2 = st.columns([1, 2])
    with c1:
        entrar = st.button("Entrar", use_container_width=True)

    if entrar:
        try:
            usuarios = st.secrets["USERS"]
        except Exception:
            st.error("USERS não configurado nos Secrets.")
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
                data = serper_search(query, num_results=10)
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

# ================= INTERFACE VISUAL (SEM LOGO) =================

# Sidebar (configurações)
with st.sidebar:
    st.markdown("## ⚙️ Configurações")
    st.caption(f"Usuário: **{st.session_state['user']}**")

    uf_padrao = st.text_input("UF padrão", value="MS")
    cidade_padrao = st.text_input("Cidade padrão (opcional)", value="")
    sleep_s = st.slider("Delay entre buscas (segundos)", 0.0, 2.0, 0.4, 0.1)

    st.markdown("---")
    st.markdown("### 🔎 Buscas")
    top_n = st.slider("TOP N por site", 1, 10, 2)

    sites_default = ["econodata.com.br", "cnpj.biz", "solutudo.com.br", "cnpja.com"]
    sites_txt = st.text_area("Sites (um por linha)", value="\n".join(sites_default), height=140)
    sites_alvo = [s.strip() for s in sites_txt.splitlines() if s.strip()]

    st.markdown("---")
    if st.button("Sair", use_container_width=True):
        st.session_state["auth"] = False
        st.session_state["user"] = ""
        st.rerun()

# Header
st.markdown(
    """
    <div style="padding: 8px 0 6px 0">
      <h1 style="margin:0">🏢 Brx Consultas Empresariais</h1>
      <p style="opacity:0.8; margin-top:6px">
        Automação inteligente para localizar CNPJs a partir de listas de empresas
      </p>
    </div>
    """,
    unsafe_allow_html=True
)

st.write("---")

# Layout em colunas
left, right = st.columns([1.1, 1.3])

with left:
    st.markdown("### 📥 Entrada")
    st.caption("Envie uma planilha Excel com a coluna **EMPRESA**. As colunas **CIDADE** e **UF** são opcionais.")
    arquivo = st.file_uploader("Upload do Excel (.xlsx)", type=["xlsx"])

    st.markdown("### ▶️ Execução")
    rodar = st.button("Rodar busca", use_container_width=True)

with right:
    st.markdown("### 📊 Resultado")
    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("Empresas", "—")
    kpi2.metric("Encontrados", "—")
    kpi3.metric("Não encontrados", "—")
    resultado_placeholder = st.empty()

if rodar:
    try:
        if arquivo is None:
            st.error("Envie um arquivo Excel (.xlsx).")
        elif not sites_alvo:
            st.error("Informe pelo menos 1 site na sidebar.")
        else:
            df = pd.read_excel(arquivo)

            t0 = time.time()
            df_saida = processar_planilha(
                df=df,
                uf_padrao=uf_padrao.strip(),
                cidade_padrao=cidade_padrao.strip(),
                sleep_s=float(sleep_s),
                sites_alvo=sites_alvo,
                top_n=int(top_n),
            )
            duracao = time.time() - t0

            # KPIs
            total_empresas = int((df_saida["STATUS"] != "SEM EMPRESA").sum())
            encontrados = int((df_saida["STATUS"] == "ENCONTRADO").sum())
            nao_encontrados = int((df_saida["STATUS"] == "NÃO ENCONTRADO").sum())

            # Atualiza KPIs
            right.markdown("### 📊 Resultado")
            kpi1, kpi2, kpi3 = right.columns(3)
            kpi1.metric("Empresas", total_empresas)
            kpi2.metric("Encontrados", encontrados)
            kpi3.metric("Não encontrados", nao_encontrados)

            right.caption(f"Tempo: {duracao:.1f}s | Sites: {len(sites_alvo)} | TOP N: {int(top_n)}")
            right.success("Busca finalizada com sucesso!")

            right.dataframe(df_saida, use_container_width=True, height=520)

            excel_bytes = df_para_excel_bytes(df_saida)
            right.download_button(
                "⬇️ Baixar cnpjs_encontrados.xlsx",
                excel_bytes,
                "cnpjs_encontrados.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
    except Exception as e:
        st.error("Ocorreu um erro durante a execução.")
        st.exception(e)
