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
