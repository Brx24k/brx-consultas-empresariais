import streamlit as st
import pandas as pd
import requests
import re
import time
import math
import hashlib
from io import BytesIO

# ================= CONFIG =================
st.set_page_config(
    page_title="BRX Consultas Empresariais",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ================= LOGIN =================
def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def check_password(plain: str, hashed_hex: str) -> bool:
    return sha256_hex(plain) == hashed_hex

def login_screen():
    st.markdown("""
    <style>
      .login-card{
        background: #0f172a;
        border: 1px solid rgba(148,163,184,.18);
        border-radius: 14px;
        padding: 18px;
      }
    </style>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1.3,1,1.3])
    with c2:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        st.markdown("### 🔐 BRX Consultas")
        usuario = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")
        if st.button("Entrar", use_container_width=True):
            users = st.secrets["USERS"]
            if usuario in users and check_password(senha, users[usuario]):
                st.session_state.auth = True
                st.session_state.user = usuario
                st.rerun()
            else:
                st.error("Usuário ou senha inválidos")
        st.markdown("</div>", unsafe_allow_html=True)

def require_auth():
    if "auth" not in st.session_state:
        st.session_state.auth = False
    if "user" not in st.session_state:
        st.session_state.user = ""
    if not st.session_state.auth:
        login_screen()
        st.stop()

require_auth()

# ================= API =================
SERPER_KEY = st.secrets["SERPER_KEY"]

CNPJ_REGEX = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}[\/]?\d{4}-?\d{2}\b")

def normalizar(v):
    if v is None: return ""
    if isinstance(v, float) and math.isnan(v): return ""
    return str(v).strip()

def extrair_cnpj(txt):
    m = CNPJ_REGEX.search(txt or "")
    return m.group(0) if m else ""

def serper_search(q):
    r = requests.post(
        "https://google.serper.dev/search",
        headers={"X-API-KEY": SERPER_KEY},
        json={"q": q, "num": 10},
        timeout=30
    )
    r.raise_for_status()
    return r.json()

def processar(df, uf, cidade, delay, sites, top_n):
    saida = []
    prog = st.progress(0)
    total = len(df)

    for i, row in df.iterrows():
        empresa = normalizar(row.get("EMPRESA"))
        cid = normalizar(row.get("CIDADE")) or cidade
        uf_l = normalizar(row.get("UF")) or uf

        cnpj = ""
        status = "NÃO ENCONTRADO"

        if empresa:
            base = f"{empresa} {cid} {uf_l}"
            for s in sites:
                try:
                    data = serper_search(f"site:{s} {base} CNPJ")
                    for it in (data.get("organic") or [])[:top_n]:
                        achou = extrair_cnpj(it.get("title","")+" "+it.get("snippet",""))
                        if achou:
                            cnpj = achou
                            status = "ENCONTRADO"
                            break
                    if cnpj:
                        break
                except:
                    pass

        saida.append({
            "EMPRESA": empresa,
            "CIDADE": cid,
            "UF": uf_l,
            "CNPJ_ENCONTRADO": cnpj,
            "STATUS": status
        })

        time.sleep(delay)
        prog.progress(int((i+1)/total*100))

    return pd.DataFrame(saida)

def df_excel(df):
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False)
    buf.seek(0)
    return buf

# ================= TOPO =================
st.markdown("""
<style>
.logout button{
    height:28px !important;
    font-size:.8rem !important;
    padding:0 12px !important;
}
</style>
""", unsafe_allow_html=True)

t1, t2 = st.columns([7,1])
with t1:
    st.markdown("### 🏢 BRX Consultas Empresariais")
    st.caption("Localize CNPJs a partir de listas de empresas (Serper)")
with t2:
    st.markdown('<div class="logout">', unsafe_allow_html=True)
    if st.button("Sair"):
        st.session_state.auth = False
        st.session_state.user = ""
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# ================= CONFIGS EM LINHA =================
c1,c2,c3,c4,c5 = st.columns([1,1.6,1.2,1,3])
uf = c1.text_input("UF", "MS")
cidade = c2.text_input("Cidade", "")
delay = c3.slider("Delay",0.0,2.0,0.4,0.1)
top_n = c4.slider("TOP N",1,10,2)
sites_txt = c5.text_input("Sites",
    "econodata.com.br, cnpj.biz, solutudo.com.br, cnpja.com")
sites = [s.strip() for s in sites_txt.split(",") if s.strip()]

st.divider()

# ================= APP =================
l,r = st.columns([1.1,1.4])

with l:
    st.markdown("### 📥 Entrada")
    arq = st.file_uploader("Upload Excel (.xlsx)", type=["xlsx"])
    buscar = st.button("🔍 Buscar", use_container_width=True)

with r:
    st.markdown("### 📊 Resultado")
    k1,k2,k3 = st.columns(3)
    k1.metric("Empresas","—")
    k2.metric("Encontrados","—")
    k3.metric("Não encontrados","—")

if buscar:
    if not arq:
        st.error("Envie um Excel.")
    else:
        df = pd.read_excel(arq)
        df_out = processar(df, uf, cidade, delay, sites, top_n)

        tot = len(df_out)
        enc = (df_out["STATUS"]=="ENCONTRADO").sum()
        nao = tot-enc

        with r:
            k1.metric("Empresas", tot)
            k2.metric("Encontrados", enc)
            k3.metric("Não encontrados", nao)

            st.dataframe(df_out, use_container_width=True, height=520)
            st.download_button(
                "⬇️ Baixar Excel",
                df_excel(df_out),
                "cnpjs.xlsx",
                use_container_width=True
            )
