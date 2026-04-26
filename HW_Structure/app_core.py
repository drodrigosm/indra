# Orquestador principal de la aplicacion Streamlit para cargar el directorio raiz y lanzar los modulos visuales.

from pathlib import Path
import streamlit as st
from modules.hw_structure import render_hw_structure


def run_app():
    st.set_page_config(page_title="Estructura HW Simulador", layout="wide")
    st.title("Estructura HW del Simulador de Vuelo")
    st.caption("Explorador visual de carpetas por niveles A01, A0101, A010101, etc.")
    st.sidebar.header("Carga del directorio")
    saved_root = st.session_state.get("root_path", "")
    root_path_input = st.sidebar.text_input("Ruta del directorio raíz", value=saved_root, placeholder=r"C:\ruta\A320_FFS_SN06")
    load_clicked = st.sidebar.button("Cargar directorio")
    if load_clicked:
        st.session_state["root_path"] = root_path_input.strip()
    root_path = st.session_state.get("root_path", "").strip()
    if not root_path:
        st.info("Pega la ruta del directorio raíz en el panel lateral y pulsa Cargar directorio.")
        return
    root = Path(root_path)
    if not root.exists() or not root.is_dir():
        st.error("El directorio raíz no existe o no es una carpeta válida.")
        st.code(root_path)
        return
    max_depth = st.sidebar.slider("Profundidad visual", min_value=1, max_value=8, value=4)
    show_empty_folders = st.sidebar.checkbox("Mostrar carpetas vacías sin ficheros", value=True)
    search_text = st.sidebar.text_input("Buscar código, descripción o ruta", value="")
    if st.sidebar.button("Actualizar lectura"):
        st.cache_data.clear()
    render_hw_structure(root_path, max_depth, show_empty_folders, search_text)