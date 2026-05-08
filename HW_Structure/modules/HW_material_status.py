# Modulo principal Material Status. Carga el fichero SAP de estado de material, cruza sus materiales con las LMs del elemento seleccionado y muestra estado de compra, entrega y precio por modulo.

from pathlib import Path
from io import BytesIO
import re
import pandas as pd
import streamlit as st
from HW_scanner import get_main_element_row
from HW_ui_common import style_dark_dataframe
from modules.HW_LMs import build_lm_file_signature, get_lm_files_for_selected_code, load_lm_materials_cached
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode

MATERIAL_STATUS_REQUIRED_COLUMNS = ["Material", "Descripción material", "Nº Cesta / Sol", "Fecha Sol.", "Nº pedido", "Fecha Ped.", "Elemento PEP", "Fe. Entrega", "Entrega final", "Ctd. pedido", "Imp. unitario Ped.", "Cant Base Ped."]
MATERIAL_STATUS_OPTIONAL_COLUMNS = ["Posición sol.", "Posición ped.", "Desc.Proveedor", "Solic.", "Comprador", "Ctd. Solicitada", "Ctd. por recepcionar", "Ctd. Aceptada", "Ctd. Rechazada", "Imp.total pos SP", "Centro", "Almacen", "Estado", "Moneda Ped.", "Unidad", "Tipo Compra"]
MATERIAL_STATUS_NUMERIC_COLUMNS = ["Ctd. pedido", "Imp. unitario Ped.", "Cant Base Ped."]
MATERIAL_STATUS_DATE_COLUMNS = ["Fecha Sol.", "Fecha Ped.", "Fe. Entrega"]
MATERIAL_STATUS_DETAIL_COLUMNS = ["Material", "Descripción material", "Nº Cesta / Sol", "Fecha Sol.", "Nº pedido", "Fecha Ped.", "Elemento PEP", "Desc.Proveedor", "Fe. Entrega", "Entrega final", "Ctd. pedido", "Imp. unitario Ped.", "Cant Base Ped.", "Precio unitario real", "Importe línea calculado", "Estado entrega"]
MATERIAL_STATUS_CROSS_COLUMNS = ["CODIGO MATERIAL", "DESCRIPCION LM", "Descripción material", "CANTIDAD LM", "CANTIDAD PEDIDA", "CANTIDAD ENTREGADA", "CANTIDAD PENDIENTE", "COBERTURA COMPRA", "ESTADO COMPRA", "ESTADO ENTREGA", "PRECIO UNITARIO MEDIO", "PRECIO UNITARIO ULTIMO", "COSTE LM ESTIMADO", "COSTE PEDIDO", "Nº PEDIDOS", "Nº CESTAS/SOLPEDS", "PRIMERA FECHA SOL.", "ULTIMA FECHA PED.", "FECHA ENTREGA PROXIMA", "FECHA ENTREGA ULTIMA", "Elemento PEP", "Proveedor", "VARIOS PRECIOS", "Nº PRECIOS DISTINTOS", "LM_DOCS"]


def normalize_column_name(value):
    text = "" if value is None else str(value)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_material_key(value):
    if value is None:
        return ""
    text = str(value).replace("\xa0", " ").strip().upper()
    if text.lower() in ["", "nan", "none", "not available"]:
        return ""
    if re.match(r"^\d+\.0$", text):
        text = text[:-2]
    return text


def parse_number(value):
    if value is None:
        return 0.0
    text = str(value).replace("\xa0", " ").strip()
    if text.lower() in ["", "nan", "none", "not available"]:
        return 0.0
    text = text.replace("€", "").replace(" ", "")
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except Exception:
        return 0.0


def parse_date(value):
    if value is None:
        return pd.NaT
    text = str(value).strip()
    if text.lower() in ["", "nan", "none", "not available"]:
        return pd.NaT
    return pd.to_datetime(text, errors="coerce", dayfirst=False)


def format_currency(value):
    try:
        number = float(value)
    except Exception:
        return "0,00 €"
    formatted = f"{number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{formatted} €"


def format_decimal(value, digits=2):
    try:
        number = float(value)
    except Exception:
        return "0"
    formatted = f"{number:,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return formatted


def join_unique_values(values, max_items=4):
    clean_values = []
    for value in values:
        text = str(value).strip()
        if text and text.lower() not in ["nan", "none", "not available"] and text not in clean_values:
            clean_values.append(text)
    if len(clean_values) > max_items:
        return " | ".join(clean_values[:max_items]) + f" | +{len(clean_values) - max_items}"
    return " | ".join(clean_values) if clean_values else "NOT AVAILABLE"


def get_material_status_cache_stamp(path):
    stat = Path(path).stat()
    return int(stat.st_mtime_ns), int(stat.st_size)


