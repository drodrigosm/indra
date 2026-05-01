# Modulo principal LMs. Carga y muestra las Listas de Materiales asociadas al elemento HW seleccionado en el sidebar global.

from pathlib import Path
import re
import pandas as pd
import streamlit as st
from HW_scanner import get_descendant_rows_by_code, get_main_element_row
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode

LM_FILE_PATTERN = re.compile(r"^(?P<lm_code>.+LM\d{2})_A(?P<revision>\d+)\.(xlsx|xlsm|xls)$", re.IGNORECASE)
LM_COLUMNS = ["CODIGO MATERIAL", "CANTIDAD", "REF.TOP.", "UNIDAD", "PROBABILIDAD", "DESCRIPCION", "P/N", "MNF", "ELEC/MEC", "CHECK BOM"]
LM_NORMALIZED_COLUMNS = {"CODIGO MATERIAL": "CODIGO MATERIAL", "CODIGO_MATERIAL": "CODIGO MATERIAL", "CANTIDAD": "CANTIDAD", "REF.TOP.": "REF.TOP.", "REF. TOP.": "REF.TOP.", "REF TOP": "REF.TOP.", "REF_TOP": "REF.TOP.", "UNIDAD": "UNIDAD", "PROBABILIDAD": "PROBABILIDAD", "BORRAR": "DESCRIPCION", "P/N": "P/N", "PN": "P/N", "P.N": "P/N", "P/N MANUFACTURER": "P/N", "PN MANUFACTURER": "P/N", "DESCRIPCION": "DESCRIPCION", "DESCRIPCIÓN": "DESCRIPCION", "Descripcion": "DESCRIPCION", "MNF": "MNF", "MANUFACTURER": "MNF", "FABRICANTE": "MNF", "ELEC/MEC": "ELEC/MEC", "ELEC MEC": "ELEC/MEC", "ELEC_MEC": "ELEC/MEC", "CHECK BOM": "CHECK BOM", "CHECK_BOM": "CHECK BOM"}

def normalize_lm_header(value):
    if value is None:
        return ""
    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)
    return LM_NORMALIZED_COLUMNS.get(text, LM_NORMALIZED_COLUMNS.get(text.upper(), text))

def get_lm_file_info(path):
    match = LM_FILE_PATTERN.match(path.name)
    if not match:
        return None
    return {"path": path, "lm_code": match.group("lm_code").upper(), "revision": int(match.group("revision")), "revision_label": f"A{int(match.group('revision'))}"}

@st.cache_data(show_spinner=False)
def find_latest_lm_files(paths, root_path=None):
    latest_files = {}
    valid_paths = [Path(path) for path in paths if path and Path(path).exists() and Path(path).is_dir()]
    if not valid_paths:
        return []
    relative_root = Path(root_path) if root_path else min(valid_paths, key=lambda item: len(str(item)))
    for base_path in valid_paths:
        for file_path in base_path.rglob("*"):
            if not file_path.is_file():
                continue
            file_info = get_lm_file_info(file_path)
            if file_info is None:
                continue
            try:
                file_info["relative_path"] = str(file_path.relative_to(relative_root))
            except Exception:
                file_info["relative_path"] = str(file_path)
            current = latest_files.get(file_info["lm_code"])
            if current is None or file_info["revision"] > current["revision"]:
                latest_files[file_info["lm_code"]] = file_info
    return sorted(latest_files.values(), key=lambda item: item["lm_code"])

def detect_lm_header_row(raw_df):
    for index, row in raw_df.iterrows():
        normalized_values = [normalize_lm_header(value) for value in row.tolist()]
        matches = len([value for value in normalized_values if value in LM_COLUMNS])
        if matches >= 4:
            return index
    return None

def get_lm_sheet_score(raw_df):
    header_row = detect_lm_header_row(raw_df)
    if header_row is None:
        return -1, None
    normalized_values = [normalize_lm_header(value) for value in raw_df.iloc[header_row].tolist()]
    score = len([value for value in normalized_values if value in LM_COLUMNS])
    if "Descripcion" in normalized_values:
        score += 10
    if "P/N" in normalized_values:
        score += 5
    return score, header_row

@st.cache_data(show_spinner=False)
def read_lm_sheet_preview_cached(file_path, sheet_name, file_mtime_ns, file_size):
    return pd.read_excel(file_path, sheet_name=sheet_name, header=None, dtype=str, nrows=80)

