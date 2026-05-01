# Orquestador principal de la aplicacion Streamlit. Carga el directorio raiz, gestiona la seleccion global y lanza las pestañas principales.

from pathlib import Path
import pandas as pd
import streamlit as st
from HW_scanner import add_missing_main_elements, get_main_element_row, get_sidebar_main_elements, scan_hw_folders
from HW_ui_common import inject_custom_theme, render_file_table
from modules.HW_PBS import render_hw_pbs
from modules.HW_LMs import render_lms
from modules.HW_BOM import render_bom
from modules.HW_material_status import render_material_status
from modules.HW_assembly_sequence import render_assembly_sequence


def set_selected_main_element(code):
    st.session_state["selected_hw_code"] = code

def render_global_hw_sidebar(df):
    st.sidebar.subheader("Estructura principal del simulador")
    main_elements = get_sidebar_main_elements(df)
    selected_code = st.session_state.get("selected_hw_code", "")
    for main in main_elements:
        main_row = get_main_element_row(df, main["code"])
        exists = bool(main_row.get("exists", False)) if main_row is not None else False
        label = f"{main['code']} - {main['component']}"
        if not exists:
            st.sidebar.caption(f"{label} · no encontrado")
            continue
        button_type = "primary" if selected_code == main["code"] else "secondary"
        st.sidebar.button(label, key=f"main_sidebar_{main['code']}", width="stretch", type=button_type, on_click=set_selected_main_element, args=(main["code"],))


def initialize_selected_hw_code(df):
    if "selected_hw_code" in st.session_state:
        current_code = st.session_state.get("selected_hw_code", "")
        current_row = get_main_element_row(df, current_code)
        if current_row is not None and bool(current_row.get("exists", False)):
            return
    first_existing = df[(df["level"] == 1) & (df["exists"] == True)].sort_values("code") if not df.empty else pd.DataFrame()
    if not first_existing.empty:
        st.session_state["selected_hw_code"] = first_existing.iloc[0]["code"]


def build_hw_dataframe(root_path, show_empty_folders):
    df = scan_hw_folders(root_path)
    df = add_missing_main_elements(df)
    if not show_empty_folders and not df.empty:
        df = df[(df["files"] > 0) | (df["level"] == 1)].copy()
    return df


def render_main_tabs(df, selected_code, max_hw_level, show_empty_folders, search_text):
    tab_pbs, tab_lms, tab_bom, tab_material_status, tab_sequence = st.tabs(["HW PBS", "LMs", "BOM", "Material Status", "Secuencia de Montaje"])
    with tab_pbs:
        render_hw_pbs(df, selected_code, max_hw_level, show_empty_folders, search_text)
    with tab_lms:
        render_lms(df, selected_code)
    with tab_bom:
        render_bom(df, selected_code)
    with tab_material_status:
        render_material_status(df, selected_code)
    with tab_sequence:
        render_assembly_sequence(df, selected_code)


def run_app():
    st.set_page_config(page_title="Estructura HW Simulador", layout="wide")
    inject_custom_theme()
    st.sidebar.header("Carga del directorio")
    saved_root = st.session_state.get("root_path", "")
    root_path_input = st.sidebar.text_input("Ruta del directorio raíz", value=saved_root, placeholder=r"C:\ruta\A320_FFS_SN06")
    load_clicked = st.sidebar.button("Cargar directorio")
    if load_clicked:
        st.session_state["root_path"] = root_path_input.strip()
    root_path = st.session_state.get("root_path", "").strip()
    if not root_path:
        st.title("Estructura HW")
        st.caption("Explorador visual de PBS por niveles A01, A0101, A010101, etc.")
        st.info("Pega la ruta del directorio raíz en el panel lateral y pulsa Cargar directorio.")
        return
    root = Path(root_path)
    folder_name = root.name if root.name else root_path
    st.title(f"Estructura HW {folder_name}")
    st.caption("Explorador visual de PBS por niveles A01, A0101, A010101, etc.")
    if not root.exists() or not root.is_dir():
        st.error("El directorio raíz no existe o no es una carpeta válida.")
        st.code(root_path)
        return
    max_hw_level = st.sidebar.slider("Nivel HW máximo", min_value=1, max_value=8, value=4)
    show_empty_folders = st.sidebar.checkbox("Mostrar carpetas vacías sin ficheros", value=True)
    search_text = st.sidebar.text_input("Buscar código, descripción o ruta", value="")
    if st.sidebar.button("Actualizar lectura"):
        st.cache_data.clear()
    df = build_hw_dataframe(root_path, show_empty_folders)
    if df.empty:
        st.warning("No se han encontrado carpetas con códigos tipo A01, A0101, A010101 con los filtros actuales.")
        render_file_table(root_path)
        return
    initialize_selected_hw_code(df)
    render_global_hw_sidebar(df)
    selected_code = st.session_state.get("selected_hw_code", "")
    render_main_tabs(df, selected_code, max_hw_level, show_empty_folders, search_text)