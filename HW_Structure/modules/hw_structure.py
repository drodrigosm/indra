# Modulo visual para mostrar la estructura HW del simulador, sus niveles, carpetas, ficheros y busqueda.

import pandas as pd
import streamlit as st
from hw_scanner import add_missing_main_elements, count_content, format_size, get_children_by_code, get_code_from_name, get_description_from_name, get_descendant_rows_by_code, get_direct_content, get_main_element_row, get_sidebar_main_elements, safe_iterdir, scan_hw_folders
from ui_common import render_file_table, render_level_summary


def set_selected_main_element(code):
    st.session_state["selected_hw_code"] = code


def render_hw_sidebar(df):
    st.sidebar.subheader("Estructura principal del simulador")
    main_elements = get_sidebar_main_elements(df)
    for main in main_elements:
        main_row = get_main_element_row(df, main["code"])
        exists = bool(main_row.get("exists", False)) if main_row is not None else False
        label = f"{main['code']} - {main['component']}"
        selected_mark = " ✅" if st.session_state.get("selected_hw_code", "") == main["code"] else ""
        if not exists:
            st.sidebar.caption(f"{label} · no encontrado")
            continue
        if st.sidebar.button(f"{label}{selected_mark}", key=f"main_sidebar_{main['code']}", use_container_width=True):
            set_selected_main_element(main["code"])

def render_logical_tree_node(df, row, depth, max_depth):
    code = row.get("code", "")
    component = row.get("component", "")
    dirs = int(row.get("dirs", 0))
    files = int(row.get("files", 0))
    children = get_children_by_code(df, code)
    label = f"{code} - {component} ({dirs} carpetas, {files} ficheros)"
    if children.empty or depth >= max_depth:
        st.markdown(f"{'&nbsp;' * depth * 6}• {label}", unsafe_allow_html=True)
        return
    with st.expander(label, expanded=depth < 1):
        for _, child in children.iterrows():
            render_logical_tree_node(df, child, depth + 1, max_depth)


def render_hw_tree_expandable(df, root_code, max_depth):
    if df.empty or not root_code:
        st.info("No hay subelementos detectados para este elemento.")
        return
    root_rows = df[df["code"] == root_code].copy()
    if root_rows.empty:
        st.info("No hay subelementos detectados para este elemento.")
        return
    root_row = root_rows.iloc[0]
    render_logical_tree_node(df, root_row, 0, max_depth)


def render_tree(path, max_depth, show_empty_folders, current_depth=0):
    if current_depth > max_depth:
        return
    items = safe_iterdir(path)
    folders = [item for item in items if item.is_dir()]
    files = [item for item in items if item.is_file()]
    for folder in folders:
        code = get_code_from_name(folder.name)
        description = get_description_from_name(folder.name)
        direct_content = get_direct_content(folder)
        direct_dirs = int((direct_content["tipo"] == "Carpeta").sum()) if not direct_content.empty else 0
        direct_files = int((direct_content["tipo"] == "Fichero").sum()) if not direct_content.empty else 0
        total_dirs, total_files = count_content(folder)
        if not show_empty_folders and total_files == 0:
            continue
        label_code = code if code else "SIN CODIGO"
        label = f"{label_code} · {description} · {direct_dirs} carpetas · {direct_files} ficheros directos · {total_files} ficheros total"
        with st.expander(label, expanded=current_depth < 1):
            st.caption(str(folder))
            render_file_table(folder)
            render_tree(folder, max_depth, show_empty_folders, current_depth + 1)
    if files:
        file_rows = []
        for file in files:
            file_rows.append({"fichero": file.name, "tamano": format_size(file.stat().st_size), "ruta": str(file)})
        st.dataframe(pd.DataFrame(file_rows), use_container_width=True, hide_index=True)