def get_material_status_source_path():
    uploaded_name = str(st.session_state.get("material_status_uploaded_name", "")).strip()
    uploaded_bytes = st.session_state.get("material_status_uploaded_bytes", b"")
    if uploaded_name and uploaded_bytes:
        return uploaded_name
    path = str(st.session_state.get("material_status_file_path", "")).strip()
    return path if path and Path(path).exists() and Path(path).is_file() else ""


def get_material_status_active_source():
    uploaded_name = str(st.session_state.get("material_status_uploaded_name", "")).strip()
    uploaded_bytes = st.session_state.get("material_status_uploaded_bytes", b"")
    if uploaded_name and uploaded_bytes:
        return {"mode": "uploaded", "display_name": uploaded_name, "file_bytes": uploaded_bytes, "file_size": int(st.session_state.get("material_status_uploaded_size", len(uploaded_bytes)))}
    path = str(st.session_state.get("material_status_file_path", "")).strip()
    if path and Path(path).exists() and Path(path).is_file():
        file_mtime_ns, file_size = get_material_status_cache_stamp(path)
        return {"mode": "path", "display_name": path, "file_path": path, "file_mtime_ns": file_mtime_ns, "file_size": file_size}
    return {"mode": "none", "display_name": "", "file_size": 0}


@st.cache_data(show_spinner=False)
def read_material_status_excel_cached(file_path, file_mtime_ns, file_size):
    log_lines = []
    try:
        excel_file = pd.ExcelFile(file_path)
    except Exception as error:
        return pd.DataFrame(), [f"[ERROR] No se puede abrir el fichero Material Status: {error}."]
    best_sheet = excel_file.sheet_names[0] if excel_file.sheet_names else None
    if best_sheet is None:
        return pd.DataFrame(), ["[ERROR] El fichero Material Status no contiene hojas."]
    try:
        raw_df = pd.read_excel(file_path, sheet_name=best_sheet, dtype=str)
    except Exception as error:
        return pd.DataFrame(), [f"[ERROR] No se puede leer la hoja {best_sheet}: {error}."]
    raw_df.columns = [normalize_column_name(column) for column in raw_df.columns]
    duplicated_columns = raw_df.columns[raw_df.columns.duplicated()].tolist()
    if duplicated_columns:
        raw_df = raw_df.loc[:, ~raw_df.columns.duplicated()].copy()
        log_lines.append(f"[WARNING] Columnas duplicadas eliminadas en Material Status: {', '.join(sorted(set(duplicated_columns)))}.")
    for column in MATERIAL_STATUS_REQUIRED_COLUMNS + MATERIAL_STATUS_OPTIONAL_COLUMNS:
        if column not in raw_df.columns:
            raw_df[column] = "NOT AVAILABLE"
            level = "ERROR" if column in MATERIAL_STATUS_REQUIRED_COLUMNS else "WARNING"
            log_lines.append(f"[{level}] Columna no encontrada en Material Status y añadida como NOT AVAILABLE: {column}.")
    result_df = raw_df.copy()
    result_df["Material Key"] = result_df["Material"].apply(normalize_material_key)
    result_df = result_df[result_df["Material Key"] != ""].copy()
    for column in MATERIAL_STATUS_NUMERIC_COLUMNS:
        result_df[f"{column} Num"] = result_df[column].apply(parse_number)
    for column in MATERIAL_STATUS_DATE_COLUMNS:
        result_df[f"{column} Date"] = result_df[column].apply(parse_date)
    result_df["Precio unitario real"] = result_df.apply(lambda row: row["Imp. unitario Ped. Num"] / row["Cant Base Ped. Num"] if row["Cant Base Ped. Num"] else 0.0, axis=1)
    result_df["Importe línea calculado"] = result_df["Ctd. pedido Num"] * result_df["Precio unitario real"]
    result_df["Entrega final normalizada"] = result_df["Entrega final"].fillna("").astype(str).str.strip().str.upper()
    result_df["Estado entrega"] = result_df["Entrega final normalizada"].apply(lambda value: "Entregado" if value == "X" else "Pendiente")
    result_df["Precio unitario real Texto"] = result_df["Precio unitario real"].apply(format_currency)
    result_df["Importe línea calculado Texto"] = result_df["Importe línea calculado"].apply(format_currency)
    log_lines.append(f"[OK] Material Status cargado correctamente. Hoja: {best_sheet}. Líneas con material: {len(result_df)}.")
    return result_df, log_lines


