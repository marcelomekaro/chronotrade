"""Termos de uso e privacidade."""

import streamlit as st

from chronotrade import estado
from chronotrade.termos import texto_termos

st.title("Termos e privacidade")
st.markdown(texto_termos(estado.config_loja()))