@st.cache_data(show_spinner=False)
def read_lm_sheet_full_cached(file_path, sheet_name, file_mtime_ns, file_size):
    return pd.read_excel(file_path, sheet_name=sheet_name, header=None, dtype=str)

def get_file_cache_stamp(path):
    stat = Path(path).stat()
    return stat.st_mtime_ns, stat.st_size

def read_best_lm_sheet(path):
    file_path = str(path)
    try:
        file_mtime_ns, file_size = get_file_cache_stamp(file_path)
        excel_file = pd.ExcelFile(file_path)
    except Exception:
        return None, None
    best_sheet = None
    best_header_row = None
    best_score = -1
    preferred_sheets = sorted(excel_file.sheet_names, key=lambda sheet_name: 0 if str(sheet_name).strip().upper() == "LM_DESCRIPCION" else 1)
    for sheet_name in preferred_sheets:
        try:
            preview_df = read_lm_sheet_preview_cached(file_path, sheet_name, file_mtime_ns, file_size)
            score, header_row = get_lm_sheet_score(preview_df)
        except Exception:
            continue
        if score > best_score:
            best_sheet = sheet_name
            best_header_row = header_row
            best_score = score
    if best_sheet is None or best_header_row is None:
        return None, None
    try:
        raw_df = read_lm_sheet_full_cached(file_path, best_sheet, file_mtime_ns, file_size)
        return raw_df, best_header_row
    except Exception:
        return None, None

@st.cache_data(show_spinner=False)
def read_lm_file_cached(file_path, lm_code, revision_label, relative_path, file_mtime_ns, file_size):
    log_lines = []
    log_prefix = f"{lm_code} {revision_label} | {relative_path}"
    raw_df, header_row = read_best_lm_sheet(file_path)
    if raw_df is None or header_row is None:
        log_lines.append(f"[ERROR] {log_prefix} | No se ha podido detectar una hoja válida o cabecera de LM.")
        empty_df = pd.DataFrame(columns=["LM DOC", "Edición", "Origen fichero"] + LM_COLUMNS)
        return empty_df, log_lines
    log_lines.append(f"[OK] {log_prefix} | Hoja válida detectada. Fila cabecera: {header_row + 1}.")
    headers = [normalize_lm_header(value) for value in raw_df.iloc[header_row].tolist()]
    data_df = raw_df.iloc[header_row + 1:].copy()
    data_df.columns = headers
    initial_rows = len(data_df)
    data_df = data_df.dropna(how="all")
    removed_empty_rows = initial_rows - len(data_df)
    if removed_empty_rows > 0:
        log_lines.append(f"[INFO] {log_prefix} | Filas completamente vacías eliminadas: {removed_empty_rows}.")
    if data_df.columns.duplicated().any():
        duplicated_names = sorted(set([column for column in data_df.columns[data_df.columns.duplicated()].tolist() if column]))
        log_lines.append(f"[OK] {log_prefix} | Columnas duplicadas fusionadas correctamente: {', '.join(duplicated_names)}.")
        duplicated_columns = [column for column in data_df.columns if column]
        compact_df = pd.DataFrame(index=data_df.index)
        for column in dict.fromkeys(duplicated_columns):
            same_columns_df = data_df.loc[:, data_df.columns == column]
            if same_columns_df.shape[1] == 1:
                compact_df[column] = same_columns_df.iloc[:, 0]
            else:
                compact_df[column] = same_columns_df.bfill(axis=1).iloc[:, 0]
        data_df = compact_df.copy()
    available_columns = [column for column in LM_COLUMNS if column in data_df.columns]
    missing_columns = [column for column in LM_COLUMNS if column not in data_df.columns]
    if missing_columns:
        log_lines.append(f"[WARNING] {log_prefix} | Columnas no encontradas y rellenadas con NOT AVAILABLE: {', '.join(missing_columns)}.")
    if available_columns:
        rows_before_material_filter = len(data_df)
        data_df = data_df[data_df[available_columns].fillna("").astype(str).apply(lambda row: any(value.strip() and value.strip().lower() != "nan" for value in row), axis=1)].copy()
        removed_no_material_rows = rows_before_material_filter - len(data_df)
        if removed_no_material_rows > 0:
            log_lines.append(f"[INFO] {log_prefix} | Filas sin datos útiles de material eliminadas: {removed_no_material_rows}.")
    else:
        log_lines.append(f"[ERROR] {log_prefix} | No se ha encontrado ninguna columna reconocible de LM.")
    if data_df.empty:
        log_lines.append(f"[ERROR] {log_prefix} | La LM queda vacía después de aplicar limpieza y filtros.")
        empty_df = pd.DataFrame(columns=["LM DOC", "Edición", "Origen fichero"] + LM_COLUMNS)
        return empty_df, log_lines
    result_df = pd.DataFrame(index=data_df.index)
    result_df["LM DOC"] = lm_code
    result_df["Edición"] = revision_label
    result_df["Origen fichero"] = relative_path
    for column in LM_COLUMNS:
        if column in data_df.columns:
            result_df[column] = data_df[column]
        else:
            result_df[column] = "NOT AVAILABLE"
    result_df = result_df.fillna("NOT AVAILABLE")
    result_df = result_df.replace("", "NOT AVAILABLE")
    log_lines.append(f"[OK] {log_prefix} | Filas cargadas correctamente: {len(result_df)}.")
    return result_df[["LM DOC", "Edición", "Origen fichero"] + LM_COLUMNS], log_lines

