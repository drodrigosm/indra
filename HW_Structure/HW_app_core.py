# Orquestador principal de la aplicacion Streamlit. Carga el directorio raiz, gestiona la seleccion global y lanza las pestañas principales.

from pathlib import Path
import pandas as pd
import streamlit as st
from HW_scanner import add_missing_main_elements, get_children_by_code, get_main_element_row, get_main_hw_elements, get_parent_code, get_sidebar_main_elements, scan_hw_folders
from HW_ui_common import inject_custom_theme, render_file_table
from modules.HW_PBS import render_hw_pbs
from modules.HW_LMs import build_lm_file_signature, build_lm_global_file_index, build_lm_hw_path_signature, get_all_lm_files_from_index, preload_lm_material_files, render_lms
from modules.HW_BOM import render_bom
from modules.HW_material_status import render_material_status
from modules.HW_assembly_sequence import render_assembly_sequence


def set_selected_hw_element(code):
    st.session_state["selected_hw_code"] = code
    st.session_state["sidebar_focus_code"] = code


def set_sidebar_home():
    st.session_state["selected_hw_code"] = "A00"
    st.session_state["sidebar_focus_code"] = "A00"


def get_sidebar_row_label(row):
    code = str(row.get("code", "")).strip()
    component = str(row.get("component", row.get("description", ""))).strip()
    return f"{code} - {component}" if component else code


def get_unique_sidebar_rows(rows_df):
    if rows_df is None or rows_df.empty:
        return pd.DataFrame()
    result = rows_df.copy()
    result["path_len"] = result["path"].fillna("").astype(str).str.len() if "path" in result.columns else 0
    result = result.sort_values(["level", "code", "path_len", "component"]).drop_duplicates(subset=["code"], keep="first")
    return result.drop(columns=["path_len"], errors="ignore").reset_index(drop=True)



def filter_configured_main_structure(df):
    if df is None or df.empty:
        return df
    configured_codes = set([str(item.get("code", "")).strip().upper() for item in get_main_hw_elements() if str(item.get("code", "")).strip()])
    configured_codes.add("A00")
    result = df.copy()
    result["main_code"] = result["main_code"].astype(str).str.upper()
    result["code"] = result["code"].astype(str).str.upper()
    return result[(result["main_code"].isin(configured_codes)) | (result["code"] == "A00")].copy().reset_index(drop=True)

def get_a00_sidebar_children(df):
    if df is None or df.empty:
        return pd.DataFrame()
    rows = []
    for item in get_sidebar_main_elements(df):
        code = str(item.get("code", "")).strip().upper()
        if not code or code == "A00" or not bool(item.get("exists", False)):
            continue
        row = get_main_element_row(df, code)
        if row is not None:
            rows.append(row.to_dict())
    return get_unique_sidebar_rows(pd.DataFrame(rows)) if rows else pd.DataFrame()

def render_sidebar_node_button(row, selected_code, key_prefix):
    code = str(row.get("code", "")).strip()
    if not code:
        return
    label = get_sidebar_row_label(row)
    button_type = "primary" if selected_code == code else "secondary"
    st.sidebar.button(label, key=f"{key_prefix}_{code}", width="stretch", type=button_type, on_click=set_selected_hw_element, args=(code,))


