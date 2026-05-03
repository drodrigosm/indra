# Modulo principal LMs. Carga y muestra las Listas de Materiales asociadas al elemento HW seleccionado en el sidebar global.

from pathlib import Path
import os
import re
import pandas as pd
import streamlit as st
from HW_scanner import get_descendant_rows_by_code, get_level_from_code, get_main_element_row, get_sidebar_main_elements
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode

EXCEL_READ_ENGINE = "calamine"
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
    relative_root = Path(root_path) if root_path and Path(root_path).exists() else min(valid_paths, key=lambda item: len(str(item)))
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



def build_lm_hw_path_signature(df):
    if df is None or df.empty or "path" not in df.columns:
        return tuple()
    records = []
    for _, row in df[df["exists"] == True].copy().iterrows():
        code = str(row.get("code", "")).strip().upper()
        path = str(row.get("path", "")).strip()
        level = int(row.get("level", 0)) if str(row.get("level", "")).strip() else 0
        if code and path and Path(path).exists() and Path(path).is_dir():
            records.append((code, path, level))
    return tuple(sorted(set(records), key=lambda item: (item[2], item[0], item[1])))


def is_path_inside(child_path, parent_path):
    try:
        child = os.path.abspath(str(child_path))
        parent = os.path.abspath(str(parent_path))
        return os.path.commonpath([child, parent]) == parent
    except Exception:
        return False


def build_lm_global_file_index(df, root_path=None):
    indexed_files = []
    if df is None or df.empty:
        return indexed_files
    sidebar_elements = get_sidebar_main_elements(df)
    for main in sidebar_elements:
        main_code = str(main.get("code", "")).strip().upper()
        main_exists = bool(main.get("exists", False))
        if not main_code or main_code == "A00" or not main_exists:
            continue
        main_paths = get_selected_hw_paths(df, main_code, root_path)
        main_lm_files = find_latest_lm_files(main_paths, root_path)
        for file_info in main_lm_files:
            indexed_item = dict(file_info)
            indexed_item["main_code"] = main_code
            indexed_files.append(indexed_item)
    return sorted(indexed_files, key=lambda item: (item.get("main_code", ""), item.get("relative_path", ""), item.get("lm_code", ""), item.get("revision", 0)))

def select_latest_lm_files(lm_files):
    latest_files = {}
    for file_info in lm_files:
        lm_code = str(file_info.get("lm_code", "")).strip().upper()
        if not lm_code:
            continue
        current = latest_files.get(lm_code)
        if current is None or int(file_info.get("revision", 0)) > int(current.get("revision", 0)):
            latest_files[lm_code] = file_info
    return sorted(latest_files.values(), key=lambda item: item.get("lm_code", ""))


def get_lm_files_from_index_for_code(df, selected_code, lm_file_index, root_path=None):
    selected_code_text = str(selected_code).strip().upper()
    if not selected_code_text or df.empty or not lm_file_index:
        return []
    if selected_code_text == "A00":
        return sorted(list(lm_file_index), key=lambda item: (item.get("relative_path", ""), item.get("lm_code", ""), item.get("revision", 0)))
    if get_level_from_code(selected_code_text) == 1:
        return sorted([file_info for file_info in lm_file_index if str(file_info.get("main_code", "")).strip().upper() == selected_code_text], key=lambda item: (item.get("relative_path", ""), item.get("lm_code", ""), item.get("revision", 0)))
    selected_paths = get_selected_hw_paths(df, selected_code_text, root_path)
    return find_latest_lm_files(selected_paths, root_path) if selected_paths else []

def get_all_lm_files_from_index(lm_file_index):
    return sorted(list(lm_file_index or []), key=lambda item: (item.get("relative_path", ""), item.get("lm_code", ""), item.get("revision", 0)))


