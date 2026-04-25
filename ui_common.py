# Este fichero centraliza la configuración visual, estilos, branding y componentes UI reutilizables de la aplicación.
import streamlit as st


PALETTE = {
    'azul_oscuro': '#001923',
    'turquesa': '#00B0BD',
    'gris_ceramica': '#E3E2DA',
    'azul_amazonico': '#004254',
    'texto_claro': '#E3E2DA',
    'texto_oscuro': '#001923'
}

PLOTLY_COLOR_SEQUENCE = ['#00B0BD', '#33C2CD', '#66D0D6', '#0097A7', '#26AAB5', '#4DBCC4', '#7BCFD4', '#5E7F8A', '#6F909A', '#80A1AA', '#91B2BA', '#A3C2C9', '#8FA3AA', '#9FB2B8', '#AFC1C6', '#BFCFD3', '#C9D4D6', '#B8C5C8', '#A7B6BA', '#96A8AD']

DISPLAY_COLUMNS = {
    'departamento': 'Departamento',
    'empleado': 'Empleado',
    'elemento': 'Elemento',
    'nombre': 'Nombre',
    'fecha': 'Periodo',
    'periodo': 'Periodo',
    'horas_aplicadas': 'Horas Aplicadas',
    'cantidad': 'Cantidad',
    'tasa': 'Tasa',
    'categoria_nombre': 'Categoría',
    'tipo_coste_nombre': 'Tipo de Coste'
}


def format_number(value: float, decimals: int = 2) -> str:
    return f"{value:,.{decimals}f}".replace(',', 'X').replace('.', ',').replace('X', '.')


def build_metric_card(title: str, value: str) -> None:
    st.markdown(f"<div style='padding:16px;border:1px solid rgba(227,226,218,0.22);border-radius:12px;background:rgba(227,226,218,0.08);box-shadow:none;'><div style='font-size:0.9rem;color:#E3E2DA;'>{title}</div><div style='font-size:1.6rem;font-weight:700;margin-top:6px;color:#00B0BD;'>{value}</div></div>", unsafe_allow_html=True)


