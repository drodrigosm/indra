# Componentes visuales comunes de Streamlit reutilizables por los distintos modulos de la aplicacion.

import streamlit as st
from HW_scanner import get_direct_content


def inject_custom_theme():
    css = (
        "<style>"
        ":root { --azul-oscuro:#001923; --turquesa:#00B0BD; --gris-ceramica:#E3E2DA; --azul-amazonico:#004254; --texto-claro:#E3E2DA; --texto-sobre-claro:#004254; --border-soft:rgba(227,226,218,0.22); --surface-soft:rgba(227,226,218,0.06); --surface-soft-2:rgba(227,226,218,0.10); }"
        "html, body, [data-testid='stAppViewContainer'], .stApp, .main, .block-container { background-color:var(--azul-amazonico) !important; color:var(--texto-claro) !important; }"
        "[data-testid='stHeader'] { background:var(--azul-amazonico) !important; }"
        "[data-testid='stSidebar'] { background-color:#F4F5F2 !important; border-right:1px solid rgba(0,66,84,0.12) !important; }"
        ".stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6, .stApp p, .stApp span, .stApp label, .stApp div, .stApp li { color:var(--texto-claro) !important; }"
        ".stMarkdown, .stCaption, .stText { color:var(--texto-claro) !important; }"
        "[data-testid='stSidebar'], [data-testid='stSidebar'] *, [data-testid='stSidebar'] label, [data-testid='stSidebar'] span, [data-testid='stSidebar'] div, [data-testid='stSidebar'] p, [data-testid='stSidebar'] small, [data-testid='stSidebar'] strong { color:var(--texto-sobre-claro) !important; }"
        "[data-testid='stSidebar'] h1, [data-testid='stSidebar'] h2, [data-testid='stSidebar'] h3, [data-testid='stSidebar'] h4, [data-testid='stSidebar'] h5, [data-testid='stSidebar'] h6 { color:var(--texto-sobre-claro) !important; font-weight:900 !important; }"
        "[data-testid='stSidebar'] div[data-baseweb='base-input'] > div, [data-testid='stSidebar'] .stTextInput input { background-color:#FFFFFF !important; color:var(--texto-sobre-claro) !important; border:1px solid rgba(0,66,84,0.25) !important; border-radius:10px !important; }"
        "[data-testid='stSidebar'] input, [data-testid='stSidebar'] [data-baseweb='input'] input { color:var(--texto-sobre-claro) !important; -webkit-text-fill-color:var(--texto-sobre-claro) !important; }"
        "[data-testid='stSidebar'] ::placeholder { color:rgba(0,66,84,0.65) !important; opacity:1 !important; }"
        ".stButton button, .stDownloadButton button { background-color:var(--turquesa) !important; color:var(--texto-claro) !important; border:1px solid var(--turquesa) !important; border-radius:8px !important; font-weight:700 !important; }"
        ".stButton button:hover, .stDownloadButton button:hover { background-color:var(--azul-oscuro) !important; color:var(--texto-claro) !important; border:1px solid var(--azul-oscuro) !important; }"
       "[data-testid='stSidebar'] .stButton button { background-color:var(--turquesa) !important; color:var(--texto-claro) !important; border:1px solid var(--turquesa) !important; border-radius:8px !important; font-weight:700 !important; }"
        "[data-testid='stSidebar'] .stButton button:hover { background-color:#55CDD6 !important; color:var(--texto-sobre-claro) !important; border:1px solid #55CDD6 !important; }"
        "[data-testid='stSidebar'] .stButton button[kind='primary'] { background-color:#BDEFF2 !important; color:var(--texto-sobre-claro) !important; border:2px solid #FF5A5F !important; box-shadow:0 0 0 2px rgba(255,90,95,0.18) !important; font-weight:900 !important; }"
        "[data-testid='stSidebar'] .stButton button[kind='primary']:hover { background-color:#DDFBFC !important; color:var(--texto-sobre-claro) !important; border:2px solid #FF5A5F !important; box-shadow:0 0 0 2px rgba(255,90,95,0.18) !important; }"
        "[data-testid='stSidebar'] .stButton button[kind='primary']:hover { background-color:#DDFBFC !important; color:var(--texto-sobre-claro) !important; border:2px solid #FF5A5F !important; }"        ".stTabs [data-baseweb='tab'] { color:var(--gris-ceramica) !important; background-color:transparent !important; font-weight:700 !important; }"
        ".stTabs [aria-selected='true'] { color:var(--turquesa) !important; border-bottom:2px solid var(--turquesa) !important; }"
        ".stSlider [data-baseweb='slider'] div { color:var(--texto-claro) !important; }"
        "[data-testid='stSidebar'] .stSlider [data-baseweb='slider'] div { color:var(--texto-sobre-claro) !important; }"
        "[data-testid='stCheckbox'] label span { color:inherit !important; }"
        "[data-testid='stExpander'] { border:1px solid rgba(227,226,218,0.22) !important; border-radius:12px !important; background:rgba(227,226,218,0.05) !important; }"
        "[data-testid='stExpander'] details summary p { color:var(--texto-claro) !important; font-weight:800 !important; }"
        "[data-testid='stSidebar'] [data-testid='stExpander'] { border:1px solid rgba(0,66,84,0.18) !important; background:rgba(0,66,84,0.04) !important; }"
        "[data-testid='stSidebar'] [data-testid='stExpander'] details summary p { color:var(--texto-sobre-claro) !important; font-weight:800 !important; }"
        ".stDataFrame, .stTable, [data-testid='stDataFrame'], [data-testid='stTable'] { background-color:var(--surface-soft) !important; color:var(--texto-claro) !important; border-radius:12px !important; }"
        "[data-testid='stDataFrame'] * { color:var(--texto-claro) !important; }"
        ".stMetric, [data-testid='stMetric'] { background:var(--surface-soft-2) !important; border:1px solid var(--border-soft) !important; border-radius:12px !important; padding:12px !important; }"
        "[data-testid='stMetric'] label, [data-testid='stMetric'] div { color:var(--texto-claro) !important; }"
        ".stAlert { background-color:var(--surface-soft) !important; color:var(--texto-claro) !important; border:1px solid var(--border-soft) !important; }"
        "hr { border-color:rgba(227,226,218,0.18) !important; }"
        "div[data-testid='column'] { color:var(--texto-claro) !important; }"
        "div[data-testid='stVerticalBlock'] div[style*='border'] { border-color:rgba(227,226,218,0.22) !important; }"
        "</style>"
    )
    st.markdown(css, unsafe_allow_html=True)