@st.cache_data(show_spinner=False)
def read_material_status_excel_bytes_cached(file_name, file_bytes, file_size):
    log_lines = []
    try:
        excel_file = pd.ExcelFile(BytesIO(file_bytes))
    except Exception as error:
        return pd.DataFrame(), [f"[ERROR] No se puede abrir el fichero Material Status: {error}."]
    best_sheet = excel_file.sheet_names[0] if excel_file.sheet_names else None
    if best_sheet is None:
        return pd.DataFrame(), ["[ERROR] El fichero Material Status no contiene hojas."]
    try:
        raw_df = pd.read_excel(BytesIO(file_bytes), sheet_name=best_sheet, dtype=str)
    except Exception as error:
        return pd.DataFrame(), [f"[ERROR] No se puede leer la hoja {best_sheet}: {error}."]
    raw_df.columns = [normalize_column_name(column) for column in raw_df.columns]
    duplicated_columns = raw_df.columns[raw_df.columns.duplicated()].tolist()
    if duplicated_columns:
        raw_df = raw_df.loc[:, ~raw_df.columns.duplicated()].copy()
        log_lines.append(f"[WARNING] Columnas duplicadas eliminadas en Material Status: {', '.join(sorted(set(duplicated_columns)))}.")
    for column in MATERIAL_STATUS_REQUIRED_COLUMNS + MATERIAL_STATUS_OPTIONAL_COLUMNS:
        if column not in raw_df.columns:
            raw_df[column] = "NOT AVAILABLE"
            level = "ERROR" if column in MATERIAL_STATUS_REQUIRED_COLUMNS else "WARNING"
            log_lines.append(f"[{level}] Columna no encontrada en Material Status y añadida como NOT AVAILABLE: {column}.")
    result_df = raw_df.copy()
    result_df["Material Key"] = result_df["Material"].apply(normalize_material_key)
    result_df = result_df[result_df["Material Key"] != ""].copy()
    for column in MATERIAL_STATUS_NUMERIC_COLUMNS:
        result_df[f"{column} Num"] = result_df[column].apply(parse_number)
    for column in MATERIAL_STATUS_DATE_COLUMNS:
        result_df[f"{column} Date"] = result_df[column].apply(parse_date)
    result_df["Precio unitario real"] = result_df.apply(lambda row: row["Imp. unitario Ped. Num"] / row["Cant Base Ped. Num"] if row["Cant Base Ped. Num"] else 0.0, axis=1)
    result_df["Importe línea calculado"] = result_df["Ctd. pedido Num"] * result_df["Precio unitario real"]
    result_df["Entrega final normalizada"] = result_df["Entrega final"].fillna("").astype(str).str.strip().str.upper()
    result_df["Estado entrega"] = result_df["Entrega final normalizada"].apply(lambda value: "Entregado" if value == "X" else "Pendiente")
    result_df["Precio unitario real Texto"] = result_df["Precio unitario real"].apply(format_currency)
    result_df["Importe línea calculado Texto"] = result_df["Importe línea calculado"].apply(format_currency)
    log_lines.append(f"[OK] Material Status cargado correctamente. Fichero: {file_name}. Hoja: {best_sheet}. Líneas con material: {len(result_df)}.")
    return result_df, log_lines


def load_material_status_dataframe(progress_bar=None, status_box=None):
    source = get_material_status_active_source()
    if source.get("mode") == "none":
        return pd.DataFrame(), ["[INFO] No hay fichero Material Status cargado."]
    if progress_bar is not None:
        progress_bar.progress(35)
    if status_box is not None:
        status_box.info(f"Leyendo fichero Material Status: {source.get('display_name', '')}")
    if source.get("mode") == "uploaded":
        result = read_material_status_excel_bytes_cached(source.get("display_name", ""), source.get("file_bytes", b""), int(source.get("file_size", 0)))
    else:
        result = read_material_status_excel_cached(source.get("file_path", ""), int(source.get("file_mtime_ns", 0)), int(source.get("file_size", 0)))
    if progress_bar is not None:
        progress_bar.progress(65)
    if status_box is not None:
        status_box.info("Material Status leído. Preparando cruce con LMs...")
    return result


def load_lm_materials_for_selected_code(df, selected_code):
    root_path = st.session_state.get("root_path", "")
    lm_files = get_lm_files_for_selected_code(df, selected_code, root_path)
    if not lm_files:
        return pd.DataFrame(), ["[INFO] El elemento seleccionado no tiene LMs detectadas."], {"total_lm_files": 0, "loaded_lm_files": 0}
    lm_file_signature = build_lm_file_signature(lm_files)
    materials_df, export_missing_df, read_log_lines, unreadable_files, metrics = load_lm_materials_cached(lm_file_signature)
    return materials_df, read_log_lines, metrics