def inject_custom_theme() -> None:
    css = (
        "<style>"
        ":root {"
        "--azul-oscuro: #001923;"
        "--turquesa: #00B0BD;"
        "--gris-ceramica: #E3E2DA;"
        "--azul-amazonico: #004254;"
        "--texto-claro: #E3E2DA;"
        "--texto-sobre-claro: #004254;"
        "--border-soft: rgba(227, 226, 218, 0.22);"
        "--surface-soft: rgba(227, 226, 218, 0.06);"
        "--surface-soft-2: rgba(227, 226, 218, 0.10);"
        "}"
        "html, body, [data-testid='stAppViewContainer'], .stApp, .main, .block-container { background-color: var(--azul-amazonico) !important; color: var(--texto-claro) !important; }"
        "[data-testid='stHeader'] { background: var(--azul-amazonico) !important; }"
        "[data-testid='stSidebar'] { background-color: var(--gris-ceramica) !important; border-right: 1px solid rgba(0, 66, 84, 0.12) !important; }"
        ".stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6, .stApp p, .stApp span, .stApp label, .stApp div, .stApp li { color: var(--texto-claro) !important; }"
        ".stMarkdown, .stCaption, .stText { color: var(--texto-claro) !important; }"
        "[data-testid='stSidebar'], [data-testid='stSidebar'] *, [data-testid='stSidebar'] label, [data-testid='stSidebar'] span, [data-testid='stSidebar'] div, [data-testid='stSidebar'] p, [data-testid='stSidebar'] small, [data-testid='stSidebar'] strong, [data-testid='stSidebar'] button { color: var(--texto-sobre-claro) !important; }"
        "[data-testid='stSidebar'] button[kind], [data-testid='stSidebar'] [role='button'], [data-testid='stSidebar'] [data-baseweb='button'], [data-testid='stSidebar'] [data-baseweb='tag'], [data-testid='stSidebar'] [data-baseweb='tag'] *, [data-testid='stSidebar'] [data-baseweb='select'] *, [data-testid='stSidebar'] [data-baseweb='popover'] *, [data-testid='stSidebar'] [data-baseweb='input'] *, [data-testid='stSidebar'] .stCheckbox *, [data-testid='stSidebar'] .stRadio *, [data-testid='stSidebar'] .stMultiSelect *, [data-testid='stSidebar'] .stSelectbox * { color: var(--texto-sobre-claro) !important; fill: var(--texto-sobre-claro) !important; -webkit-text-fill-color: var(--texto-sobre-claro) !important; }"
        "[data-testid='stSidebar'] div[data-baseweb='select'] > div, [data-testid='stSidebar'] div[data-baseweb='base-input'] > div, [data-testid='stSidebar'] .stTextInput input, [data-testid='stSidebar'] .stNumberInput input, [data-testid='stSidebar'] .stDateInput input, [data-testid='stSidebar'] .stTextArea textarea { background-color: #FFFFFF !important; color: var(--texto-sobre-claro) !important; border: 1px solid rgba(0, 66, 84, 0.25) !important; border-radius: 10px !important; }"
        "[data-testid='stSidebar'] input, [data-testid='stSidebar'] textarea, [data-testid='stSidebar'] [data-baseweb='input'] input, [data-testid='stSidebar'] [data-baseweb='select'] input { color: var(--texto-sobre-claro) !important; -webkit-text-fill-color: var(--texto-sobre-claro) !important; }"
        "[data-testid='stSidebar'] ::placeholder { color: rgba(0, 66, 84, 0.65) !important; opacity: 1 !important; }"
        ".stFileUploader, [data-testid='stFileUploader'] { background-color: var(--surface-soft) !important; border: 1px solid var(--border-soft) !important; border-radius: 12px !important; }"
        "[data-testid='stFileUploader'] * { color: var(--texto-claro) !important; }"
        ".stTabs [data-baseweb='tab'] { color: var(--gris-ceramica) !important; background-color: transparent !important; }"
        ".stTabs [aria-selected='true'] { color: var(--turquesa) !important; border-bottom: 2px solid var(--turquesa) !important; }"
        ".stButton button, .stDownloadButton button { background-color: var(--turquesa) !important; color: var(--texto-claro) !important; border: 1px solid var(--turquesa) !important; border-radius: 8px !important; font-weight: 600 !important; }"
        ".stButton button:hover, .stDownloadButton button:hover { background-color: var(--azul-oscuro) !important; color: var(--texto-claro) !important; border: 1px solid var(--azul-oscuro) !important; }"
        "[data-testid='stMetric'] { background: var(--surface-soft-2) !important; border: 1px solid var(--border-soft) !important; border-radius: 12px !important; padding: 8px !important; }"
        "[data-testid='stMetric'] label, [data-testid='stMetric'] div { color: var(--texto-claro) !important; }"
        ".stDataFrame, .stTable, [data-testid='stDataFrame'], [data-testid='stTable'] { background-color: var(--surface-soft) !important; color: var(--texto-claro) !important; }"
        "[data-testid='stDataFrame'] * { color: var(--texto-claro) !important; }"
        ".stAlert { background-color: var(--surface-soft) !important; color: var(--texto-claro) !important; border: 1px solid var(--border-soft) !important; }"
        "hr { border-color: rgba(227, 226, 218, 0.18) !important; }"
        "[data-testid='stFileUploader'] { padding: 8px !important; margin-bottom: 8px !important; }"
        "[data-testid='stFileUploaderDropzone'] { min-height: 42px !important; padding: 6px 10px !important; }"
        "[data-testid='stFileUploaderDropzone'] div { font-size: 0.78rem !important; }"
        "[data-testid='stFileUploaderDropzone'] small { display: none !important; }"
        "[data-testid='stFileUploaderFile'] { padding: 4px 8px !important; margin-top: 4px !important; }"
        "[data-testid='stFileUploaderFile'] div { font-size: 0.78rem !important; }"
        "[data-testid='stSidebar'] { background-color: #F4F5F2 !important; }"
        ".indra-sidebar-section-title { margin-top: 28px; margin-bottom: 14px; font-size: 0.74rem; font-weight: 800; letter-spacing: 0.04em; color: #5E737A !important; text-transform: uppercase; }"
        "[data-testid='stSidebar'] details { border: 0 !important; background: transparent !important; box-shadow: none !important; margin-bottom: 8px !important; }"
        "[data-testid='stSidebar'] details summary { min-height: 42px !important; padding: 8px 2px !important; border-radius: 10px !important; color: #5E737A !important; font-weight: 700 !important; }"
        "[data-testid='stSidebar'] details summary:hover { background: rgba(0,176,189,0.08) !important; }"
        "[data-testid='stSidebar'] details summary p { color: #5E737A !important; font-weight: 700 !important; }"
        "[data-testid='stSidebar'] details[open] summary { color: #004254 !important; }"
        "[data-testid='stSidebar'] details[open] summary p { color: #004254 !important; }"
        "[data-testid='stSidebar'] .stButton button[kind='secondary'] { min-height: 46px !important; background-color: #E9ECE8 !important; color: #004254 !important; border: 0 !important; border-radius: 10px !important; font-weight: 800 !important; }"
        ".indra-sidebar-reset-text { margin-top: -8px; padding: 0 0 8px 16px; color: #0097A7 !important; font-size: 0.86rem; font-weight: 700; }"
                "</style>"
    )
    st.markdown(css, unsafe_allow_html=True)