def render_search_results(df, search_text):
    if not search_text:
        st.info("Introduce un texto en el buscador del sidebar para buscar por código, descripción, nombre o ruta.")
        return
    query = search_text.strip().lower()
    filtered = df[df["code"].str.lower().str.contains(query, na=False) | df["description"].str.lower().str.contains(query, na=False) | df["component"].str.lower().str.contains(query, na=False) | df["name"].str.lower().str.contains(query, na=False) | df["path"].str.lower().str.contains(query, na=False)].copy()
    st.subheader("Resultados de búsqueda")
    st.caption(f"{len(filtered)} elementos encontrados")
    if filtered.empty:
        st.warning("No se han encontrado elementos con ese texto.")
        return
    st.dataframe(filtered[["code", "level", "component", "sica", "dirs", "files", "path"]], use_container_width=True, hide_index=True)


def build_component_list_text(selected_df, selected_code):
    if selected_df.empty:
        return ""
    components = selected_df[selected_df["code"] != selected_code].copy()
    if components.empty:
        return ""
    values = []
    for _, row in components.sort_values(["level", "code", "component"]).iterrows():
        values.append(f"{row.get('code', '')} - {row.get('component', '')}")
    return " | ".join(values)

def build_node_options(selected_df):
    if selected_df.empty:
        return []
    options = []
    for _, row in selected_df.sort_values(["level", "code", "component", "path"]).iterrows():
        code = row.get("code", "")
        component = row.get("component", "")
        level = int(row.get("level", 0)) if str(row.get("level", "")).strip() != "" else 0
        path = row.get("path", "")
        files = int(row.get("files", 0))
        dirs = int(row.get("dirs", 0))
        indent = "    " * max(level - 1, 0)
        label = f"{indent}{code} - {component} ({dirs} carpetas, {files} ficheros)"
        options.append({"label": label, "code": code, "component": component, "level": level, "path": path, "dirs": dirs, "files": files})
    return options

def render_node_content(node):
    if not node:
        st.info("Selecciona un nodo para ver su contenido.")
        return
    path = node.get("path", "")
    if not path:
        st.warning("El nodo seleccionado no tiene ruta física asociada.")
        return
    st.subheader(f"Contenido de {node.get('code', '')} - {node.get('component', '')}")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("REF. HW", node.get("code", ""))
    col2.metric("Nivel", node.get("level", ""))
    col3.metric("Carpetas", node.get("dirs", 0))
    col4.metric("Ficheros", node.get("files", 0))
    st.caption(path)
    content = get_direct_content(path)
    if content.empty:
        st.info("Esta carpeta no contiene elementos directos.")
        return
    folders_df = content[content["tipo"] == "Carpeta"].copy()
    files_df = content[content["tipo"] == "Fichero"].copy()
    tab_all, tab_folders, tab_files = st.tabs(["Contenido directo", "Carpetas", "Ficheros"])
    with tab_all:
        st.dataframe(content[["tipo", "codigo", "nivel", "nombre", "tamano", "ruta"]], use_container_width=True, hide_index=True)
    with tab_folders:
        if folders_df.empty:
            st.info("No hay carpetas directas.")
        else:
            st.dataframe(folders_df[["tipo", "codigo", "nivel", "nombre", "ruta"]], use_container_width=True, hide_index=True)
    with tab_files:
        if files_df.empty:
            st.info("No hay ficheros directos.")
        else:
            st.dataframe(files_df[["nombre", "tamano", "ruta"]], use_container_width=True, hide_index=True)

