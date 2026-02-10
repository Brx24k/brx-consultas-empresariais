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
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ================= CSS (LOGIN COMPACTO) =================
st.markdown("""
<style>
/* esconde barra superior/rodapé */
header { visibility: hidden; }
footer { visibility: hidden; }
div[data-testid="stToolbar"] { visibility: hidden; height: 0; }

/* centraliza e deixa compacto somente quando estiver no login */
.login-wrap .block-container {
  max-width: 460px;
  padding-top: 1.6rem;
  padding-bottom: 1.6rem;
}

/* inputs mais compactos */
.login-wrap input {
  height: 38px !important;
  font-size: 0.92rem !important;
}

/* botão compacto */
.login-wrap .stButton > button {
  height: 40px;
  border-radius: 10px;
  font-size: 0.95rem;
}

/* card do login */
.login-card{
  background: rgba(15, 23, 42, .94);
  border: 1px solid rgba(148, 163, 184, .18);
  border-radius: 16px;
  padding: 1.25rem 1.2rem;
  box-shadow: 0 14px 36px rgba(0,0,0,.45);
}
.login-title{
  text-align:center;
  font-size:1.15rem;
  font-weight:700;
  margin:0;
}
.login-sub{
  text-align:center;
  font-size:.85rem;
  color: rgba(203,213,225,.75);
  margin:.35rem 0 1rem 0;
}
</style>
""", unsafe_allow_html=True)

# ================= LOGIN MULTIUSUÁRIO (HASH) =================
def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def check_password(plain: str, hashed_hex: str) -> bool:
    return sha256_hex(plain) == hashed_hex

def login_screen():
    # wrapper pra aplicar CSS só no login
    st.markdown('<div class="login-wrap">', unsafe_allow_html=True)

    st.markdown('<div class="login-card">', unsafe_allow_html=True)
    st.markdown('<p class="login-title">🔐 Brx Consultas Empresariais</p>', unsafe_allow_html=True)
    st.markdown('<p class="login-sub">Acesso restrito</p>', unsafe_allow_html=True)

    usuario = st.text_input("Usuário", placeholder="Usuário", label_visibility="collapsed")
    senha = st.text_input("Senha", type="password", placeholder="Senha", label_visibility="collapsed")

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

    st.markdown('</div>', unsafe_allow_html=True)  # login-card
    st.markdown('</div>', unsafe_allow_html=True)  # login-wrap

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

    for idx, row