def preload_lm_material_files(lm_file_signature, progress_bar=None, status_box=None, start_percent=65, end_percent=98):
    total_files = len(lm_file_signature)
    loaded_files = 0
    unreadable_files = 0
    if total_files == 0:
        if progress_bar is not None:
            progress_bar.progress(end_percent)
        if status_box is not None:
            status_box.info("No se han detectado ficheros LM para precargar.")
        return {"total_lm_files": 0, "loaded_lm_files": 0, "unreadable_lm_files": 0}
    for index, record in enumerate(lm_file_signature):
        file_path, lm_code, revision, revision_label, relative_path, file_mtime_ns, file_size = record
        if status_box is not None:
            status_box.info(f"Precargando LM {index + 1}/{total_files}: {lm_code} {revision_label} | {relative_path}")
        try:
            lm_df, log_lines = read_lm_file_cached(file_path, lm_code, revision_label, relative_path, file_mtime_ns, file_size)
            loaded_files += 0 if lm_df.empty else 1
            unreadable_files += 1 if lm_df.empty else 0
        except Exception:
            unreadable_files += 1
        if progress_bar is not None:
            current_percent = int(start_percent + ((index + 1) / total_files) * (end_percent - start_percent))
            progress_bar.progress(min(current_percent, end_percent))
    return {"total_lm_files": total_files, "loaded_lm_files": loaded_files, "unreadable_lm_files": unreadable_files}

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
    return pd.read_excel(file_path, sheet_name=sheet_name, header=None, dtype=str, nrows=80, engine=EXCEL_READ_ENGINE)

@st.cache_data(show_spinner=False)
def read_lm_sheet_full_cached(file_path, sheet_name, file_mtime_ns, file_size):
    return pd.read_excel(file_path, sheet_name=sheet_name, header=None, dtype=str, engine=EXCEL_READ_ENGINE)

def get_file_cache_stamp(path):
    stat = Path(path).stat()
    return stat.st_mtime_ns, stat.st_size

def format_lm_read_error(error):
    error_text = str(error)
    if "Permission denied" in error_text or "WinError 32" in error_text or "being used by another process" in error_text or "El proceso no tiene acceso" in error_text:
        return f"No se puede leer el fichero. Puede estar abierto, bloqueado por Excel o usado por otro proceso. Detalle: {error_text}"
    return f"Error leyendo el fichero. Detalle: {error_text}"

def read_best_lm_sheet(path):
    file_path = str(path)
    try:
        file_mtime_ns, file_size = get_file_cache_stamp(file_path)
        excel_file = pd.ExcelFile(file_path, engine=EXCEL_READ_ENGINE)
    except Exception as error:
        return None, None, format_lm_read_error(error)
    best_sheet = None
    best_header_row = None
    best_score = -1
    preferred_sheets = sorted(excel_file.sheet_names, key=lambda sheet_name: 0 if str(sheet_name).strip().upper() == "LM_DESCRIPCION" else 1)
    for sheet_name in preferred_sheets:
        try:
            preview_df = read_lm_sheet_preview_cached(file_path, sheet_name, file_mtime_ns, file_size)
            score, header_row = get_lm_sheet_score(preview_df)
        except Exception as error:
            continue
        if score > best_score:
            best_sheet = sheet_name
            best_header_row = header_row
            best_score = score
    if best_sheet is None or best_header_row is None:
        return None, None, "No se ha podido detectar una hoja válida o una cabecera reconocible de LM."
    try:
        raw_df = read_lm_sheet_full_cached(file_path, best_sheet, file_mtime_ns, file_size)
        return raw_df, best_header_row, ""
    except Exception as error:
        return None, None, format_lm_read_error(error)

@st.cache_data(show_spinner=False)
def read_lm_file_cached(file_path, lm_code, revision_label, relative_path, file_mtime_ns, file_size):
    log_lines = []
    log_prefix = f"{lm_code} {revision_label} | {relative_path}"
    
    raw_df, header_row, read_error = read_best_lm_sheet(file_path)
    if raw_df is None or header_row is None:
        error_message = read_error if read_error else "No se ha podido detectar una hoja válida o cabecera de LM."
        log_lines.append(f"[ERROR] {log_prefix} | {error_message}")
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

def get_selected_hw_paths(df, selected_code, root_path=None):
    if not selected_code:
        return []
    if df.empty:
        return []
    selected_code_text = str(selected_code).strip().upper()
    if selected_code_text == "A00":
        return []
    selected_df = get_descendant_rows_by_code(df, selected_code_text)
    if selected_df.empty or "path" not in selected_df.columns:
        return []
    paths = selected_df["path"].dropna().astype(str).tolist()
    return [path for path in paths if path.strip()]