def render_selected_element(df, selected_code, max_depth, show_empty_folders):
    selected_row = get_main_element_row(df, selected_code)
    if selected_row is None:
        st.warning("No se ha encontrado el elemento seleccionado.")
        return
    code = selected_row["code"]
    component = selected_row.get("component", selected_row.get("description", ""))
    sica = selected_row.get("sica", "")
    path = selected_row.get("path", "")
    exists = bool(selected_row.get("exists", True))
    st.subheader(f"{code} - {component}")
    if not exists:
        st.warning("Este elemento principal existe en la estructura de referencia, pero no se ha encontrado en el directorio cargado.")
        if sica:
            st.metric("CODIGO SICA", sica)
        return
    selected_df = get_descendant_rows_by_code(df, code)
    if not show_empty_folders and not selected_df.empty:
        selected_df = selected_df[selected_df["files"] > 0].copy()
    total_dirs = int(selected_row.get("dirs", 0))
    total_files = int(selected_row.get("files", 0))
    composed_count = max(len(selected_df) - 1, 0)
    component_list = build_component_list_text(selected_df, code)
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("REF. HW", code)
    col2.metric("CODIGO SICA", sica if sica else "No informado")
    col3.metric("Carpetas", total_dirs)
    col4.metric("Ficheros", total_files)
    col5.metric("Elementos", composed_count)
    details = pd.DataFrame([{"REF. HW": code, "COMPONENTE": component, "CODIGO SICA": sica, "Nivel": selected_row.get("level", ""), "Ruta": path, "Carpetas": total_dirs, "Ficheros": total_files, "Elementos que lo componen": component_list}])
    st.dataframe(details, use_container_width=True, hide_index=True)
    tab_tree, tab_elements, tab_visual, tab_levels, tab_content = st.tabs(["Árbol lógico", "Elementos que lo componen", "Explorador visual", "Resumen niveles", "Contenido directo"])
    with tab_tree:
        st.caption("Árbol lógico construido por código HW, no por estructura física de carpetas.")
        tree_depth = st.slider("Profundidad del árbol lógico", min_value=1, max_value=10, value=6, key=f"logical_tree_depth_{code}")
        render_hw_tree_expandable(selected_df, code, tree_depth)
        st.divider()
        st.subheader("Inspeccionar nodo del árbol")
        node_options = build_node_options(selected_df)
        if not node_options:
            st.info("No hay nodos disponibles para inspeccionar.")
        else:
            labels = [item["label"] for item in node_options]
            selected_label = st.selectbox("Selecciona un nodo para ver su carpeta y ficheros", options=labels, key=f"node_selector_{code}")
            selected_node = next(item for item in node_options if item["label"] == selected_label)
            render_node_content(selected_node)
    with tab_elements:
        st.subheader("Elementos que lo componen")
        table_df = selected_df[selected_df["code"] != code].copy()
        if table_df.empty:
            st.info("Este elemento no tiene subelementos detectados.")
        else:
            st.dataframe(table_df[["code", "parent_code", "level", "component", "sica", "dirs", "files", "path"]], use_container_width=True, hide_index=True)
    with tab_visual:
        st.caption(path)
        render_tree(path, max_depth, show_empty_folders)
    with tab_levels:
        render_level_summary(selected_df)
    with tab_content:
        render_file_table(path)


def render_hw_structure(root_path, max_depth, show_empty_folders, search_text):
    df = scan_hw_folders(root_path)
    df = add_missing_main_elements(df)
    if not show_empty_folders and not df.empty:
        df = df[(df["files"] > 0) | (df["level"] == 1)].copy()
    if df.empty:
        st.warning("No se han encontrado carpetas con códigos tipo A01, A0101, A010101 con los filtros actuales.")
        render_file_table(root_path)
        return
    if "selected_hw_code" not in st.session_state:
        first_existing = df[(df["level"] == 1) & (df["exists"] == True)].sort_values("code")
        if not first_existing.empty:
            st.session_state["selected_hw_code"] = first_existing.iloc[0]["code"]
    render_hw_sidebar(df)
    selected_code = st.session_state.get("selected_hw_code", "")
    tab_selected, tab_search = st.tabs(["Elemento seleccionado", "Búsqueda"])
    with tab_selected:
        render_selected_element(df, selected_code, max_depth, show_empty_folders)
    with tab_search:
        render_search_results(df, search_text)