def get_indra_logo_svg(color: str) -> str:
    return (
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 760 180' preserveAspectRatio='xMidYMid meet' aria-label='INDRA logo' style='display:block;width:100%;height:auto;overflow:visible;'>"
        f"<g fill='{color}'>"
        "<path d='M40 50c24 0 36 9 52 16 8 4 16 6 24 6 8 0 16-2 24-6 16-7 28-16 52-16-13 10-24 18-35 25-15 9-27 14-41 14s-26-5-41-14c-11-7-22-15-35-25Z'/>"
        "<path d='M40 130c24 0 36-9 52-16 8-4 16-6 24-6 8 0 16 2 24 6 16 7 28 16 52 16-13-10-24-18-35-25-15-9-27-14-41-14s-26 5-41 14c-11 7-22 15-35 25Z'/>"
        "<path d='M196 44h23v92h-23V44Z'/>"
        "<path d='M245 44h26l63 59V44h23v92h-24l-65-62v62h-23V44Z'/>"
        "<path d='M391 44h50c34 0 55 18 55 46s-21 46-55 46h-50V44Zm23 20v52h26c21 0 33-10 33-26s-12-26-33-26h-26Z'/>"
        "<path d='M521 44h67c29 0 43 12 43 33 0 15-9 25-22 30l26 29h-29l-21-24h-41v24h-23V44Zm23 19v31h41c16 0 24-5 24-15s-8-16-24-16h-41Z'/>"
        "<path d='M657 136h25l11-20h40l11 20h26l-48-92h-18l-47 92Zm40-39 16-31 16 31h-32Z'/>"
        "</g>"
        "</svg>"
    )


def render_indra_branding() -> None:
    sidebar_logo = get_indra_logo_svg('#004254')
    main_logo = get_indra_logo_svg('#E3E2DA')
    st.sidebar.markdown(f"<div style='display:flex;justify-content:center;align-items:center;width:100%;padding:14px 10px 20px 10px;box-sizing:border-box;'><div style='width:75%;max-width:240px;line-height:0;'>{sidebar_logo}</div></div>", unsafe_allow_html=True)
    st.markdown(f"<div style='display:flex;justify-content:center;align-items:center;width:100%;padding:8px 0 18px 0;box-sizing:border-box;'><div style='width:75%;max-width:360px;line-height:0;'>{main_logo}</div></div>", unsafe_allow_html=True)