def style_dark_dataframe(df):
    return df.style.set_table_styles([{"selector": "thead th", "props": [("background-color", "#155D68"), ("color", "#E3E2DA"), ("font-weight", "800"), ("border", "1px solid rgba(227,226,218,0.18)")]}]).set_properties(**{"background-color": "#004254", "color": "#E3E2DA", "border": "1px solid rgba(227,226,218,0.16)", "font-weight": "600"})

def render_file_table(path):
    content = get_direct_content(path)
    if content.empty:
        st.caption("Sin contenido directo.")
        return
    table_df = content[["tipo", "codigo", "nivel", "nombre", "tamano", "ruta"]].copy()
    table_df = table_df.fillna("NOT AVAILABLE").astype(str)
    st.dataframe(style_dark_dataframe(table_df), width="stretch", hide_index=True)

def render_level_summary(df):
    if df.empty:
        return
    summary = df.groupby("level").agg(elementos=("code", "count"), carpetas=("dirs", "sum"), ficheros=("files", "sum")).reset_index()
    summary["nivel"] = summary["level"].apply(lambda value: f"Nivel {int(value)}")
    table_df = summary[["nivel", "elementos", "carpetas", "ficheros"]].copy()
    table_df = table_df.fillna("NOT AVAILABLE").astype(str)
    st.dataframe(style_dark_dataframe(table_df), width="stretch", hide_index=True)