def aggregate_lm_materials(materials_df):
    if materials_df is None or materials_df.empty or "CODIGO MATERIAL" not in materials_df.columns:
        return pd.DataFrame(columns=["MATERIAL_KEY", "CODIGO MATERIAL", "DESCRIPCION LM", "CANTIDAD LM", "LM_DOCS"])
    result_df = materials_df.copy()
    result_df["MATERIAL_KEY"] = result_df["CODIGO MATERIAL"].apply(normalize_material_key)
    result_df = result_df[result_df["MATERIAL_KEY"] != ""].copy()
    if result_df.empty:
        return pd.DataFrame(columns=["MATERIAL_KEY", "CODIGO MATERIAL", "DESCRIPCION LM", "CANTIDAD LM", "LM_DOCS"])
    result_df["CANTIDAD LM NUM"] = result_df["CANTIDAD"].apply(parse_number) if "CANTIDAD" in result_df.columns else 0.0
    grouped_rows = []
    for material_key, group in result_df.groupby("MATERIAL_KEY", dropna=False):
        grouped_rows.append({"MATERIAL_KEY": material_key, "CODIGO MATERIAL": join_unique_values(group["CODIGO MATERIAL"].tolist(), 1), "DESCRIPCION LM": join_unique_values(group["DESCRIPCION"].tolist(), 2) if "DESCRIPCION" in group.columns else "NOT AVAILABLE", "CANTIDAD LM": float(group["CANTIDAD LM NUM"].sum()), "LM_DOCS": join_unique_values(group["LM_DOC"].tolist(), 6) if "LM_DOC" in group.columns else "NOT AVAILABLE"})
    return pd.DataFrame(grouped_rows)


def aggregate_material_status(ms_df):
    if ms_df is None or ms_df.empty:
        return pd.DataFrame()
    grouped_rows = []
    today = pd.Timestamp.today().normalize()
    for material_key, group in ms_df.groupby("Material Key", dropna=False):
        delivered_group = group[group["Entrega final normalizada"] == "X"].copy()
        pending_group = group[group["Entrega final normalizada"] != "X"].copy()
        valid_price_group = group[(group["Precio unitario real"] > 0) & (group["Ctd. pedido Num"] > 0)].copy()
        price_values = sorted(set([round(float(value), 8) for value in group["Precio unitario real"].tolist() if float(value) > 0]))
        weighted_price = float((valid_price_group["Precio unitario real"] * valid_price_group["Ctd. pedido Num"]).sum() / valid_price_group["Ctd. pedido Num"].sum()) if not valid_price_group.empty and valid_price_group["Ctd. pedido Num"].sum() else 0.0
        dated_group = group.dropna(subset=["Fecha Ped. Date"]).sort_values("Fecha Ped. Date").copy()
        last_price = float(dated_group.iloc[-1]["Precio unitario real"]) if not dated_group.empty else weighted_price
        pending_dates = pending_group.dropna(subset=["Fe. Entrega Date"])["Fe. Entrega Date"].tolist()
        next_delivery = min([date for date in pending_dates if date >= today], default=pd.NaT)
        overdue_count = int(len(pending_group[pending_group["Fe. Entrega Date"] < today])) if not pending_group.empty else 0
        grouped_rows.append({"MATERIAL_KEY": material_key, "Descripción material": join_unique_values(group["Descripción material"].tolist(), 2), "CANTIDAD PEDIDA": float(group["Ctd. pedido Num"].sum()), "CANTIDAD ENTREGADA": float(delivered_group["Ctd. pedido Num"].sum()) if not delivered_group.empty else 0.0, "CANTIDAD PENDIENTE": float(pending_group["Ctd. pedido Num"].sum()) if not pending_group.empty else 0.0, "PRECIO UNITARIO MEDIO": weighted_price, "PRECIO UNITARIO ULTIMO": last_price, "COSTE PEDIDO": float(group["Importe línea calculado"].sum()), "Nº PEDIDOS": int(group["Nº pedido"].replace("NOT AVAILABLE", pd.NA).dropna().nunique()), "Nº CESTAS/SOLPEDS": int(group["Nº Cesta / Sol"].replace("NOT AVAILABLE", pd.NA).dropna().nunique()), "PRIMERA FECHA SOL.": group["Fecha Sol. Date"].min(), "ULTIMA FECHA PED.": group["Fecha Ped. Date"].max(), "FECHA ENTREGA PROXIMA": next_delivery, "FECHA ENTREGA ULTIMA": group["Fe. Entrega Date"].max(), "Elemento PEP": join_unique_values(group["Elemento PEP"].tolist(), 4), "Proveedor": join_unique_values(group["Desc.Proveedor"].tolist(), 3), "VARIOS PRECIOS": "SI" if len(price_values) > 1 else "NO", "Nº PRECIOS DISTINTOS": len(price_values), "LINEAS MATERIAL STATUS": len(group), "LINEAS PENDIENTES VENCIDAS": overdue_count})
    return pd.DataFrame(grouped_rows)