def read_lm_file(file_info):
    file_path = str(file_info["path"])
    try:
        file_mtime_ns, file_size = get_file_cache_stamp(file_path)
    except Exception as error:
        empty_df = pd.DataFrame(columns=["LM DOC", "Edición", "Origen fichero"] + LM_COLUMNS)
        empty_df.attrs["lm_read_log"] = [f"[ERROR] {file_info.get('lm_code', 'LM DESCONOCIDA')} {file_info.get('revision_label', '')} | {file_path} | No se puede acceder al fichero: {error}."]
        return empty_df
    lm_df, log_lines = read_lm_file_cached(file_path, file_info["lm_code"], file_info["revision_label"], file_info.get("relative_path", file_path), file_mtime_ns, file_size)
    lm_df.attrs["lm_read_log"] = log_lines
    return lm_df

def get_selected_hw_paths(df, selected_code):
    if df.empty or not selected_code:
        return []
    if selected_code == "A00":
        selected_df = df[df["exists"] == True].copy()
    else:
        selected_df = get_descendant_rows_by_code(df, selected_code)
    if selected_df.empty or "path" not in selected_df.columns:
        return []
    paths = selected_df["path"].dropna().astype(str).tolist()
    return [path for path in paths if path.strip()]

def get_hw_root_path(df):
    if df.empty or "path" not in df.columns:
        return None
    paths = [path for path in df["path"].dropna().astype(str).tolist() if path.strip()]
    if not paths:
        return None
    try:
        return str(Path(paths[0]).anchor) if len(paths) == 1 else str(Path(paths[0]).parent if len(paths) == 1 else Path(__import__("os").path.commonpath(paths)))
    except Exception:
        return None

def render_lm_materials_table(materials_df):
    grid_builder = GridOptionsBuilder.from_dataframe(materials_df)
    grid_builder.configure_default_column(filter=True, sortable=True, resizable=True, editable=False)
    grid_builder.configure_column("CODIGO MATERIAL", minWidth=140)
    grid_builder.configure_column("DESCRIPCION", minWidth=220)
    grid_builder.configure_column("LM_DOC", minWidth=140)
    grid_builder.configure_column("EDICION", minWidth=90)
    grid_builder.configure_column("Origen fichero", minWidth=260)
    auto_size_code = JsCode("function(params) { const cols = ['CODIGO MATERIAL', 'DESCRIPCION', 'LM_DOC', 'EDICION', 'Origen fichero']; setTimeout(function() { params.api.autoSizeColumns(cols, false); }, 500); setTimeout(function() { params.api.autoSizeColumns(cols, false); }, 1200); }")
    grid_builder.configure_grid_options(domLayout="normal", onGridReady=auto_size_code, onFirstDataRendered=auto_size_code)
    grid_options = grid_builder.build()
    AgGrid(materials_df, gridOptions=grid_options, height=520, fit_columns_on_grid_load=False, allow_unsafe_jscode=True)

