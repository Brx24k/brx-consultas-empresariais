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
    page_title="BRX Consultas Empresariais",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ================= LOGIN MULTIUSUÁRIO (HASH) =================
def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def check_password(plain: str, hashed_hex: str) -> bool:
    return sha256_hex(plain) == hashed_hex

def login_screen():
    # CSS SÓ PARA O LOGIN (não mexe no app após login)
    st.markdown("""
    <style>
      .login-card{
        background: rgba(15, 23, 42, .92);
        border: 1px solid rgba(148, 163, 184, .18);
        border-radius: 16px;
        padding: 18px 18px 12px 18px;
        box-shadow: 0 14px 36px rgba(0,0,0,.35);
      }
      .login-title{
        text-align:center;
        font-size: 1.15rem;
        font-weight: 700;
        margin: 0;
      }
      .login-sub{
        text-align:center;
        font-size: .85rem;
        color: rgba(203,213,225,.75);
        margin: 6px 0 14px 0;
      }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    cL, cM, cR = st.columns([1.2, 1.0, 1.2])

    with cM:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        st.markdown('<p class="login-title">🔐 BRX Consultas</p>', unsafe_allow_html=True)
        st.markdown('<p class="login-sub">Acesso restrito</p>', unsafe_allow_html=True)

        usuario = st.text_input("Usuário", placeholder="Ex: admin")
        senha = st.text_input("Senha", type="password", placeholder="Sua senha")

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

        st.markdown('</div>', unsafe_allow_html=True)

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
    headers = {"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"}
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

# ================= UI CLEAN (TOPO HORIZONTAL) =================
st.markdown("""
<style>
/* Barra superior clean */
.topbar {
  padding: 10px 0 12px 0;
  border-bottom: 1px solid rgba(255,255,255,.10);
  margin-bottom: 14px;
}
.small-btn button{
  height: 32px !important;
  padding: 0 14px !important;
  font-size: 0.85rem !important;
}
</style>
""", unsafe_allow_html=True)

# Linha 1: Nome (esq) + Sair (dir)
t1, t2 = st.columns([6, 1.4], vertical_alignment="center")
with t1:
    st.markdown("### 🏢 BRX Consultas Empresariais")
    st.caption("Localize CNPJs a partir de listas de empresas (Serper)")
with t2:
    st.markdown('<div class="small-btn">', unsafe_allow_html=True)
    if st.button("Sair", use_container_width=True):
        st.session_state["auth"] = False
        st.session_state["user"] = ""
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# Linha 2: Configs em linha
c1, c2, c3, c4, c5 = st.columns([1, 1.8, 1.3, 1.0, 3.2], vertical_alignment="bottom")
uf_padrao = c1.text_input("UF", value="MS")
cidade_padrao = c2.text_input("Cidade", value="")
sleep_s = c3.slider("Delay", 0.0, 2.0, 0.4, 0.1)
top_n = c4.slider("TOP N", 1, 10, 2)
sites_txt = c5.text_input("Sites (separados por vírgula)",
                          value="econodata.com.br, cnpj.biz, solutudo.com.br, cnpja.com")

sites_alvo = [s.strip() for s in sites_txt.split(",") if s.strip()]

st.markdown("---")

# ================= APP PRINCIPAL (IGUAL) =================
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
    _ = st.empty()

if rodar:
    try:
        if arquivo is None:
            st.error("Envie um arquivo Excel (.xlsx).")
        elif not sites_alvo:
            st.error("Informe pelo menos 1 site.")
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

            total_empresas = int((df_saida["STATUS"] != "SEM EMPRESA").sum())
            encontrados = int((df_saida["STATUS"] == "ENCONTRADO").sum())
            nao_encontrados = int((df_saida["STATUS"] == "NÃO ENCONTRADO").sum())

            with right:
                st.markdown("### 📊 Resultado")
                kpi1, kpi2, kpi3 = st.columns(3)
                kpi1.metric("Empresas", total_empresas)
                kpi2.metric("Encontrados", encontrados)
                kpi3.metric("Não encontrados", nao_encontrados)

                st.caption(f"Tempo: {duracao:.1f}s | Sites: {len(sites_alvo)} | TOP N: {int(top_n)}")
                st.success("Busca finalizada com sucesso!")

                st.dataframe(df_saida, use_container_width=True, height=520)

                excel_bytes = df_para_excel_bytes(df_saida)
                st.download_button(
                    "⬇️ Baixar cnpjs_encontrados.xlsx",
                    excel_bytes,
                    "cnpjs_encontrados.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
    except Exception as e:
        st.error("Ocorreu um erro durante a execução.")
        st.exception(e)