def build_material_status_cross_for_selected_code(df, selected_code, progress_bar=None, status_box=None):
    if progress_bar is not None:
        progress_bar.progress(5)
    if status_box is not None:
        status_box.info("Cargando LMs del elemento seleccionado...")
    materials_df, lm_log_lines, lm_metrics = load_lm_materials_for_selected_code(df, selected_code)
    if progress_bar is not None:
        progress_bar.progress(20)
    if status_box is not None:
        status_box.info("Agrupando materiales de LMs...")
    lm_agg_df = aggregate_lm_materials(materials_df)
    ms_df, ms_log_lines = load_material_status_dataframe(progress_bar, status_box)
    if progress_bar is not None:
        progress_bar.progress(75)
    if status_box is not None:
        status_box.info("Agrupando Material Status por material...")
    ms_agg_df = aggregate_material_status(ms_df)
    if lm_agg_df.empty:
        empty_metrics = {"source_loaded": bool(get_material_status_source_path()), "precio_modulo": 0.0, "materiales_totales": 0, "materiales_encontrados": 0, "materiales_no_encontrados": 0, "materiales_con_precio": 0, "materiales_sin_precio": 0, "materiales_pendientes": 0, "materiales_entregados": 0, "lineas_material_status": 0}
        return pd.DataFrame(), pd.DataFrame(), ms_df, empty_metrics, lm_log_lines + ms_log_lines
    if ms_agg_df.empty:
        cross_df = lm_agg_df.copy()
        cross_df["MATERIAL_STATUS_ENCONTRADO"] = "NO"
        cross_df["COSTE LM ESTIMADO"] = 0.0
        metrics = {"source_loaded": bool(get_material_status_source_path()), "precio_modulo": 0.0, "materiales_totales": len(cross_df), "materiales_encontrados": 0, "materiales_no_encontrados": len(cross_df), "materiales_con_precio": 0, "materiales_sin_precio": len(cross_df), "materiales_pendientes": 0, "materiales_entregados": 0, "lineas_material_status": 0}
        return format_cross_table(cross_df), build_incidents_table(cross_df), ms_df, metrics, lm_log_lines + ms_log_lines
    cross_df = lm_agg_df.merge(ms_agg_df, on="MATERIAL_KEY", how="left")
    cross_df["MATERIAL_STATUS_ENCONTRADO"] = cross_df["Descripción material"].fillna("").astype(str).apply(lambda value: "SI" if value.strip() and value.strip().lower() != "nan" else "NO")
    for column in ["CANTIDAD PEDIDA", "CANTIDAD ENTREGADA", "CANTIDAD PENDIENTE", "PRECIO UNITARIO MEDIO", "PRECIO UNITARIO ULTIMO", "COSTE PEDIDO", "Nº PEDIDOS", "Nº CESTAS/SOLPEDS", "Nº PRECIOS DISTINTOS", "LINEAS MATERIAL STATUS", "LINEAS PENDIENTES VENCIDAS"]:
        if column not in cross_df.columns:
            cross_df[column] = 0
        cross_df[column] = cross_df[column].fillna(0)
    cross_df["COBERTURA COMPRA"] = cross_df.apply(lambda row: row["CANTIDAD PEDIDA"] / row["CANTIDAD LM"] if row["CANTIDAD LM"] else 0.0, axis=1)
    cross_df["ESTADO COMPRA"] = cross_df.apply(calculate_purchase_status, axis=1)
    cross_df["ESTADO ENTREGA"] = cross_df.apply(calculate_delivery_status, axis=1)
    cross_df["COSTE LM ESTIMADO"] = cross_df["CANTIDAD LM"] * cross_df["PRECIO UNITARIO MEDIO"]
    cross_df["Descripción material"] = cross_df["Descripción material"].fillna("NOT AVAILABLE")
    cross_df["Elemento PEP"] = cross_df["Elemento PEP"].fillna("NOT AVAILABLE")
    cross_df["Proveedor"] = cross_df["Proveedor"].fillna("NOT AVAILABLE")
    cross_df["VARIOS PRECIOS"] = cross_df["VARIOS PRECIOS"].fillna("NO")
    metrics = {"source_loaded": bool(get_material_status_source_path()), "precio_modulo": float(cross_df["COSTE LM ESTIMADO"].sum()), "materiales_totales": int(len(cross_df)), "materiales_encontrados": int((cross_df["MATERIAL_STATUS_ENCONTRADO"] == "SI").sum()), "materiales_no_encontrados": int((cross_df["MATERIAL_STATUS_ENCONTRADO"] != "SI").sum()), "materiales_con_precio": int(((cross_df["PRECIO UNITARIO MEDIO"] > 0) & (cross_df["MATERIAL_STATUS_ENCONTRADO"] == "SI")).sum()), "materiales_sin_precio": int(((cross_df["PRECIO UNITARIO MEDIO"] <= 0) | (cross_df["MATERIAL_STATUS_ENCONTRADO"] != "SI")).sum()), "materiales_pendientes": int(cross_df["ESTADO ENTREGA"].isin(["Pendiente", "Parcial", "Retrasado"]).sum()), "materiales_entregados": int((cross_df["ESTADO ENTREGA"] == "Entregado").sum()), "lineas_material_status": int(cross_df["LINEAS MATERIAL STATUS"].sum())}
    return format_cross_table(cross_df), build_incidents_table(cross_df), ms_df, metrics, lm_log_lines + ms_log_lines