def render_hierarchical_hw_sidebar(df):
    st.sidebar.subheader("Estructura HW")
    selected_code = st.session_state.get("selected_hw_code", "A00")
    focus_code = st.session_state.get("sidebar_focus_code", "")
    if not focus_code:
        a00_row = get_main_element_row(df, "A00")
        if a00_row is None:
            st.sidebar.warning("No se ha encontrado el nodo A00.")
            return
        render_sidebar_node_button(a00_row, selected_code, "sidebar_root")
        return
    current_row = get_main_element_row(df, focus_code)
    if current_row is None:
        st.sidebar.warning("No se ha encontrado el nodo seleccionado.")
        return
    if focus_code != "A00":
        parent_code = get_parent_code(focus_code)
        target_parent = parent_code if parent_code else "A00"
        parent_label = "Subir a A00" if target_parent == "A00" else f"Subir a {target_parent}"
        st.sidebar.button(parent_label, key=f"sidebar_up_{focus_code}", width="stretch", on_click=set_selected_hw_element, args=(target_parent,))
    else:
        st.sidebar.button("Volver al inicio", key="sidebar_back_home", width="stretch", on_click=set_sidebar_home)
    st.sidebar.caption("Elemento activo")
    render_sidebar_node_button(current_row, selected_code, "sidebar_current")
    children = get_a00_sidebar_children(df) if focus_code == "A00" else get_unique_sidebar_rows(get_children_by_code(df, focus_code))
    if children.empty:
        st.sidebar.caption("Este elemento no tiene subniveles detectados.")
        return
    st.sidebar.caption("Subniveles")
    for _, child in children.iterrows():
        render_sidebar_node_button(child, selected_code, f"sidebar_child_{focus_code}")


def initialize_selected_hw_code(df):
    if "selected_hw_code" in st.session_state:
        current_code = st.session_state.get("selected_hw_code", "")
        current_row = get_main_element_row(df, current_code)
        if current_row is not None and bool(current_row.get("exists", False)):
            if "sidebar_focus_code" not in st.session_state or not st.session_state.get("sidebar_focus_code", ""):
                st.session_state["sidebar_focus_code"] = current_code if current_code else "A00"
            return
    a00_row = get_main_element_row(df, "A00")
    if a00_row is not None:
        st.session_state["selected_hw_code"] = "A00"
        st.session_state["sidebar_focus_code"] = "A00"
        return
    first_existing = df[(df["level"] == 1) & (df["exists"] == True)].sort_values("code") if not df.empty else pd.DataFrame()
    if not first_existing.empty:
        st.session_state["selected_hw_code"] = first_existing.iloc[0]["code"]
        st.session_state["sidebar_focus_code"] = first_existing.iloc[0]["code"]


def ensure_logical_a00_element(df, root_path):
    root_path_text = str(root_path)
    if df.empty:
        return df
    a00_mask = df["code"].astype(str).str.upper() == "A00"
    level_1_df = df[(df["level"] == 1) & (df["code"] != "A00") & (df["exists"] == True)].copy()
    total_dirs = int(level_1_df["dirs"].sum()) if not level_1_df.empty else 0
    total_files = int(level_1_df["files"].sum()) if not level_1_df.empty else 0
    if a00_mask.any():
        df.loc[a00_mask, "name"] = "SIM"
        df.loc[a00_mask, "description"] = "SIM"
        df.loc[a00_mask, "component"] = "SIM"
        df.loc[a00_mask, "path"] = root_path_text
        df.loc[a00_mask, "parent_code"] = ""
        df.loc[a00_mask, "main_code"] = "A00"
        df.loc[a00_mask, "dirs"] = total_dirs
        df.loc[a00_mask, "files"] = total_files
        df.loc[a00_mask, "exists"] = True
        return df
    a00_row = pd.DataFrame([{"code": "A00", "level": 1, "name": "SIM", "description": "SIM", "component": "SIM", "sica": "", "path": root_path_text, "parent_code": "", "main_code": "A00", "dirs": total_dirs, "files": total_files, "exists": True}])
    return pd.concat([df, a00_row], ignore_index=True).sort_values(["main_code", "level", "code", "path"]).reset_index(drop=True)


@st.cache_data(show_spinner=False)
def build_hw_dataframe_cached(root_path):
    df = scan_hw_folders(root_path)
    df = filter_configured_main_structure(df)
    df = add_missing_main_elements(df)
    df = ensure_logical_a00_element(df, root_path)
    return df


def build_hw_dataframe(root_path, show_empty_folders):
    df = build_hw_dataframe_cached(root_path)
    if not show_empty_folders and not df.empty:
        df = df[(df["files"] > 0) | (df["level"] == 1) | (df["code"] == "A00")].copy()
    return df.copy() if df is not None else pd.DataFrame()