def get_lm_files_for_selected_code(df, selected_code, root_path=None):
    lm_file_index = st.session_state.get("lm_global_file_index", [])
    if lm_file_index:
        return get_lm_files_from_index_for_code(df, selected_code, lm_file_index, root_path)
    selected_code_text = str(selected_code).strip().upper()
    if selected_code_text != "A00":
        selected_paths = get_selected_hw_paths(df, selected_code_text, root_path)
        return find_latest_lm_files(selected_paths, root_path)
    lm_files = []
    sidebar_elements = get_sidebar_main_elements(df)
    for main in sidebar_elements:
        main_code = str(main.get("code", "")).strip().upper()
        main_exists = bool(main.get("exists", False))
        if not main_code or main_code == "A00" or not main_exists:
            continue
        main_paths = get_selected_hw_paths(df, main_code, root_path)
        main_lm_files = find_latest_lm_files(main_paths, root_path)
        lm_files.extend(main_lm_files)
    return sorted(lm_files, key=lambda item: (item.get("relative_path", ""), item.get("lm_code", ""), item.get("revision", 0)))

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

def build_lm_file_signature(lm_files):
    records = []
    for file_info in lm_files:
        file_path = str(file_info.get("path", ""))
        try:
            file_mtime_ns, file_size = get_file_cache_stamp(file_path)
        except Exception:
            file_mtime_ns, file_size = 0, 0
        records.append((file_path, str(file_info.get("lm_code", "")).upper(), int(file_info.get("revision", 0)), str(file_info.get("revision_label", "")), str(file_info.get("relative_path", file_path)), int(file_mtime_ns), int(file_size)))
    return tuple(sorted(records, key=lambda item: (item[4], item[1], item[2], item[0])))

def build_empty_lm_materials_result(lm_file_signature, read_log_lines=None, unreadable_files=None):
    materials_df = pd.DataFrame(columns=["CODIGO MATERIAL", "DESCRIPCION", "LM_DOC", "EDICION", "Campos obligatorios incompletos", "CANTIDAD", "REF.TOP.", "UNIDAD", "PROBABILIDAD", "P/N", "MNF", "ELEC/MEC", "CHECK BOM", "Origen fichero"])
    export_missing_df = pd.DataFrame(columns=materials_df.columns)
    metrics = {"total_lm_files": len(lm_file_signature), "loaded_lm_files": 0, "unreadable_lm_files": len(unreadable_files or []), "materials_with_missing_required": 0, "export_missing_count": 0}
    return materials_df, export_missing_df, read_log_lines or [], unreadable_files or [], metrics