def calculate_purchase_status(row):
    if str(row.get("MATERIAL_STATUS_ENCONTRADO", "NO")) != "SI":
        return "Sin compra"
    required_qty = float(row.get("CANTIDAD LM", 0))
    ordered_qty = float(row.get("CANTIDAD PEDIDA", 0))
    if ordered_qty <= 0:
        return "Sin compra"
    if required_qty <= 0:
        return "Comprado"
    if ordered_qty < required_qty:
        return "Parcial"
    if ordered_qty > required_qty:
        return "Exceso"
    return "Comprado"


def calculate_delivery_status(row):
    if str(row.get("MATERIAL_STATUS_ENCONTRADO", "NO")) != "SI":
        return "No encontrado"
    ordered_qty = float(row.get("CANTIDAD PEDIDA", 0))
    delivered_qty = float(row.get("CANTIDAD ENTREGADA", 0))
    overdue_lines = int(row.get("LINEAS PENDIENTES VENCIDAS", 0))
    if ordered_qty <= 0:
        return "Pendiente"
    if delivered_qty >= ordered_qty:
        return "Entregado"
    if overdue_lines > 0:
        return "Retrasado"
    if delivered_qty > 0:
        return "Parcial"
    return "Pendiente"


def format_date_value(value):
    date_value = pd.to_datetime(value, errors="coerce")
    return "" if pd.isna(date_value) else date_value.strftime("%Y-%m-%d")


def format_cross_table(cross_df):
    if cross_df is None or cross_df.empty:
        return pd.DataFrame(columns=MATERIAL_STATUS_CROSS_COLUMNS)
    result_df = cross_df.copy()
    for column in ["PRIMERA FECHA SOL.", "ULTIMA FECHA PED.", "FECHA ENTREGA PROXIMA", "FECHA ENTREGA ULTIMA"]:
        if column in result_df.columns:
            result_df[column] = result_df[column].apply(format_date_value)
    result_df["COBERTURA COMPRA"] = result_df["COBERTURA COMPRA"].apply(lambda value: format_decimal(float(value) * 100, 1) + " %")
    for column in ["PRECIO UNITARIO MEDIO", "PRECIO UNITARIO ULTIMO", "COSTE LM ESTIMADO", "COSTE PEDIDO"]:
        result_df[column] = result_df[column].apply(format_currency)
    for column in ["CANTIDAD LM", "CANTIDAD PEDIDA", "CANTIDAD ENTREGADA", "CANTIDAD PENDIENTE"]:
        result_df[column] = result_df[column].apply(lambda value: format_decimal(value, 3))
    for column in MATERIAL_STATUS_CROSS_COLUMNS:
        if column not in result_df.columns:
            result_df[column] = "NOT AVAILABLE"
    return result_df[MATERIAL_STATUS_CROSS_COLUMNS].fillna("NOT AVAILABLE")


def build_incidents_table(cross_df):
    rows = []
    if cross_df is None or cross_df.empty:
        return pd.DataFrame(columns=["CODIGO MATERIAL", "Incidencia", "Detalle", "Prioridad"])
    for _, row in cross_df.iterrows():
        material = str(row.get("CODIGO MATERIAL", ""))
        if str(row.get("MATERIAL_STATUS_ENCONTRADO", "NO")) != "SI":
            rows.append({"CODIGO MATERIAL": material, "Incidencia": "Material LM no encontrado en Material Status", "Detalle": "El material existe en las LMs del elemento seleccionado pero no aparece en el fichero Material Status.", "Prioridad": "Alta"})
        if str(row.get("MATERIAL_STATUS_ENCONTRADO", "NO")) == "SI" and float(row.get("PRECIO UNITARIO MEDIO", 0)) <= 0:
            rows.append({"CODIGO MATERIAL": material, "Incidencia": "Material sin precio calculable", "Detalle": "Existe en Material Status pero Imp. unitario Ped. o Cant Base Ped. no permiten calcular precio unitario.", "Prioridad": "Alta"})
        if str(row.get("VARIOS PRECIOS", "NO")) == "SI":
            rows.append({"CODIGO MATERIAL": material, "Incidencia": "Material con varios precios", "Detalle": f"Precios distintos detectados: {int(row.get('Nº PRECIOS DISTINTOS', 0))}. Se usa precio medio ponderado para coste de módulo.", "Prioridad": "Media"})
        if str(row.get("ESTADO COMPRA", "")) in ["Sin compra", "Parcial"]:
            rows.append({"CODIGO MATERIAL": material, "Incidencia": "Cantidad comprada insuficiente", "Detalle": f"Cantidad LM: {row.get('CANTIDAD LM', 0)}. Cantidad pedida: {row.get('CANTIDAD PEDIDA', 0)}.", "Prioridad": "Alta"})
        if str(row.get("ESTADO ENTREGA", "")) == "Retrasado":
            rows.append({"CODIGO MATERIAL": material, "Incidencia": "Entrega pendiente vencida", "Detalle": "Hay líneas pendientes con fecha de entrega anterior a hoy.", "Prioridad": "Alta"})
    return pd.DataFrame(rows)