def preload_project_data(root_path, force_reload=False):
    loaded_root_path = st.session_state.get("loaded_root_path", "")
    if not force_reload and loaded_root_path == root_path and "lm_global_file_index" in st.session_state:
        return
    progress_bar = st.progress(0)
    status_box = st.empty()
    status_box.info("Iniciando carga del directorio HW...")
    progress_bar.progress(5)
    status_box.info("Escaneando estructura HW/PBS...")
    df = build_hw_dataframe_cached(root_path)
    progress_bar.progress(35)
    status_box.info("Preparando rutas HW para búsqueda de LMs...")
    hw_path_signature = build_lm_hw_path_signature(df)
    progress_bar.progress(45)
    status_box.info("Indexando ficheros LM del directorio cargado...")
    lm_file_index = build_lm_global_file_index(df, root_path)
    st.session_state["lm_global_file_index"] = lm_file_index
    progress_bar.progress(65)
    all_lm_files = get_all_lm_files_from_index(lm_file_index)
    lm_file_signature = build_lm_file_signature(all_lm_files)
    st.session_state["lm_global_file_count"] = len(lm_file_signature)
    preload_metrics = preload_lm_material_files(lm_file_signature, progress_bar, status_box, 65, 98)
    st.session_state["lm_preload_metrics"] = preload_metrics
    st.session_state["loaded_root_path"] = root_path
    progress_bar.progress(100)
    status_box.success(f"Carga completada. PBS preparado y {preload_metrics.get('loaded_lm_files', 0)}/{preload_metrics.get('total_lm_files', 0)} LMs precargadas.")

def render_main_tabs(df, selected_code, max_hw_level, show_empty_folders, search_text):
    tab_names = ["HW PBS", "LMs", "BOM", "Material Status", "Secuencia de Montaje"]
    active_tab = st.radio("Pestaña principal", options=tab_names, horizontal=True, label_visibility="collapsed", key="main_active_tab")
    if active_tab == "HW PBS":
        render_hw_pbs(df, selected_code, max_hw_level, show_empty_folders, search_text)
    elif active_tab == "LMs":
        render_lms(df, selected_code)
    elif active_tab == "BOM":
        render_bom(df, selected_code)
    elif active_tab == "Material Status":
        render_material_status(df, selected_code)
    elif active_tab == "Secuencia de Montaje":
        render_assembly_sequence(df, selected_code)


def run_app():
    st.set_page_config(page_title="Estructura HW Simulador", layout="wide")
    inject_custom_theme()
    st.sidebar.header("Carga del directorio")
    saved_root = st.session_state.get("root_path", "")
    root_path_input = st.sidebar.text_input("Ruta del directorio raíz", value=saved_root, placeholder=r"C:\ruta\A320_FFS_SN06")
    load_clicked = st.sidebar.button("Cargar directorio")
    if load_clicked:
        st.cache_data.clear()
        st.session_state["root_path"] = root_path_input.strip()
        st.session_state["selected_hw_code"] = "A00"
        st.session_state["sidebar_focus_code"] = "A00"
        st.session_state.pop("loaded_root_path", None)
        st.session_state.pop("lm_global_file_index", None)
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
    force_reload = False
    if st.sidebar.button("Actualizar lectura"):
        st.cache_data.clear()
        st.session_state.pop("loaded_root_path", None)
        st.session_state.pop("lm_global_file_index", None)
        force_reload = True
    preload_project_data(root_path, force_reload)
    df = build_hw_dataframe(root_path, show_empty_folders)
    if df.empty:
        st.warning("No se han encontrado carpetas con códigos tipo A01, A0101, A010101 con los filtros actuales.")
        render_file_table(root_path)
        return
    initialize_selected_hw_code(df)
    render_hierarchical_hw_sidebar(df)
    selected_code = st.session_state.get("selected_hw_code", "A00")
    render_main_tabs(df, selected_code, max_hw_level, show_empty_folders, search_text)