def render_lm_read_log(log_lines):
    st.markdown("### Log de lectura y fusión de LMs")
    available_levels = ["OK", "INFO", "WARNING", "ERROR"]
    default_levels = ["WARNING", "ERROR"]
    selected_levels = st.multiselect("Mostrar tipos de mensaje", options=available_levels, default=default_levels, key="lm_read_log_levels")
    if not log_lines:
        st.text_area("Detalle de lectura", value="Sin anomalías detectadas. Todas las LMs cargadas correctamente.", height=180, disabled=True)
        return
    filtered_log_lines = []
    for line in log_lines:
        line_level = ""
        for level in available_levels:
            if line.startswith(f"[{level}]"):
                line_level = level
                break
        if line_level in selected_levels:
            filtered_log_lines.append(line)
    if not filtered_log_lines:
        log_text = "No hay mensajes para los tipos seleccionados."
    else:
        log_text = "\n".join(filtered_log_lines)
    st.text_area("Detalle de lectura", value=log_text, height=220, disabled=True)

def render_lms(df, selected_code):
    selected_row = get_main_element_row(df, selected_code)
    if selected_row is None:
        st.warning("No hay elemento HW seleccionado.")
        return
    selected_code_value = selected_row.get("code", "")
    selected_component = selected_row.get("component", "")
    st.subheader(f"LMs - {selected_code_value} - {selected_component}")
    selected_paths = get_selected_hw_paths(df, selected_code)
    root_path = get_hw_root_path(df)
    lm_files = find_latest_lm_files(selected_paths, root_path)
    if not lm_files:
        st.subheader("Elemento HW Sin Lista de Materiales")
        return
    loaded_tables = []
    unreadable_files = []
    read_log_lines = []
    for file_info in lm_files:
        lm_df = read_lm_file(file_info)
        read_log_lines.extend(lm_df.attrs.get("lm_read_log", []))
        if lm_df.empty:
            unreadable_files.append(f"{file_info['lm_code']} {file_info['revision_label']} | {file_info.get('relative_path', str(file_info['path']))}")
            continue
        loaded_tables.append(lm_df)
    if not loaded_tables:
        st.subheader("Elemento HW Sin Lista de Materiales")
        if unreadable_files:
            read_log_lines.append("[ERROR] No se ha podido cargar ninguna LM válida para el elemento seleccionado.")
        render_lm_read_log(read_log_lines)
        return
    materials_df = pd.concat(loaded_tables, ignore_index=True)
    materials_df = materials_df.rename(columns={"LM DOC": "LM_DOC", "Edición": "EDICION"})
    duplicated_columns = materials_df.columns[materials_df.columns.duplicated()].tolist()
    if duplicated_columns:
        read_log_lines.append(f"[OK] Tabla fusionada | Columnas duplicadas eliminadas correctamente tras la fusión: {', '.join(duplicated_columns)}.")
        materials_df = materials_df.loc[:, ~materials_df.columns.duplicated()].copy()
    required_columns = ["CODIGO MATERIAL", "DESCRIPCION", "LM_DOC", "EDICION", "CANTIDAD", "REF.TOP.", "UNIDAD", "PROBABILIDAD", "P/N", "MNF", "ELEC/MEC", "CHECK BOM", "Origen fichero"]
    for column in required_columns:
        if column not in materials_df.columns:
            materials_df[column] = "NOT AVAILABLE"
            read_log_lines.append(f"[WARNING] Tabla fusionada | Columna obligatoria no existente en la fusión, añadida como NOT AVAILABLE: {column}.")
    priority_columns = ["CODIGO MATERIAL", "DESCRIPCION", "LM_DOC", "EDICION"]
    last_columns = ["Origen fichero"]
    remaining_columns = [column for column in materials_df.columns if column not in priority_columns and column not in last_columns]
    materials_df = materials_df[priority_columns + remaining_columns + last_columns]
    st.caption(f"{len(lm_files)} listas de materiales encontradas. Si existen varias ediciones de una misma lista, solo se carga la más actualizada.")
    if unreadable_files:
        st.warning("No se han podido cargar estas listas: " + ", ".join(unreadable_files))
    render_lm_materials_table(materials_df)
    read_log_lines.append(f"[OK] Tabla fusionada | LMs válidas cargadas: {len(loaded_tables)}.")
    read_log_lines.append(f"[OK] Tabla fusionada | Filas totales fusionadas: {len(materials_df)}.")
    read_log_lines.append(f"[OK] Tabla fusionada | Columnas finales: {', '.join(materials_df.columns.tolist())}.")
    render_lm_read_log(read_log_lines)