def get_material_status_metrics_for_pbs(df, selected_code):
    try:
        cross_df, incidents_df, ms_df, metrics, log_lines = build_material_status_cross_for_selected_code(df, selected_code)
        return metrics
    except Exception as error:
        return {"source_loaded": bool(get_material_status_source_path()), "error": str(error), "precio_modulo": 0.0, "materiales_totales": 0, "materiales_encontrados": 0, "materiales_no_encontrados": 0, "materiales_con_precio": 0, "materiales_sin_precio": 0}


def render_material_status_table(table_df, height=520):
    if table_df is None or table_df.empty:
        st.info("No hay datos para mostrar.")
        return
    grid_builder = GridOptionsBuilder.from_dataframe(table_df)
    grid_builder.configure_default_column(filter=True, sortable=True, resizable=True, editable=False)
    for column in table_df.columns:
        min_width = 220 if column in ["DESCRIPCION LM", "Descripción material", "Detalle", "Proveedor", "Elemento PEP", "LM_DOCS"] else 140
        grid_builder.configure_column(column, minWidth=min_width)
    auto_size_code = JsCode("function(params) { setTimeout(function() { params.api.autoSizeAllColumns(false); }, 500); setTimeout(function() { params.api.autoSizeAllColumns(false); }, 1200); }")
    grid_builder.configure_grid_options(domLayout="normal", onGridReady=auto_size_code, onFirstDataRendered=auto_size_code)
    AgGrid(table_df, gridOptions=grid_builder.build(), height=height, fit_columns_on_grid_load=False, allow_unsafe_jscode=True)


def render_material_status_source_selector():
    st.markdown("### Fichero Material Status")
    uploaded_file = st.file_uploader("Buscar fichero Material Status", type=["xlsx", "xlsm", "xls"], key="material_status_file_uploader")
    load_clicked = st.button("Cargar Material Status", key="material_status_load_button")
    if load_clicked:
        if uploaded_file is None:
            st.warning("Selecciona un fichero Excel de Material Status antes de cargar.")
        else:
            file_bytes = uploaded_file.getvalue()
            st.session_state["material_status_uploaded_name"] = uploaded_file.name
            st.session_state["material_status_uploaded_bytes"] = file_bytes
            st.session_state["material_status_uploaded_size"] = len(file_bytes)
            st.session_state["material_status_loaded_at"] = pd.Timestamp.now().isoformat()
    source_name = get_material_status_source_path()
    if not source_name:
        st.warning("Busca un fichero Excel de Material Status y pulsa Cargar Material Status para cruzar precios, pedidos y entregas.")
        return "", load_clicked
    st.success(f"Material Status activo: {source_name}")
    if uploaded_file is not None and uploaded_file.name != str(st.session_state.get("material_status_uploaded_name", "")).strip():
        st.caption("Hay un fichero seleccionado en el buscador que todavía no está cargado. Pulsa Cargar Material Status para activarlo.")
    return source_name, load_clicked


def render_material_status_metrics(metrics):
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Precio módulo", format_currency(metrics.get("precio_modulo", 0)))
    col2.metric("Materiales totales", metrics.get("materiales_totales", 0))
    col3.metric("Encontrados MS", metrics.get("materiales_encontrados", 0))
    col4.metric("No encontrados MS", metrics.get("materiales_no_encontrados", 0))
    col5.metric("Con precio", metrics.get("materiales_con_precio", 0))
    col6.metric("Sin precio", metrics.get("materiales_sin_precio", 0))


