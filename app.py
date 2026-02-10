import streamlit as st

# =====================================================
# CONFIGURAÇÃO GERAL
# =====================================================
st.set_page_config(
    page_title="BRX Consultas",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# =====================================================
# ESTADO DE LOGIN
# =====================================================
if "logado" not in st.session_state:
    st.session_state.logado = False

# =====================================================
# CSS – LOGIN COMPACTO + RESPONSIVO (PC E CELULAR)
# =====================================================
st.markdown("""
<style>
/* Remove barra superior do Streamlit */
header { visibility: hidden; }
footer { visibility: hidden; }
div[data-testid="stToolbar"] { visibility: hidden; height: 0%; }

/* Centraliza e limita largura (card) */
.block-container {
    max-width: 420px;
    padding-top: 2rem;
    padding-bottom: 2rem;
}

/* Card do login */
.login-card {
    background: rgba(15, 23, 42, 0.95);
    border: 1px solid rgba(148, 163, 184, 0.15);
    border-radius: 16px;
    padding: 1.4rem 1.3rem;
    box-shadow: 0 14px 40px rgba(0,0,0,0.55);
}

/* Título */
.login-title {
    text-align: center;
    font-size: 1.25rem;
    font-weight: 700;
    margin-bottom: 0.25rem;
}

/* Subtítulo */
.login-sub {
    text-align: center;
    font-size: 0.85rem;
    color: #9ca3af;
    margin-bottom: 1.2rem;
}

/* Inputs compactos */
input {
    height: 38px !important;
    font-size: 0.9rem !important;
}

/* Botão compacto */
.stButton > button {
    width: 100%;
    height: 40px;
    font-size: 0.95rem;
    border-radius: 10px;
}

/* Mobile ainda mais compacto */
@media (max-width: 480px) {
    .block-container {
        padding-top: 1.2rem;
    }
    .login-card {
        padding: 1.1rem 1rem;
    }
}
</style>
""", unsafe_allow_html=True)

# =====================================================
# TELA DE LOGIN
# =====================================================
def tela_login():
    st.markdown('<div class="login-card">', unsafe_allow_html=True)

    st.markdown('<div class="login-title">🔐 BRX Consultas</div>', unsafe_allow_html=True)
    st.markdown('<div class="login-sub">Acesso restrito</div>', unsafe_allow_html=True)

    usuario = st.text_input("Usuário", placeholder="Digite seu usuário")
    senha = st.text_input("Senha", type="password", placeholder="Digite sua senha")

    if st.button("Entrar"):
        # 🔴 TROQUE AQUI SE QUISER OUTRO LOGIN
        if usuario == "Brx" and senha == "10203040":
            st.session_state.logado = True
            st.rerun()
        else:
            st.error("Usuário ou senha inválidos")

    st.markdown('</div>', unsafe_allow_html=True)

# =====================================================
# CONTROLE DE ACESSO
# =====================================================
if not st.session_state.logado:
    tela_login()
    st.stop()

# =====================================================
# APP PRINCIPAL (DEPOIS DO LOGIN)
# =====================================================
st.title("BRX Consultas Empresariais")
st.caption("Automação inteligente para localizar CNPJs a partir de listas de empresas")

st.markdown("---")

st.success("✅ Login realizado com sucesso")

# 🔽 DAQUI PRA BAIXO você pode colocar TODO o resto do seu app
# Exemplo base:

st.subheader("Consulta")
entrada = st.text_area(
    "Cole aqui nomes de empresas ou CNPJs (1 por linha):",
    height=150
)

if st.button("Buscar"):
    if not entrada.strip():
        st.warning("Informe pelo menos um item.")
    else:
        linhas = [l.strip() for l in entrada.splitlines() if l.strip()]
        st.write("Itens informados:")
        for l in linhas:
            st.write("•", l)

st.markdown("---")
st.caption("BRX Consultas • Interface compacta e responsiva")