@st.cache_data(show_spinner=False)
def load_lm_materials_cached(lm_file_signature):
    loaded_tables = []
    unreadable_files = []
    read_log_lines = []
    for file_path, lm_code, revision, revision_label, relative_path, file_mtime_ns, file_size in lm_file_signature:
        if not file_path:
            unreadable_files.append(f"{lm_code} {revision_label} | Ruta de fichero no disponible")
            read_log_lines.append(f"[ERROR] {lm_code} {revision_label} | Ruta de fichero no disponible.")
            continue
        if file_mtime_ns == 0 and file_size == 0 and not Path(file_path).exists():
            unreadable_files.append(f"{lm_code} {revision_label} | {relative_path}")
            read_log_lines.append(f"[ERROR] {lm_code} {revision_label} | {relative_path} | No se puede acceder al fichero.")
            continue
        lm_df, log_lines = read_lm_file_cached(file_path, lm_code, revision_label, relative_path, file_mtime_ns, file_size)
        read_log_lines.extend(log_lines)
        if lm_df.empty:
            unreadable_files.append(f"{lm_code} {revision_label} | {relative_path}")
            continue
        loaded_tables.append(lm_df)
    if not loaded_tables:
        if unreadable_files:
            read_log_lines.append("[ERROR] No se ha podido cargar ninguna LM válida para el elemento seleccionado.")
        return build_empty_lm_materials_result(lm_file_signature, read_log_lines, unreadable_files)
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
    required_material_fields = ["CODIGO MATERIAL", "CANTIDAD", "REF.TOP.", "UNIDAD"]
    missing_required_mask = materials_df[required_material_fields].astype(str).apply(lambda row: any(value.strip() == "" or value.strip().upper() == "NOT AVAILABLE" or value.strip().lower() == "nan" for value in row), axis=1)
    materials_df["Campos obligatorios incompletos"] = missing_required_mask.map({True: "SI", False: "NO"})
    materials_with_missing_required = int(missing_required_mask.sum())
    export_required_fields = ["CODIGO MATERIAL", "DESCRIPCION", "LM_DOC", "EDICION"]
    export_missing_mask = materials_df[export_required_fields].astype(str).apply(lambda row: any(value.strip() == "" or value.strip().upper() == "NOT AVAILABLE" or value.strip().lower() == "nan" for value in row), axis=1)
    export_missing_df = materials_df[export_missing_mask].copy()
    export_missing_count = len(export_missing_df)
    priority_columns = ["CODIGO MATERIAL", "DESCRIPCION", "LM_DOC", "EDICION", "Campos obligatorios incompletos"]
    last_columns = ["Origen fichero"]
    remaining_columns = [column for column in materials_df.columns if column not in priority_columns and column not in last_columns]
    materials_df = materials_df[priority_columns + remaining_columns + last_columns]
    read_log_lines.append(f"[OK] Tabla fusionada | LMs válidas cargadas: {len(loaded_tables)}.")
    read_log_lines.append(f"[OK] Tabla fusionada | Filas totales fusionadas: {len(materials_df)}.")
    read_log_lines.append(f"[OK] Tabla fusionada | Columnas finales: {', '.join(materials_df.columns.tolist())}.")
    metrics = {"total_lm_files": len(lm_file_signature), "loaded_lm_files": len(loaded_tables), "unreadable_lm_files": len(unreadable_files), "materials_with_missing_required": materials_with_missing_required, "export_missing_count": export_missing_count}
    return materials_df, export_missing_df, read_log_lines, unreadable_files, metrics

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
    root_path = st.session_state.get("root_path", "")
    lm_files = get_lm_files_for_selected_code(df, selected_code, root_path)
    if not lm_files:
        st.subheader("Elemento HW Sin Lista de Materiales")
        return
    lm_file_signature = build_lm_file_signature(lm_files)
    st.caption(f"{len(lm_file_signature)} listas de materiales detectadas para el elemento seleccionado. La lectura y fusión quedan cacheadas hasta actualizar la lectura o modificar los ficheros.")
    with st.spinner("Cargando LMs del elemento seleccionado..."):
        materials_df, export_missing_df, read_log_lines, unreadable_files, metrics = load_lm_materials_cached(lm_file_signature)
    if materials_df.empty:
        st.subheader("Elemento HW Sin Lista de Materiales")
        render_lm_read_log(read_log_lines)
        return
    info_col, export_col = st.columns([5, 1])
    info_col.caption(f"{metrics['total_lm_files']} listas de materiales encontradas. {metrics['loaded_lm_files']} listas cargadas correctamente. {metrics['unreadable_lm_files']} listas no cargadas. {len(materials_df)} materiales cargados. {metrics['materials_with_missing_required']} materiales cargados sin alguno de estos campos: CODIGO MATERIAL, CANTIDAD, REF.TOP., UNIDAD. {metrics['export_missing_count']} registros cargados tienen CODIGO MATERIAL, DESCRIPCION, LM_DOC o EDICION en NOT AVAILABLE. Si existen varias ediciones de una misma lista, solo se carga la más actualizada.")
    if metrics["export_missing_count"] > 0:
        export_csv = export_missing_df.to_csv(index=False, sep=";").encode("utf-8-sig")
        export_col.download_button("Exportar errores CSV", data=export_csv, file_name=f"LMs_{selected_code_value}_registros_not_available.csv", mime="text/csv", key=f"download_lm_missing_priority_{selected_code_value}")
    else:
        export_col.button("Exportar errores CSV", disabled=True, key=f"download_lm_missing_priority_disabled_{selected_code_value}")
    if unreadable_files:
        st.error("Hay LMs que no se han podido leer. Revisa si están abiertas, bloqueadas o corruptas: " + ", ".join(unreadable_files))
    render_lm_materials_table(materials_df)
    render_lm_read_log(read_log_lines)