def build_material_status_detail_table(ms_df):
    if ms_df is None or ms_df.empty:
        return pd.DataFrame(columns=MATERIAL_STATUS_DETAIL_COLUMNS)
    result_df = ms_df.copy()
    result_df["Precio unitario real"] = result_df["Precio unitario real"].apply(format_currency)
    result_df["Importe línea calculado"] = result_df["Importe línea calculado"].apply(format_currency)
    for column in MATERIAL_STATUS_DATE_COLUMNS:
        if f"{column} Date" in result_df.columns:
            result_df[column] = result_df[f"{column} Date"].apply(format_date_value)
    for column in ["Ctd. pedido", "Imp. unitario Ped.", "Cant Base Ped."]:
        if column in result_df.columns:
            result_df[column] = result_df[column].fillna("NOT AVAILABLE").astype(str)
    for column in MATERIAL_STATUS_DETAIL_COLUMNS:
        if column not in result_df.columns:
            result_df[column] = "NOT AVAILABLE"
    return result_df[MATERIAL_STATUS_DETAIL_COLUMNS].fillna("NOT AVAILABLE")


def render_material_status_log(log_lines):
    st.markdown("### Log de Material Status")
    available_levels = ["OK", "INFO", "WARNING", "ERROR", "OTROS"]
    default_levels = ["WARNING", "ERROR"]
    selected_levels = st.multiselect("Mostrar tipos de mensaje", options=available_levels, default=default_levels, key="material_status_log_levels")
    if not log_lines:
        st.text_area("Detalle", value="Sin mensajes.", height=180, disabled=True)
        return
    filtered_log_lines = []
    level_counts = {level: 0 for level in available_levels}
    for line in log_lines:
        line_text = str(line)
        detected_level = "OTROS"
        for level in ["OK", "INFO", "WARNING", "ERROR"]:
            if line_text.startswith(f"[{level}]"):
                detected_level = level
                break
        level_counts[detected_level] += 1
        if detected_level in selected_levels:
            filtered_log_lines.append(line_text)
    summary_text = " | ".join([f"{level}: {level_counts.get(level, 0)}" for level in available_levels])
    st.caption(summary_text)
    if not filtered_log_lines:
        st.text_area("Detalle", value="No hay mensajes para los tipos seleccionados.", height=220, disabled=True)
        return
    st.text_area("Detalle", value="\n".join(filtered_log_lines), height=220, disabled=True)


def render_material_status(df, selected_code):
    selected_row = get_main_element_row(df, selected_code)
    if selected_row is None:
        st.warning("No hay elemento HW seleccionado.")
        return
    selected_code_value = selected_row.get("code", "")
    selected_component = selected_row.get("component", "")
    st.subheader(f"Material Status - {selected_code_value} - {selected_component}")
    source_name, load_clicked = render_material_status_source_selector()
    if not source_name:
        return
    if load_clicked:
        progress_bar = st.progress(0)
        status_box = st.empty()
        status_box.info("Iniciando carga de Material Status...")
        cross_df, incidents_df, ms_df, metrics, log_lines = build_material_status_cross_for_selected_code(df, selected_code, progress_bar, status_box)
        progress_bar.progress(100)
        status_box.success("Material Status cargado y cruzado correctamente.")
    else:
        with st.spinner("Cruzando LMs con Material Status..."):
            cross_df, incidents_df, ms_df, metrics, log_lines = build_material_status_cross_for_selected_code(df, selected_code)
    render_material_status_metrics(metrics)
    st.caption("El coste del módulo se calcula cruzando CODIGO MATERIAL de las LMs contra Material del fichero Material Status y usando CANTIDAD LM * Precio unitario real.")
    tab_summary, tab_materials, tab_detail, tab_incidents, tab_log = st.tabs(["Resumen", "Materiales del elemento", "Detalle SAP", "Incidencias", "Log de carga"])
    with tab_summary:
        summary_rows = [{"Concepto": "Precio por módulo", "Valor": format_currency(metrics.get("precio_modulo", 0))}, {"Concepto": "Materiales totales en LMs", "Valor": metrics.get("materiales_totales", 0)}, {"Concepto": "Materiales encontrados en Material Status", "Valor": metrics.get("materiales_encontrados", 0)}, {"Concepto": "Materiales no encontrados en Material Status", "Valor": metrics.get("materiales_no_encontrados", 0)}, {"Concepto": "Materiales con precio", "Valor": metrics.get("materiales_con_precio", 0)}, {"Concepto": "Materiales sin precio", "Valor": metrics.get("materiales_sin_precio", 0)}, {"Concepto": "Materiales pendientes/parciales/retrasados", "Valor": metrics.get("materiales_pendientes", 0)}, {"Concepto": "Materiales entregados", "Valor": metrics.get("materiales_entregados", 0)}, {"Concepto": "Líneas Material Status usadas", "Valor": metrics.get("lineas_material_status", 0)}]
        st.dataframe(style_dark_dataframe(pd.DataFrame(summary_rows)), width="stretch", hide_index=True)
    with tab_materials:
        render_material_status_table(cross_df, 560)
    with tab_detail:
        render_material_status_table(build_material_status_detail_table(ms_df), 560)
    with tab_incidents:
        render_material_status_table(incidents_df, 520)
    with tab_log:
        render_material_status_log(log_lines)
