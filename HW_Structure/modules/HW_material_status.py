# Modulo principal Material Status. Carga una vez el fichero SAP, cachea su procesamiento y cruza de forma ligera con las LMs segun la seleccion del sidebar.

from pathlib import Path
from io import BytesIO
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from HW_scanner import get_main_element_row
from modules.HW_LMs import build_lm_file_signature, get_lm_files_for_selected_code, load_lm_materials_cached
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode, GridUpdateMode, DataReturnMode

CHART_PALETTE = {"azul_oscuro": "#001923", "turquesa": "#00B0BD", "gris_ceramica": "#E3E2DA", "azul_amazonico": "#004254", "texto_claro": "#E3E2DA", "texto_oscuro": "#001923", "grid": "rgba(227,226,218,0.18)"}
CHART_COLOR_SEQUENCE = ["#00B0BD", "#33C2CD", "#66D0D6", "#0097A7", "#26AAB5", "#4DBCC4", "#7BCFD4", "#5E7F8A", "#6F909A", "#80A1AA", "#91B2BA", "#A3C2C9", "#8FA3AA", "#9FB2B8", "#AFC1C6", "#BFCFD3", "#C9D4D6", "#B8C5C8", "#A7B6BA", "#96A8AD"]

MATERIAL_STATUS_REQUIRED_COLUMNS = ["Material", "Descripción material", "Nº Cesta / Sol", "Fecha Sol.", "Nº pedido", "Fecha Ped.", "Elemento PEP", "Fe. Entrega", "Entrega final", "Ctd. pedido", "Imp. unitario Ped.", "Cant Base Ped."]
MATERIAL_STATUS_OPTIONAL_COLUMNS = ["Posición sol.", "Posición ped.", "Desc.Proveedor", "Solic.", "Comprador", "Ctd. Solicitada", "Ctd. por recepcionar", "Ctd. Aceptada", "Ctd. Rechazada", "Imp.total pos SP", "Imp.total pos Ped", "Centro", "Almacen", "Estado", "Moneda Ped.", "Unidad", "Tipo Compra"]
MATERIAL_STATUS_NUMERIC_COLUMNS = ["Ctd. pedido", "Imp. unitario Ped.", "Cant Base Ped.", "Ctd. Solicitada", "Imp.total pos Ped", "Imp.total pos SP"]
MATERIAL_STATUS_DATE_COLUMNS = ["Fecha Sol.", "Fecha Ped.", "Fe. Entrega"]
MATERIAL_STATUS_DETAIL_COLUMNS = ["Nº", "Material", "Lista de materiales", "Tipo pedido", "Descripción material", "Precio total", "Nº Cesta / Sol", "Fecha Sol.", "Nº pedido", "Fecha Ped.", "Elemento PEP", "Desc.Proveedor", "Fe. Entrega", "Ctd. Solicitada", "Ctd. pedido", "Entrega final", "Almacen", "Imp. unitario Ped.", "Cant Base Ped.", "Precio unitario real", "Importe línea calculado", "Estado entrega", "CODIGO MATERIAL", "DESCRIPCION LM", "CANTIDAD LM", "ESTADO COMPRA", "ESTADO ENTREGA"]
MATERIAL_STATUS_CROSS_COLUMNS = ["Material", "Lista de materiales", "Descripción material", "Desc.Proveedor", "Ctd. Solicitada", "Precio unitario", "Precio total", "CODIGO MATERIAL", "DESCRIPCION LM", "CANTIDAD LM", "CANTIDAD PEDIDA", "CANTIDAD ENTREGADA", "CANTIDAD PENDIENTE", "COBERTURA COMPRA", "ESTADO COMPRA", "ESTADO ENTREGA", "PRECIO UNITARIO MEDIO", "PRECIO UNITARIO ULTIMO", "COSTE LM ESTIMADO", "COSTE PEDIDO", "Nº PEDIDOS", "Nº CESTAS/SOLPEDS", "PRIMERA FECHA SOL.", "ULTIMA FECHA PED.", "FECHA ENTREGA PROXIMA", "FECHA ENTREGA ULTIMA", "Elemento PEP", "Proveedor", "VARIOS PRECIOS", "Nº PRECIOS DISTINTOS", "LM_DOCS"]
MATERIALS_ELEMENT_DEFAULT_COLUMNS = ["Material", "Lista de materiales", "Descripción material", "Desc.Proveedor", "Ctd. Solicitada", "Precio unitario", "Precio total"]
MATERIAL_STATUS_DETAIL_DEFAULT_COLUMNS = ["Nº", "Material", "Lista de materiales", "Tipo pedido", "Descripción material", "Precio total", "Nº Cesta / Sol", "Fecha Sol.", "Nº pedido", "Fecha Ped.", "Elemento PEP", "Desc.Proveedor", "Fe. Entrega", "Ctd. Solicitada", "Ctd. pedido", "Entrega final", "Precio unitario real", "ESTADO COMPRA", "ESTADO ENTREGA"]
MATERIAL_STATUS_INCIDENTS_DEFAULT_COLUMNS = ["CODIGO MATERIAL", "Incidencia", "Detalle", "Prioridad"]


def normalize_column_name(value):
    text = "" if value is None else str(value)
    text = text.replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def normalize_purchase_order_prefix(value):
    text = "" if value is None else str(value).replace("\xa0", " ").strip()
    if text.lower() in ["", "nan", "none", "not available"]:
        return ""
    digits = re.sub(r"\D", "", text)
    return digits[:2] if len(digits) >= 2 else ""


def classify_purchase_order_type(value):
    prefix = normalize_purchase_order_prefix(value)
    order_types = {"46": "PO Hitos", "42": "PO Materiales", "43": "PO Servicios", "41": "PO Inversión", "48": "PO Punchout", "44": "PO Servicios Abiertos", "45": "PO Leasing"}
    if not prefix:
        return "NOT AVAILABLE"
    return order_types.get(prefix, "Otros")


def clean_material_text(value):
    if value is None:
        return ""
    text = str(value).replace("\xa0", " ").strip().upper()
    if text.lower() in ["", "nan", "none", "not available"]:
        return ""
    while text.startswith("'"):
        text = text[1:].strip()
    return text


def expand_scientific_material_text(text):
    clean_text = str(text).replace(" ", "").replace(",", ".")
    if not re.match(r"^[+-]?\d+(\.\d+)?[E][+-]?\d+$", clean_text):
        return text
    try:
        number = Decimal(clean_text)
        return format(number.quantize(Decimal("1"), rounding=ROUND_HALF_UP), "f")
    except (InvalidOperation, ValueError, OverflowError):
        return text


def normalize_material_display(value):
    text = clean_material_text(value)
    if not text:
        return ""
    text = expand_scientific_material_text(text)
    text = text.replace(",", ".")
    if re.match(r"^\d+\.0$", text):
        return text[:-2]
    return text


def normalize_material_key(value):
    display_value = normalize_material_display(value)
    if not display_value:
        return ""
    text = str(display_value).replace("\xa0", " ").strip().upper()
    text = re.sub(r"\s+", "", text)
    text = text.replace(",", ".")
    if re.match(r"^\d+\.00$", text):
        return text.split(".", 1)[0]
    if re.match(r"^\d+\.0$", text):
        return text.split(".", 1)[0]
    return text


def material_keys_match(lm_key, ms_key):
    lm_text = normalize_material_key(lm_key)
    ms_text = normalize_material_key(ms_key)
    if not lm_text or not ms_text:
        return False
    if lm_text == ms_text:
        return True
    if len(lm_text) >= 8 and lm_text in ms_text:
        return True
    if len(ms_text) >= 8 and ms_text in lm_text:
        return True
    return False


def format_material_for_excel_csv(value):
    display_value = normalize_material_display(value)
    if re.match(r"^\d{10,}(\.\d+)?$", display_value):
        return f'="{display_value}"'
    return display_value


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
    return f"{number:,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_date_value(value):
    date_value = pd.to_datetime(value, errors="coerce")
    return "" if pd.isna(date_value) else date_value.strftime("%Y-%m-%d")


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
        return {"mode": "uploaded", "display_name": uploaded_name, "file_bytes": uploaded_bytes, "file_size": int(st.session_state.get("material_status_uploaded_size", len(uploaded_bytes))), "signature": f"uploaded|{uploaded_name}|{int(st.session_state.get('material_status_uploaded_size', len(uploaded_bytes)))}|{st.session_state.get('material_status_loaded_at', '')}"}
    path = str(st.session_state.get("material_status_file_path", "")).strip()
    if path and Path(path).exists() and Path(path).is_file():
        file_mtime_ns, file_size = get_material_status_cache_stamp(path)
        return {"mode": "path", "display_name": path, "file_path": path, "file_mtime_ns": file_mtime_ns, "file_size": file_size, "signature": f"path|{path}|{file_mtime_ns}|{file_size}"}
    return {"mode": "none", "display_name": "", "file_size": 0, "signature": "none"}


def clear_material_status_selection_cache():
    st.session_state["material_status_selection_cache"] = {}
    st.session_state["material_status_detail_cache"] = {}
    st.session_state["material_status_view_cache"] = {}

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
    return prepare_material_status_dataframe(raw_df, f"Hoja: {best_sheet}", log_lines)


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
    return prepare_material_status_dataframe(raw_df, f"Fichero: {file_name}. Hoja: {best_sheet}", log_lines)


def prepare_material_status_dataframe(raw_df, source_label, log_lines):
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
    result_df["Material"] = result_df["Material"].apply(normalize_material_display)
    result_df["Material"] = result_df["Material"].apply(lambda value: value if str(value).strip() else "NOT AVAILABLE")
    result_df["Tipo pedido"] = result_df["Nº pedido"].apply(classify_purchase_order_type)
    empty_material_mask = result_df["Material Key"].astype(str).str.strip() == ""
    if empty_material_mask.any():
        result_df.loc[empty_material_mask, "Material Key"] = [f"__MS_SIN_CODIGO_{index + 1:08d}" for index in range(int(empty_material_mask.sum()))]
        log_lines.append(f"[INFO] Líneas sin código de material conservadas en Material Status: {int(empty_material_mask.sum())}.")
    for column in MATERIAL_STATUS_NUMERIC_COLUMNS:
        result_df[f"{column} Num"] = result_df[column].apply(parse_number)
    for column in MATERIAL_STATUS_DATE_COLUMNS:
        result_df[f"{column} Date"] = result_df[column].apply(parse_date)
    result_df["Precio unitario real"] = result_df.apply(lambda row: row["Imp. unitario Ped. Num"] / row["Cant Base Ped. Num"] if row["Cant Base Ped. Num"] else 0.0, axis=1)
    result_df["Importe línea calculado auxiliar"] = result_df["Ctd. pedido Num"] * result_df["Precio unitario real"]
    result_df["Importe línea calculado"] = result_df.apply(lambda row: row["Imp.total pos Ped Num"] if "Imp.total pos Ped Num" in result_df.columns and row["Imp.total pos Ped Num"] != 0 else row["Importe línea calculado auxiliar"], axis=1)
    result_df["Entrega final normalizada"] = result_df["Entrega final"].fillna("").astype(str).str.strip().str.upper()
    result_df["Estado entrega"] = result_df["Entrega final normalizada"].apply(lambda value: "Entregado" if value == "X" else "Pendiente")
    log_lines.append(f"[OK] Material Status cargado correctamente. {source_label}. Líneas procesadas: {len(result_df)}.")
    return result_df, log_lines


def load_material_status_dataframe(progress_bar=None, status_box=None, force_reload=False):
    source = get_material_status_active_source()
    if source.get("mode") == "none":
        return pd.DataFrame(), ["[INFO] No hay fichero Material Status cargado."]
    if not force_reload and st.session_state.get("material_status_active_signature", "") == source.get("signature", "") and "material_status_active_df" in st.session_state:
        return st.session_state.get("material_status_active_df", pd.DataFrame()).copy(), list(st.session_state.get("material_status_active_log_lines", []))
    if progress_bar is not None:
        progress_bar.progress(25)
    if status_box is not None:
        status_box.info(f"Leyendo fichero Material Status: {source.get('display_name', '')}")
    if source.get("mode") == "uploaded":
        result_df, log_lines = read_material_status_excel_bytes_cached(source.get("display_name", ""), source.get("file_bytes", b""), int(source.get("file_size", 0)))
    else:
        result_df, log_lines = read_material_status_excel_cached(source.get("file_path", ""), int(source.get("file_mtime_ns", 0)), int(source.get("file_size", 0)))
    st.session_state["material_status_active_signature"] = source.get("signature", "")
    st.session_state["material_status_active_source_name"] = source.get("display_name", "")
    st.session_state["material_status_active_df"] = result_df.copy()
    st.session_state["material_status_active_log_lines"] = list(log_lines)
    clear_material_status_selection_cache()
    if progress_bar is not None:
        progress_bar.progress(55)
    return result_df.copy(), list(log_lines)


def ensure_material_status_processed(progress_bar=None, status_box=None, force_reload=False):
    source = get_material_status_active_source()
    if source.get("mode") == "none":
        return pd.DataFrame(), pd.DataFrame(), ["[INFO] No hay fichero Material Status cargado."], "none"
    if not force_reload and st.session_state.get("material_status_processed_signature", "") == source.get("signature", "") and "material_status_active_df" in st.session_state and "material_status_active_agg_df" in st.session_state:
        return st.session_state.get("material_status_active_df", pd.DataFrame()).copy(), st.session_state.get("material_status_active_agg_df", pd.DataFrame()).copy(), list(st.session_state.get("material_status_active_log_lines", [])), source.get("signature", "")
    ms_df, log_lines = load_material_status_dataframe(progress_bar, status_box, force_reload)
    if status_box is not None:
        status_box.info("Agrupando Material Status por material...")
    if progress_bar is not None:
        progress_bar.progress(70)
    ms_agg_df = aggregate_material_status(ms_df)
    st.session_state["material_status_processed_signature"] = source.get("signature", "")
    st.session_state["material_status_active_agg_df"] = ms_agg_df.copy()
    return ms_df.copy(), ms_agg_df.copy(), list(log_lines), source.get("signature", "")


def get_lm_materials_for_selected_code(df, selected_code):
    root_path = st.session_state.get("root_path", "")
    lm_files = get_lm_files_for_selected_code(df, selected_code, root_path)
    lm_file_signature = build_lm_file_signature(lm_files) if lm_files else tuple()
    if not lm_files:
        return pd.DataFrame(), ["[INFO] El elemento seleccionado no tiene LMs detectadas."], {"total_lm_files": 0, "loaded_lm_files": 0}, lm_file_signature
    materials_df, export_missing_df, read_log_lines, unreadable_files, metrics = load_lm_materials_cached(lm_file_signature)
    return materials_df, read_log_lines, metrics, lm_file_signature


def aggregate_lm_materials(materials_df):
    if materials_df is None or materials_df.empty or "CODIGO MATERIAL" not in materials_df.columns:
        return pd.DataFrame(columns=["MATERIAL_KEY", "CODIGO MATERIAL", "DESCRIPCION LM", "CANTIDAD LM", "LM_DOCS"])
    result_df = materials_df.copy()
    result_df["MATERIAL_KEY"] = result_df["CODIGO MATERIAL"].apply(normalize_material_key)
    result_df["CODIGO MATERIAL DISPLAY"] = result_df["CODIGO MATERIAL"].apply(normalize_material_display)
    result_df = result_df[result_df["MATERIAL_KEY"] != ""].copy()
    if result_df.empty:
        return pd.DataFrame(columns=["MATERIAL_KEY", "CODIGO MATERIAL", "DESCRIPCION LM", "CANTIDAD LM", "LM_DOCS"])
    result_df["CANTIDAD LM NUM"] = result_df["CANTIDAD"].apply(parse_number) if "CANTIDAD" in result_df.columns else 0.0
    grouped_rows = []
    for material_key, group in result_df.groupby("MATERIAL_KEY", dropna=False):
        grouped_rows.append({"MATERIAL_KEY": material_key, "CODIGO MATERIAL": join_unique_values(group["CODIGO MATERIAL DISPLAY"].tolist(), 1), "DESCRIPCION LM": join_unique_values(group["DESCRIPCION"].tolist(), 2) if "DESCRIPCION" in group.columns else "NOT AVAILABLE", "CANTIDAD LM": float(group["CANTIDAD LM NUM"].sum()), "LM_DOCS": join_unique_values(group["LM_DOC"].tolist(), 6) if "LM_DOC" in group.columns else "NIL"})
    return pd.DataFrame(grouped_rows)


def aggregate_material_status(ms_df):
    if ms_df is None or ms_df.empty:
        return pd.DataFrame(columns=["MATERIAL_KEY"])
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
        grouped_rows.append({"MATERIAL_KEY": material_key, "Tipo pedido": join_unique_values(group["Tipo pedido"].tolist(), 4) if "Tipo pedido" in group.columns else "NOT AVAILABLE", "Descripción material": join_unique_values(group["Descripción material"].tolist(), 2), "CANTIDAD PEDIDA": float(group["Ctd. pedido Num"].sum()), "Ctd. Solicitada": float(group["Ctd. Solicitada Num"].sum()) if "Ctd. Solicitada Num" in group.columns else 0.0, "CANTIDAD ENTREGADA": float(delivered_group["Ctd. pedido Num"].sum()) if not delivered_group.empty else 0.0, "CANTIDAD PENDIENTE": float(pending_group["Ctd. pedido Num"].sum()) if not pending_group.empty else 0.0, "PRECIO UNITARIO MEDIO": weighted_price, "PRECIO UNITARIO ULTIMO": last_price, "COSTE PEDIDO": float(group["Importe línea calculado"].sum()), "Nº PEDIDOS": int(group["Nº pedido"].replace("NOT AVAILABLE", pd.NA).dropna().nunique()), "Nº CESTAS/SOLPEDS": int(group["Nº Cesta / Sol"].replace("NOT AVAILABLE", pd.NA).dropna().nunique()), "PRIMERA FECHA SOL.": group["Fecha Sol. Date"].min(), "ULTIMA FECHA PED.": group["Fecha Ped. Date"].max(), "FECHA ENTREGA PROXIMA": next_delivery, "FECHA ENTREGA ULTIMA": group["Fe. Entrega Date"].max(), "Elemento PEP": join_unique_values(group["Elemento PEP"].tolist(), 4), "Proveedor": join_unique_values(group["Desc.Proveedor"].tolist(), 3), "VARIOS PRECIOS": "SI" if len(price_values) > 1 else "NO", "Nº PRECIOS DISTINTOS": len(price_values), "LINEAS MATERIAL STATUS": len(group), "LINEAS PENDIENTES VENCIDAS": overdue_count})
    return pd.DataFrame(grouped_rows)

def build_fallback_material_status_agg(ms_df, ms_agg_df, lm_agg_df):
    if ms_df is None or ms_df.empty or lm_agg_df is None or lm_agg_df.empty:
        return pd.DataFrame(columns=ms_agg_df.columns if ms_agg_df is not None and not ms_agg_df.empty else ["MATERIAL_KEY"])
    exact_keys = set(ms_agg_df["MATERIAL_KEY"].dropna().astype(str).tolist()) if ms_agg_df is not None and not ms_agg_df.empty and "MATERIAL_KEY" in ms_agg_df.columns else set()
    fallback_rows = []
    unmatched_lm_keys = [key for key in lm_agg_df["MATERIAL_KEY"].dropna().astype(str).tolist() if key not in exact_keys]
    for lm_key in unmatched_lm_keys:
        matched_df = ms_df[ms_df["Material Key"].apply(lambda ms_key: material_keys_match(lm_key, ms_key))].copy()
        if matched_df.empty:
            continue
        matched_df["Material Key"] = lm_key
        agg_df = aggregate_material_status(matched_df)
        if not agg_df.empty:
            fallback_rows.append(agg_df.iloc[0].to_dict())
    return pd.DataFrame(fallback_rows)


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


def complete_cross_dataframe(cross_df):
    for column in ["CANTIDAD PEDIDA", "Ctd. Solicitada", "CANTIDAD ENTREGADA", "CANTIDAD PENDIENTE", "PRECIO UNITARIO MEDIO", "PRECIO UNITARIO ULTIMO", "COSTE PEDIDO", "Nº PEDIDOS", "Nº CESTAS/SOLPEDS", "Nº PRECIOS DISTINTOS", "LINEAS MATERIAL STATUS", "LINEAS PENDIENTES VENCIDAS"]:
        if column not in cross_df.columns:
            cross_df[column] = 0
        cross_df[column] = cross_df[column].fillna(0)
    cross_df["MATERIAL_STATUS_ENCONTRADO"] = cross_df["Descripción material"].fillna("").astype(str).apply(lambda value: "SI" if value.strip() and value.strip().lower() != "nan" else "NO") if "Descripción material" in cross_df.columns else "NO"
    cross_df["COBERTURA COMPRA"] = cross_df.apply(lambda row: row["CANTIDAD PEDIDA"] / row["CANTIDAD LM"] if row["CANTIDAD LM"] else 0.0, axis=1)
    cross_df["ESTADO COMPRA"] = cross_df.apply(calculate_purchase_status, axis=1)
    cross_df["ESTADO ENTREGA"] = cross_df.apply(calculate_delivery_status, axis=1)
    cross_df["COSTE LM ESTIMADO"] = cross_df["CANTIDAD LM"] * cross_df["PRECIO UNITARIO MEDIO"]
    for column in ["Descripción material", "Elemento PEP", "Proveedor"]:
        if column not in cross_df.columns:
            cross_df[column] = "NOT AVAILABLE"
        cross_df[column] = cross_df[column].fillna("NOT AVAILABLE")
    if "VARIOS PRECIOS" not in cross_df.columns:
        cross_df["VARIOS PRECIOS"] = "NO"
    cross_df["VARIOS PRECIOS"] = cross_df["VARIOS PRECIOS"].fillna("NO")
    return cross_df


def build_material_status_cross_for_selected_code(df, selected_code, progress_bar=None, status_box=None, force_reload=False):
    source = get_material_status_active_source()
    if source.get("mode") == "none":
        empty_metrics = {"source_loaded": False, "precio_modulo": 0.0, "materiales_totales": 0, "materiales_encontrados": 0, "materiales_no_encontrados": 0, "materiales_con_precio": 0, "materiales_sin_precio": 0, "materiales_pendientes": 0, "materiales_entregados": 0, "lineas_material_status": 0}
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), empty_metrics, ["[INFO] No hay fichero Material Status cargado."]
    if progress_bar is not None:
        progress_bar.progress(5)
    if status_box is not None:
        status_box.info("Cargando LMs del elemento seleccionado...")
    materials_df, lm_log_lines, lm_metrics, lm_file_signature = get_lm_materials_for_selected_code(df, selected_code)
    cache_key = repr((str(selected_code), source.get("signature", ""), lm_file_signature))
    selection_cache = st.session_state.setdefault("material_status_selection_cache", {})
    if not force_reload and cache_key in selection_cache:
        cached = selection_cache[cache_key]
        return cached["cross_df"].copy(), cached["incidents_df"].copy(), cached["ms_df"].copy(), dict(cached["metrics"]), list(cached["log_lines"])
    if progress_bar is not None:
        progress_bar.progress(20)
    if status_box is not None:
        status_box.info("Agrupando materiales de LMs...")
    lm_agg_df = aggregate_lm_materials(materials_df)
    ms_df, ms_agg_df, ms_log_lines, source_signature = ensure_material_status_processed(progress_bar, status_box, force_reload)
    if lm_agg_df.empty:
        empty_metrics = {"source_loaded": True, "precio_modulo": 0.0, "materiales_totales": 0, "materiales_encontrados": 0, "materiales_no_encontrados": 0, "materiales_con_precio": 0, "materiales_sin_precio": 0, "materiales_pendientes": 0, "materiales_entregados": 0, "lineas_material_status": 0}
        result = (pd.DataFrame(), pd.DataFrame(), ms_df, empty_metrics, lm_log_lines + ms_log_lines)
        return result
    if progress_bar is not None:
        progress_bar.progress(82)
    if status_box is not None:
        status_box.info("Cruzando Material Status cacheado con LMs del elemento seleccionado...")
    fallback_agg_df = build_fallback_material_status_agg(ms_df, ms_agg_df, lm_agg_df)
    effective_ms_agg_df = pd.concat([ms_agg_df, fallback_agg_df], ignore_index=True) if fallback_agg_df is not None and not fallback_agg_df.empty else ms_agg_df.copy()
    if effective_ms_agg_df.empty:
        cross_df = lm_agg_df.copy()
        cross_df["MATERIAL_STATUS_ENCONTRADO"] = "NO"
        cross_df["COSTE LM ESTIMADO"] = 0.0
        metrics = {"source_loaded": True, "precio_modulo": 0.0, "materiales_totales": len(cross_df), "materiales_encontrados": 0, "materiales_no_encontrados": len(cross_df), "materiales_con_precio": 0, "materiales_sin_precio": len(cross_df), "materiales_pendientes": 0, "materiales_entregados": 0, "lineas_material_status": 0}
    else:
        cross_df = lm_agg_df.merge(effective_ms_agg_df, on="MATERIAL_KEY", how="left")
        cross_df = complete_cross_dataframe(cross_df)
        metrics = {"source_loaded": True, "precio_modulo": float(cross_df["COSTE LM ESTIMADO"].sum()), "materiales_totales": int(len(cross_df)), "materiales_encontrados": int((cross_df["MATERIAL_STATUS_ENCONTRADO"] == "SI").sum()), "materiales_no_encontrados": int((cross_df["MATERIAL_STATUS_ENCONTRADO"] != "SI").sum()), "materiales_con_precio": int(((cross_df["PRECIO UNITARIO MEDIO"] > 0) & (cross_df["MATERIAL_STATUS_ENCONTRADO"] == "SI")).sum()), "materiales_sin_precio": int(((cross_df["PRECIO UNITARIO MEDIO"] <= 0) | (cross_df["MATERIAL_STATUS_ENCONTRADO"] != "SI")).sum()), "materiales_pendientes": int(cross_df["ESTADO ENTREGA"].isin(["Pendiente", "Parcial", "Retrasado"]).sum()), "materiales_entregados": int((cross_df["ESTADO ENTREGA"] == "Entregado").sum()), "lineas_material_status": int(cross_df["LINEAS MATERIAL STATUS"].sum())}
    raw_cross_df = cross_df.copy()
    formatted_cross_df = format_cross_table(raw_cross_df)
    incidents_df = build_incidents_table(raw_cross_df)
    log_lines = lm_log_lines + ms_log_lines + [f"[OK] Cruce Material Status completado para {selected_code}. Materiales LM: {metrics.get('materiales_totales', 0)}. Encontrados: {metrics.get('materiales_encontrados', 0)}. No encontrados: {metrics.get('materiales_no_encontrados', 0)}."]
    selection_cache[cache_key] = {"cross_df": formatted_cross_df.copy(), "incidents_df": incidents_df.copy(), "ms_df": ms_df.copy(), "metrics": dict(metrics), "log_lines": list(log_lines)}
    if progress_bar is not None:
        progress_bar.progress(95)
    return formatted_cross_df, incidents_df, ms_df, metrics, log_lines


def format_cross_table(cross_df):
    if cross_df is None or cross_df.empty:
        return pd.DataFrame(columns=MATERIAL_STATUS_CROSS_COLUMNS)
    result_df = cross_df.copy()
    result_df["Material"] = result_df["CODIGO MATERIAL"].apply(normalize_material_display) if "CODIGO MATERIAL" in result_df.columns else "NOT AVAILABLE"
    result_df["Lista de materiales"] = result_df["LM_DOCS"].fillna("NIL").astype(str).apply(lambda value: "NIL" if value.strip() == "" or value.strip().upper() in ["NAN", "NONE", "NOT AVAILABLE"] else value.strip()) if "LM_DOCS" in result_df.columns else "NIL"
    result_df["Desc.Proveedor"] = result_df["Proveedor"].fillna("NOT AVAILABLE") if "Proveedor" in result_df.columns else "NOT AVAILABLE"
    result_df["Precio unitario"] = result_df["PRECIO UNITARIO MEDIO"].apply(format_currency) if "PRECIO UNITARIO MEDIO" in result_df.columns else "0,00 €"
    result_df["Precio total"] = result_df["COSTE PEDIDO"].apply(format_currency) if "COSTE PEDIDO" in result_df.columns else "0,00 €"
    for column in ["PRIMERA FECHA SOL.", "ULTIMA FECHA PED.", "FECHA ENTREGA PROXIMA", "FECHA ENTREGA ULTIMA"]:
        if column in result_df.columns:
            result_df[column] = result_df[column].apply(format_date_value)
    if "COBERTURA COMPRA" in result_df.columns:
        result_df["COBERTURA COMPRA"] = result_df["COBERTURA COMPRA"].apply(lambda value: format_decimal(float(value) * 100, 1) + " %")
    for column in ["PRECIO UNITARIO MEDIO", "PRECIO UNITARIO ULTIMO", "COSTE LM ESTIMADO", "COSTE PEDIDO"]:
        if column in result_df.columns:
            result_df[column] = result_df[column].apply(format_currency)
    for column in ["CANTIDAD LM", "CANTIDAD PEDIDA", "CANTIDAD ENTREGADA", "CANTIDAD PENDIENTE", "Ctd. Solicitada"]:
        if column in result_df.columns:
            result_df[column] = result_df[column].apply(lambda value: format_decimal(value, 3))
    for column in MATERIAL_STATUS_CROSS_COLUMNS:
        if column not in result_df.columns:
            result_df[column] = "NIL" if column == "Lista de materiales" else "NOT AVAILABLE"
    return result_df[MATERIAL_STATUS_CROSS_COLUMNS].fillna({"Lista de materiales": "NIL"}).fillna("NOT AVAILABLE")

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


def render_material_status_table(table_df, height=520, default_visible_columns=None, grid_key="material_status_table", limit_rows_by_page_size=False):
    if table_df is None or table_df.empty:
        st.info("No hay datos para mostrar.")
        return
    default_visible_columns = default_visible_columns or [column for column in table_df.columns if not str(column).startswith("__")]
    hidden_columns = [column for column in table_df.columns if column not in default_visible_columns or str(column).startswith("__")]
    row_count = len(table_df)
    page_size_label = st.selectbox("Page Size", options=["100", "200", "300", "Todos"], index=0, key=f"{grid_key}_page_size")
    page_size = row_count if page_size_label == "Todos" else int(page_size_label)
    page_size = max(1, min(page_size, row_count))
    display_df = table_df if page_size_label == "Todos" or not limit_rows_by_page_size else table_df.head(page_size)
    loaded_count = len(display_df)
    if limit_rows_by_page_size and loaded_count < row_count:
        st.caption(f"Mostrando {loaded_count} de {row_count} registros. Cambia Page Size a 200, 300 o Todos para cargar más registros en la tabla.")
    st.caption("Usa el panel lateral de columnas de la tabla para mostrar u ocultar campos. Click en una celda copia directamente su valor. Ordenar, filtrar y mover columnas no debe relanzar el proceso de Streamlit.")
    numeric_comparator = JsCode("function(valueA, valueB) { function parseSpanishNumber(value) { if (value === null || value === undefined) { return 0; } let text = String(value).replace('€', '').replace('%', '').replace(/\s/g, '').trim(); if (text === '' || text.toUpperCase() === 'NOTAVAILABLE' || text.toUpperCase() === 'NOT AVAILABLE') { return 0; } text = text.replace(/\./g, '').replace(',', '.'); let number = parseFloat(text); return isNaN(number) ? 0 : number; } return parseSpanishNumber(valueA) - parseSpanishNumber(valueB); }")
    date_comparator = JsCode("function(valueA, valueB) { function parseDate(value) { if (!value) { return 0; } let text = String(value).trim(); let parts = text.split('-'); if (parts.length === 3) { return new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2])).getTime(); } let dateValue = Date.parse(text); return isNaN(dateValue) ? 0 : dateValue; } return parseDate(valueA) - parseDate(valueB); }")
    copy_cell_code = JsCode("function(params) { if (!params || params.value === null || params.value === undefined) { return; } const text = String(params.value); function fallbackCopy(value) { const area = document.createElement('textarea'); area.value = value; area.style.position = 'fixed'; area.style.left = '-9999px'; document.body.appendChild(area); area.focus(); area.select(); try { document.execCommand('copy'); } catch (e) {} document.body.removeChild(area); } if (navigator.clipboard && window.isSecureContext) { navigator.clipboard.writeText(text).catch(function() { fallbackCopy(text); }); } else { fallbackCopy(text); } }")
    numeric_sort_columns = ["Nº", "Precio total", "Precio unitario", "Precio unitario real", "Importe línea calculado", "Imp. unitario Ped.", "Cant Base Ped.", "Ctd. Solicitada", "Ctd. pedido", "CANTIDAD LM", "CANTIDAD PEDIDA", "CANTIDAD ENTREGADA", "CANTIDAD PENDIENTE", "COBERTURA COMPRA", "PRECIO UNITARIO MEDIO", "PRECIO UNITARIO ULTIMO", "COSTE LM ESTIMADO", "COSTE PEDIDO", "Nº PEDIDOS", "Nº CESTAS/SOLPEDS", "Nº PRECIOS DISTINTOS"]
    date_sort_columns = ["Fecha Sol.", "Fecha Ped.", "Fe. Entrega", "PRIMERA FECHA SOL.", "ULTIMA FECHA PED.", "FECHA ENTREGA PROXIMA", "FECHA ENTREGA ULTIMA"]
    grid_builder = GridOptionsBuilder.from_dataframe(display_df)
    grid_builder.configure_default_column(filter=True, sortable=True, resizable=True, editable=False, floatingFilter=True)
    default_sort_candidates = ["Precio total", "COSTE PEDIDO", "Importe línea calculado", "COSTE LM ESTIMADO", "Precio unitario", "Precio unitario real", "PRECIO UNITARIO MEDIO", "PRECIO UNITARIO ULTIMO"]
    default_sort_column = next((column for column in default_sort_candidates if column in display_df.columns), "")
    for column in display_df.columns:
        min_width = 90 if column == "Nº" else 240 if column in ["DESCRIPCION LM", "Descripción material", "Detalle", "Proveedor", "Desc.Proveedor", "Elemento PEP", "LM_DOCS", "Lista de materiales"] else 150
        sort_value = "desc" if column == default_sort_column else None
        sort_index_value = 0 if column == default_sort_column else None
        if column in numeric_sort_columns:
            grid_builder.configure_column(column, minWidth=min_width, width=min_width, hide=column in hidden_columns, comparator=numeric_comparator, filter="agNumberColumnFilter", sort=sort_value, sortIndex=sort_index_value)
        elif column in date_sort_columns:
            grid_builder.configure_column(column, minWidth=min_width, width=min_width, hide=column in hidden_columns, comparator=date_comparator, filter="agDateColumnFilter", sort=sort_value, sortIndex=sort_index_value)
        else:
            grid_builder.configure_column(column, minWidth=min_width, width=min_width, hide=column in hidden_columns, sort=sort_value, sortIndex=sort_index_value)
    grid_options = grid_builder.build()
    grid_options["sideBar"] = {"toolPanels": ["columns"], "defaultToolPanel": ""}
    grid_options["suppressRowClickSelection"] = True
    grid_options["suppressCellFocus"] = False
    grid_options["enableCellTextSelection"] = True
    grid_options["ensureDomOrder"] = True
    grid_options["suppressClipboardPaste"] = True
    grid_options["readOnlyEdit"] = True
    grid_options["singleClickEdit"] = False
    grid_options["suppressClickEdit"] = True
    grid_options["stopEditingWhenCellsLoseFocus"] = True
    grid_options["maintainColumnOrder"] = True
    grid_options["animateRows"] = False
    grid_options["rowBuffer"] = 10
    grid_options["pagination"] = True
    grid_options["paginationPageSize"] = page_size
    grid_options["paginationPageSizeSelector"] = [100, 200, 300, loaded_count]
    grid_options["suppressPaginationPanel"] = False
    grid_options["suppressScrollOnNewData"] = True
    grid_options["domLayout"] = "normal"
    grid_options["onCellClicked"] = copy_cell_code
    try:
        AgGrid(display_df, gridOptions=grid_options, height=height, fit_columns_on_grid_load=False, allow_unsafe_jscode=True, key=grid_key, update_mode=GridUpdateMode.NO_UPDATE, data_return_mode=DataReturnMode.AS_INPUT, reload_data=False, try_to_convert_back_to_original_types=False, update_on=[])
    except TypeError:
        AgGrid(display_df, gridOptions=grid_options, height=height, fit_columns_on_grid_load=False, allow_unsafe_jscode=True, key=grid_key, update_mode=GridUpdateMode.NO_UPDATE, data_return_mode=DataReturnMode.AS_INPUT, reload_data=False, try_to_convert_back_to_original_types=False)

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
            st.session_state.pop("material_status_active_signature", None)
            st.session_state.pop("material_status_processed_signature", None)
            clear_material_status_selection_cache()
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
    col2.metric("Coste servicios", format_currency(metrics.get("coste_servicios_sin_codigo", 0)))
    col3.metric("Líneas sin código", metrics.get("lineas_sin_codigo_material", 0))
    col4.metric("Materiales totales", metrics.get("materiales_totales", 0))
    col5.metric("Encontrados MS", metrics.get("materiales_encontrados", 0))
    col6.metric("No encontrados MS", metrics.get("materiales_no_encontrados", 0))


def build_lm_lookup_from_cross(cross_df):
    lookup_rows = []
    if cross_df is None or cross_df.empty or "CODIGO MATERIAL" not in cross_df.columns:
        return lookup_rows
    for _, lm_row in cross_df.iterrows():
        lm_key = normalize_material_key(lm_row.get("CODIGO MATERIAL", lm_row.get("Material", "")))
        if not lm_key:
            continue
        lookup_rows.append((lm_key, {"Lista de materiales": str(lm_row.get("Lista de materiales", "NOT AVAILABLE")).strip() or "NOT AVAILABLE", "CODIGO MATERIAL": normalize_material_display(lm_row.get("CODIGO MATERIAL", lm_row.get("Material", ""))), "DESCRIPCION LM": str(lm_row.get("DESCRIPCION LM", "NOT AVAILABLE")).strip() or "NOT AVAILABLE", "CANTIDAD LM": str(lm_row.get("CANTIDAD LM", "0")).strip() or "0", "ESTADO COMPRA": str(lm_row.get("ESTADO COMPRA", "NOT AVAILABLE")).strip() or "NOT AVAILABLE", "ESTADO ENTREGA": str(lm_row.get("ESTADO ENTREGA", "NOT AVAILABLE")).strip() or "NOT AVAILABLE", "Precio total": str(lm_row.get("Precio total", lm_row.get("COSTE PEDIDO", "0,00 €"))).strip() or "0,00 €"}))
    return lookup_rows


def get_lm_lookup_value(material_key, lookup_rows, field_name, default_value):
    for lm_key, lm_info in lookup_rows:
        if material_keys_match(lm_key, material_key):
            value = str(lm_info.get(field_name, default_value)).strip()
            return value if value and value.upper() not in ["NIL", "NAN", "NONE", ""] else default_value
    return default_value


def build_material_status_detail_table(ms_df, cross_df=None):
    if ms_df is None or ms_df.empty:
        return pd.DataFrame(columns=MATERIAL_STATUS_DETAIL_COLUMNS + ["__Precio total Num"])
    result_df = ms_df.copy()
    lookup_rows = build_lm_lookup_from_cross(cross_df)
    result_df["__Precio total Num"] = result_df["Importe línea calculado"].apply(parse_number) if "Importe línea calculado" in result_df.columns else 0.0
    result_df["Precio total"] = result_df["__Precio total Num"].apply(format_currency)
    if "Material Key" in result_df.columns:
        result_df["Lista de materiales"] = result_df["Material Key"].apply(lambda value: get_lm_lookup_value(value, lookup_rows, "Lista de materiales", "NOT AVAILABLE"))
        result_df["CODIGO MATERIAL"] = result_df.apply(lambda row: get_lm_lookup_value(row.get("Material Key", ""), lookup_rows, "CODIGO MATERIAL", row.get("Material", "NOT AVAILABLE")), axis=1)
        result_df["DESCRIPCION LM"] = result_df["Material Key"].apply(lambda value: get_lm_lookup_value(value, lookup_rows, "DESCRIPCION LM", "NOT AVAILABLE"))
        result_df["CANTIDAD LM"] = result_df["Material Key"].apply(lambda value: get_lm_lookup_value(value, lookup_rows, "CANTIDAD LM", "0"))
        result_df["ESTADO COMPRA"] = result_df["Material Key"].apply(lambda value: get_lm_lookup_value(value, lookup_rows, "ESTADO COMPRA", "NOT AVAILABLE"))
        result_df["ESTADO ENTREGA"] = result_df["Material Key"].apply(lambda value: get_lm_lookup_value(value, lookup_rows, "ESTADO ENTREGA", "NOT AVAILABLE"))
    else:
        result_df["Lista de materiales"] = "NOT AVAILABLE"
        result_df["CODIGO MATERIAL"] = result_df["Material"] if "Material" in result_df.columns else "NOT AVAILABLE"
        result_df["DESCRIPCION LM"] = "NOT AVAILABLE"
        result_df["CANTIDAD LM"] = "0"
        result_df["ESTADO COMPRA"] = "NOT AVAILABLE"
        result_df["ESTADO ENTREGA"] = "NOT AVAILABLE"
    result_df["CODIGO MATERIAL"] = result_df["CODIGO MATERIAL"].fillna("NOT AVAILABLE").astype(str).apply(lambda value: value if value.strip() and value.strip().upper() not in ["NAN", "NONE", ""] else "NOT AVAILABLE")
    result_df["Precio unitario real"] = result_df["Precio unitario real"].apply(format_currency)
    result_df["Importe línea calculado"] = result_df["Importe línea calculado"].apply(format_currency)
    for column in MATERIAL_STATUS_DATE_COLUMNS:
        if f"{column} Date" in result_df.columns:
            result_df[column] = result_df[f"{column} Date"].apply(format_date_value)
    for column in ["Ctd. Solicitada", "Ctd. pedido", "Imp. unitario Ped.", "Cant Base Ped."]:
        if column in result_df.columns:
            result_df[column] = result_df[column].fillna("NOT AVAILABLE").astype(str)
    for column in MATERIAL_STATUS_DETAIL_COLUMNS:
        if column not in result_df.columns:
            result_df[column] = "NOT AVAILABLE"
    result_columns = MATERIAL_STATUS_DETAIL_COLUMNS + ["__Precio total Num"]
    return result_df[result_columns].fillna("NOT AVAILABLE")

def get_material_status_detail_table_cached(selected_code, ms_df, cross_df):
    source = get_material_status_active_source()
    detail_signature = f"{len(ms_df)}|{len(cross_df) if cross_df is not None else 0}"
    cache_key = repr((str(selected_code), source.get("signature", ""), detail_signature))
    detail_cache = st.session_state.setdefault("material_status_detail_cache", {})
    if cache_key in detail_cache:
        return detail_cache[cache_key]
    detail_df = build_material_status_detail_table(ms_df, cross_df)
    detail_cache[cache_key] = detail_df
    return detail_df

def get_export_csv_bytes(table_df):
    if table_df is None or table_df.empty:
        return "".encode("utf-8-sig")
    export_df = table_df.drop(columns=[column for column in table_df.columns if str(column).startswith("__")], errors="ignore").fillna("NOT AVAILABLE").astype(str).copy()
    for column in ["CODIGO MATERIAL", "Material"]:
        if column in export_df.columns:
            export_df[column] = export_df[column].apply(format_material_for_excel_csv)
    return export_df.to_csv(index=False, sep=";").encode("utf-8-sig")


def is_not_available_value(value):
    text = str(value).strip().upper()
    return text in ["", "NAN", "NONE", "NOT AVAILABLE"]


def build_material_status_summary_export_tables(cross_df, detail_df):
    safe_cross_df = cross_df if cross_df is not None else pd.DataFrame()
    safe_detail_df = detail_df if detail_df is not None else pd.DataFrame()
    if safe_cross_df.empty:
        return {"materiales_totales_lms": pd.DataFrame(), "materiales_encontrados_ms": pd.DataFrame(), "materiales_no_encontrados_ms": pd.DataFrame(), "materiales_con_precio": pd.DataFrame(), "materiales_sin_precio": pd.DataFrame(), "materiales_pendientes": pd.DataFrame(), "materiales_entregados": pd.DataFrame(), "lineas_material_status_usadas": safe_detail_df}
    found_mask = ~safe_cross_df["Descripción material"].apply(is_not_available_value) if "Descripción material" in safe_cross_df.columns else pd.Series([False] * len(safe_cross_df), index=safe_cross_df.index)
    price_mask = safe_cross_df["PRECIO UNITARIO MEDIO"].apply(lambda value: parse_number(value) > 0) if "PRECIO UNITARIO MEDIO" in safe_cross_df.columns else pd.Series([False] * len(safe_cross_df), index=safe_cross_df.index)
    delivery_mask = safe_cross_df["ESTADO ENTREGA"].isin(["Pendiente", "Parcial", "Retrasado"]) if "ESTADO ENTREGA" in safe_cross_df.columns else pd.Series([False] * len(safe_cross_df), index=safe_cross_df.index)
    delivered_mask = safe_cross_df["ESTADO ENTREGA"].eq("Entregado") if "ESTADO ENTREGA" in safe_cross_df.columns else pd.Series([False] * len(safe_cross_df), index=safe_cross_df.index)
    return {"materiales_totales_lms": safe_cross_df, "materiales_encontrados_ms": safe_cross_df.loc[found_mask], "materiales_no_encontrados_ms": safe_cross_df.loc[~found_mask], "materiales_con_precio": safe_cross_df.loc[found_mask & price_mask], "materiales_sin_precio": safe_cross_df.loc[(~found_mask) | (~price_mask)], "materiales_pendientes": safe_cross_df.loc[delivery_mask], "materiales_entregados": safe_cross_df.loc[delivered_mask], "lineas_material_status_usadas": safe_detail_df}


def build_material_status_summary_export_payloads(cross_df, detail_df):
    export_tables = build_material_status_summary_export_tables(cross_df, detail_df)
    suffix_map = {"materiales_totales_lms": "materiales_totales_lms", "materiales_encontrados_ms": "materiales_encontrados_ms", "materiales_no_encontrados_ms": "materiales_no_encontrados_ms", "materiales_con_precio": "materiales_con_precio", "materiales_sin_precio": "materiales_sin_precio", "materiales_pendientes_parciales_retrasados": "materiales_pendientes", "materiales_entregados": "materiales_entregados", "lineas_material_status_usadas": "lineas_material_status_usadas"}
    payloads = {}
    for suffix, table_key in suffix_map.items():
        table_df = export_tables.get(table_key, pd.DataFrame())
        payloads[suffix] = {"disabled": table_df is None or table_df.empty, "csv_bytes": get_export_csv_bytes(table_df)}
    return payloads


def prepare_material_status_display_table(table_df):
    if table_df is None or table_df.empty:
        return table_df if table_df is not None else pd.DataFrame()
    result_df = table_df.copy()
    if "__Precio total Num" in result_df.columns:
        result_df["__material_status_sort_value"] = result_df["__Precio total Num"].apply(parse_number)
    else:
        default_sort_candidates = ["Precio total", "COSTE PEDIDO", "Importe línea calculado", "COSTE LM ESTIMADO", "Precio unitario", "Precio unitario real", "PRECIO UNITARIO MEDIO", "PRECIO UNITARIO ULTIMO"]
        sort_column = next((column for column in default_sort_candidates if column in result_df.columns), "")
        result_df["__material_status_sort_value"] = result_df[sort_column].apply(parse_number) if sort_column else 0
    result_df = result_df.sort_values("__material_status_sort_value", ascending=False).drop(columns=["__material_status_sort_value"], errors="ignore").reset_index(drop=True)
    if "Nº" in result_df.columns:
        result_df = result_df.drop(columns=["Nº"], errors="ignore")
    result_df.insert(0, "Nº", range(1, len(result_df) + 1))
    return result_df

def render_summary_download_line(label, value, export_payloads, file_suffix, selected_code):
    col_text, col_button = st.columns([4, 1])
    payload = export_payloads.get(file_suffix, {}) if isinstance(export_payloads, dict) else {}
    disabled = bool(payload.get("disabled", True))
    csv_bytes = payload.get("csv_bytes", "".encode("utf-8-sig"))
    col_text.markdown(f"**{label}:** {value}")
    col_button.download_button("Exportar CSV", data=csv_bytes, file_name=f"Material_Status_{selected_code}_{file_suffix}.csv", mime="text/csv", disabled=disabled, key=f"download_material_status_summary_{selected_code}_{file_suffix}")

def render_material_status_summary(metrics, export_payloads, selected_code):
    st.info("El coste del módulo se calcula con el Precio total de todas las líneas de Material Status mostradas, incluyendo servicios sin código de material. Las LMs se usan para indicar en qué lista aparece cada material cuando existe coincidencia.")
    st.markdown(f"**Precio por módulo:** {format_currency(metrics.get('precio_modulo', 0))}")
    st.markdown(f"**Coste servicios sin código de material:** {format_currency(metrics.get('coste_servicios_sin_codigo', 0))}")
    st.markdown(f"**Líneas sin código de material:** {metrics.get('lineas_sin_codigo_material', 0)}")
    render_summary_download_line("Materiales totales en LMs", metrics.get("materiales_totales", 0), export_payloads, "materiales_totales_lms", selected_code)
    render_summary_download_line("Materiales encontrados en Material Status", metrics.get("materiales_encontrados", 0), export_payloads, "materiales_encontrados_ms", selected_code)
    render_summary_download_line("Materiales no encontrados en Material Status", metrics.get("materiales_no_encontrados", 0), export_payloads, "materiales_no_encontrados_ms", selected_code)
    render_summary_download_line("Materiales con precio", metrics.get("materiales_con_precio", 0), export_payloads, "materiales_con_precio", selected_code)
    render_summary_download_line("Materiales sin precio", metrics.get("materiales_sin_precio", 0), export_payloads, "materiales_sin_precio", selected_code)
    render_summary_download_line("Materiales pendientes/parciales/retrasados", metrics.get("materiales_pendientes", 0), export_payloads, "materiales_pendientes_parciales_retrasados", selected_code)
    render_summary_download_line("Materiales entregados", metrics.get("materiales_entregados", 0), export_payloads, "materiales_entregados", selected_code)
    render_summary_download_line("Líneas Material Status usadas", metrics.get("lineas_material_status", 0), export_payloads, "lineas_material_status_usadas", selected_code)

def build_material_type_classification_table(material_status_df):
    if material_status_df is None or material_status_df.empty or "Tipo pedido" not in material_status_df.columns:
        return pd.DataFrame(columns=["Tipo pedido", "Materiales", "Lineas", "Importe"])
    type_df = material_status_df.copy()
    type_df["__importe_num"] = type_df["__Precio total Num"].apply(parse_number) if "__Precio total Num" in type_df.columns else type_df["Precio total"].apply(parse_number) if "Precio total" in type_df.columns else 0.0
    grouped_df = type_df.groupby("Tipo pedido", dropna=False).agg(Materiales=("Material", "nunique"), Lineas=("Material", "count"), Importe=("__importe_num", "sum")).reset_index()
    grouped_df["__importe_sort"] = grouped_df["Importe"]
    grouped_df["Importe"] = grouped_df["Importe"].apply(format_currency)
    return grouped_df.sort_values(["__importe_sort", "Materiales", "Lineas"], ascending=False).drop(columns=["__importe_sort"], errors="ignore").reset_index(drop=True)


def render_material_type_classification(type_summary_df):
    st.markdown("### Clasificación por tipo")
    if type_summary_df is None or type_summary_df.empty:
        st.info("No hay datos suficientes para clasificar por tipo de pedido.")
        return
    st.dataframe(type_summary_df, width="stretch", hide_index=True)


def render_material_status_information_labels(metrics, material_status_df):
    st.markdown("### Información de materiales del elemento")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Materiales en LMs", metrics.get("materiales_totales", 0))
    col2.metric("Encontrados en SAP", metrics.get("materiales_encontrados", 0))
    col3.metric("No encontrados en SAP", metrics.get("materiales_no_encontrados", 0))
    col4.metric("Líneas Material Status", len(material_status_df) if material_status_df is not None else 0)


def build_material_status_chart_tables(material_status_df):
    empty_result = {"type_amount_df": pd.DataFrame(columns=["Tipo pedido", "Importe Num", "Importe"]), "supplier_amount_df": pd.DataFrame(columns=["Proveedor", "Importe Num", "Importe"]), "delivery_month_amount_df": pd.DataFrame(columns=["Mes entrega", "Importe Num", "Importe", "__Fecha Orden"])}
    if material_status_df is None or material_status_df.empty:
        return empty_result
    chart_df = material_status_df.copy()
    chart_df["__importe_num"] = chart_df["__Precio total Num"].apply(parse_number) if "__Precio total Num" in chart_df.columns else chart_df["Precio total"].apply(parse_number) if "Precio total" in chart_df.columns else 0.0
    chart_df["__tipo_pedido"] = chart_df["Tipo pedido"].fillna("NOT AVAILABLE").astype(str).replace("", "NOT AVAILABLE") if "Tipo pedido" in chart_df.columns else "NOT AVAILABLE"
    chart_df["__proveedor"] = chart_df["Desc.Proveedor"].fillna("NOT AVAILABLE").astype(str).replace("", "NOT AVAILABLE") if "Desc.Proveedor" in chart_df.columns else "NOT AVAILABLE"
    chart_df["__fecha_entrega"] = pd.to_datetime(chart_df["Fe. Entrega"], errors="coerce") if "Fe. Entrega" in chart_df.columns else pd.NaT
    type_amount_df = chart_df.groupby("__tipo_pedido", dropna=False).agg(**{"Importe Num": ("__importe_num", "sum")}).reset_index().rename(columns={"__tipo_pedido": "Tipo pedido"})
    type_amount_df = type_amount_df[type_amount_df["Importe Num"] != 0].copy().sort_values("Importe Num", ascending=False).reset_index(drop=True)
    type_amount_df["Importe"] = type_amount_df["Importe Num"].apply(format_currency)
    supplier_amount_df = chart_df.groupby("__proveedor", dropna=False).agg(**{"Importe Num": ("__importe_num", "sum")}).reset_index().rename(columns={"__proveedor": "Proveedor"})
    supplier_amount_df = supplier_amount_df[supplier_amount_df["Importe Num"] != 0].copy().sort_values("Importe Num", ascending=False).reset_index(drop=True)
    supplier_amount_df["Importe"] = supplier_amount_df["Importe Num"].apply(format_currency)
    dated_df = chart_df.dropna(subset=["__fecha_entrega"]).copy()
    if dated_df.empty:
        delivery_month_amount_df = pd.DataFrame(columns=["Mes entrega", "Importe Num", "Importe", "__Fecha Orden"])
    else:
        dated_df["__Fecha Orden"] = dated_df["__fecha_entrega"].dt.to_period("M").dt.to_timestamp()
        dated_df["Mes entrega"] = dated_df["__Fecha Orden"].dt.strftime("%m/%Y")
        delivery_month_amount_df = dated_df.groupby(["__Fecha Orden", "Mes entrega"], dropna=False).agg(**{"Importe Num": ("__importe_num", "sum")}).reset_index().sort_values("__Fecha Orden", ascending=True).reset_index(drop=True)
        delivery_month_amount_df["Importe"] = delivery_month_amount_df["Importe Num"].apply(format_currency)
    return {"type_amount_df": type_amount_df, "supplier_amount_df": supplier_amount_df, "delivery_month_amount_df": delivery_month_amount_df}


def format_chart_amount_label(value):
    try:
        number = float(value)
    except Exception:
        return "0€"
    abs_number = abs(number)
    if abs_number >= 1000000:
        return format_decimal(number / 1000000, 1) + "M€"
    if abs_number >= 1000:
        return format_decimal(number / 1000, 0) + "k€"
    return format_decimal(number, 0) + "€"


def apply_indra_plotly_layout(fig, title, x_title="", y_title="", height=360, horizontal=False):
    fig.update_layout(title={"text": title, "x": 0.0, "xanchor": "left", "font": {"size": 15, "color": CHART_PALETTE["texto_claro"]}}, paper_bgcolor=CHART_PALETTE["azul_amazonico"], plot_bgcolor=CHART_PALETTE["azul_amazonico"], font={"color": CHART_PALETTE["texto_claro"], "size": 11}, height=height, margin={"l": 160 if horizontal else 52, "r": 28, "t": 62, "b": 78 if not horizontal else 44}, showlegend=False, hoverlabel={"bgcolor": CHART_PALETTE["azul_oscuro"], "font_size": 12, "font_color": CHART_PALETTE["texto_claro"]})
    fig.update_xaxes(title_text=x_title, showgrid=not horizontal, gridcolor=CHART_PALETTE["grid"], zeroline=False, linecolor=CHART_PALETTE["grid"], tickfont={"color": CHART_PALETTE["texto_claro"], "size": 10}, title_font={"color": CHART_PALETTE["texto_claro"], "size": 12})
    fig.update_yaxes(title_text=y_title, showgrid=horizontal, gridcolor=CHART_PALETTE["grid"], zeroline=False, linecolor=CHART_PALETTE["grid"], tickfont={"color": CHART_PALETTE["texto_claro"], "size": 10}, title_font={"color": CHART_PALETTE["texto_claro"], "size": 12})
    return fig


def render_indra_plotly_bar_chart(chart_df, title, category_column, value_column, orientation="v", height=360, x_title="", y_title="", max_rows=None):
    if chart_df is None or chart_df.empty or category_column not in chart_df.columns or value_column not in chart_df.columns:
        st.info(f"No hay datos para generar el gráfico: {title}.")
        return
    plot_df = chart_df.copy()
    plot_df[value_column] = pd.to_numeric(plot_df[value_column], errors="coerce").fillna(0)
    plot_df = plot_df[plot_df[value_column] != 0].copy()
    if plot_df.empty:
        st.info(f"No hay importes válidos para generar el gráfico: {title}.")
        return
    if max_rows is not None:
        plot_df = plot_df.sort_values(value_column, ascending=False).head(max_rows).copy()
    plot_df["__label"] = plot_df[value_column].apply(format_chart_amount_label)
    colors = [CHART_COLOR_SEQUENCE[index % len(CHART_COLOR_SEQUENCE)] for index in range(len(plot_df))]
    if orientation == "h":
        plot_df = plot_df.sort_values(value_column, ascending=True).copy()
        colors = [CHART_COLOR_SEQUENCE[index % len(CHART_COLOR_SEQUENCE)] for index in range(len(plot_df))]
        fig = go.Figure(go.Bar(x=plot_df[value_column], y=plot_df[category_column], orientation="h", marker={"color": colors, "line": {"width": 0}}, text=plot_df["__label"], textposition="inside", insidetextanchor="end", cliponaxis=False, hovertemplate="%{y}<br>Importe: %{customdata}<extra></extra>", customdata=plot_df["Importe"] if "Importe" in plot_df.columns else plot_df["__label"]))
        fig = apply_indra_plotly_layout(fig, title, x_title=x_title, y_title=y_title, height=height, horizontal=True)
    else:
        fig = go.Figure(go.Bar(x=plot_df[category_column], y=plot_df[value_column], marker={"color": colors, "line": {"width": 0}}, text=plot_df["__label"], textposition="outside", cliponaxis=False, hovertemplate="%{x}<br>Importe: %{customdata}<extra></extra>", customdata=plot_df["Importe"] if "Importe" in plot_df.columns else plot_df["__label"]))
        fig = apply_indra_plotly_layout(fig, title, x_title=x_title, y_title=y_title, height=height, horizontal=False)
    st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]})


def render_material_status_amount_charts(chart_tables):
    st.markdown("### Gráficos de importe")
    type_amount_df = chart_tables.get("type_amount_df", pd.DataFrame()) if isinstance(chart_tables, dict) else pd.DataFrame()
    supplier_amount_df = chart_tables.get("supplier_amount_df", pd.DataFrame()) if isinstance(chart_tables, dict) else pd.DataFrame()
    delivery_month_amount_df = chart_tables.get("delivery_month_amount_df", pd.DataFrame()) if isinstance(chart_tables, dict) else pd.DataFrame()
    render_indra_plotly_bar_chart(type_amount_df, "Importe por tipo", "Tipo pedido", "Importe Num", "v", 360, "Tipo pedido", "Importe (€)")
    supplier_height = min(max(360, len(supplier_amount_df) * 28), 900) if supplier_amount_df is not None and not supplier_amount_df.empty else 360
    render_indra_plotly_bar_chart(supplier_amount_df, "Importe por proveedor", "Proveedor", "Importe Num", "h", supplier_height, "Importe (€)", "Proveedor", 30)
    render_indra_plotly_bar_chart(delivery_month_amount_df, "Importe por fecha de entrega", "Mes entrega", "Importe Num", "v", 360, "Mes/Año entrega", "Importe (€)")


def get_material_status_view_cache_key(df, selected_code):
    source = get_material_status_active_source()
    root_path = str(st.session_state.get("root_path", ""))
    loaded_root_path = str(st.session_state.get("loaded_root_path", ""))
    lm_global_file_count = int(st.session_state.get("lm_global_file_count", 0))
    return repr((str(selected_code), source.get("signature", ""), root_path, loaded_root_path, lm_global_file_count))


def build_material_status_view_bundle(df, selected_code, progress_bar=None, status_box=None, force_reload=False):
    cache_key = get_material_status_view_cache_key(df, selected_code)
    view_cache = st.session_state.setdefault("material_status_view_cache", {})
    if not force_reload and cache_key in view_cache:
        return view_cache[cache_key]
    cross_df, incidents_df, ms_df, metrics, log_lines = build_material_status_cross_for_selected_code(df, selected_code, progress_bar, status_box, force_reload)
    if status_box is not None:
        status_box.info("Preparando tablas finales de Material Status...")
    if progress_bar is not None:
        progress_bar.progress(96)
    detail_df = get_material_status_detail_table_cached(selected_code, ms_df, cross_df)
    if status_box is not None:
        status_box.info("Ordenando y preparando vistas en memoria...")
    detail_df = prepare_material_status_display_table(detail_df)
    incidents_df = prepare_material_status_display_table(incidents_df)
    cross_df = prepare_material_status_display_table(cross_df)
    metrics = dict(metrics)
    detail_total_cost = float(detail_df["__Precio total Num"].apply(parse_number).sum()) if detail_df is not None and not detail_df.empty and "__Precio total Num" in detail_df.columns else float(detail_df["Precio total"].apply(parse_number).sum()) if detail_df is not None and not detail_df.empty and "Precio total" in detail_df.columns else 0.0
    empty_material_mask = detail_df["CODIGO MATERIAL"].apply(is_not_available_value) if detail_df is not None and not detail_df.empty and "CODIGO MATERIAL" in detail_df.columns else pd.Series(dtype=bool)
    empty_material_cost = float(detail_df.loc[empty_material_mask, "__Precio total Num"].apply(parse_number).sum()) if detail_df is not None and not detail_df.empty and "__Precio total Num" in detail_df.columns and len(empty_material_mask) else float(detail_df.loc[empty_material_mask, "Precio total"].apply(parse_number).sum()) if detail_df is not None and not detail_df.empty and "Precio total" in detail_df.columns and len(empty_material_mask) else 0.0
    metrics["precio_modulo"] = detail_total_cost
    metrics["coste_servicios_sin_codigo"] = empty_material_cost
    metrics["lineas_sin_codigo_material"] = int(empty_material_mask.sum()) if len(empty_material_mask) else 0
    metrics["lineas_material_status"] = len(detail_df)
    type_summary_df = build_material_type_classification_table(detail_df)
    chart_tables = build_material_status_chart_tables(detail_df)
    if status_box is not None:
        status_box.info("Preparando exportaciones del resumen...")
    if progress_bar is not None:
        progress_bar.progress(98)
    summary_export_payloads = build_material_status_summary_export_payloads(cross_df, detail_df)
    result = {"cross_df": cross_df, "incidents_df": incidents_df, "ms_df": ms_df, "detail_df": detail_df, "type_summary_df": type_summary_df, "chart_tables": chart_tables, "summary_export_payloads": summary_export_payloads, "metrics": metrics, "log_lines": list(log_lines)}
    view_cache[cache_key] = result
    return result

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
    st.caption(" | ".join([f"{level}: {level_counts.get(level, 0)}" for level in available_levels]))
    st.text_area("Detalle", value="\n".join(filtered_log_lines) if filtered_log_lines else "No hay mensajes para los tipos seleccionados.", height=220, disabled=True)


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
    active_view = st.radio("Vista Material Status", options=["Resumen", "Material Status", "Incidencias", "Log de carga"], horizontal=True, label_visibility="collapsed", key="material_status_active_view")
    if load_clicked:
        progress_bar = st.progress(0)
        status_box = st.empty()
        status_box.info("Iniciando carga de Material Status...")
        st.session_state[f"material_status_merged_{selected_code_value}_page_size"] = "100"
        bundle = build_material_status_view_bundle(df, selected_code, progress_bar, status_box, True)
        progress_bar.progress(100)
        status_box.success("Material Status cargado, cacheado y preparado correctamente.")
    else:
        bundle = build_material_status_view_bundle(df, selected_code)
    cross_df = bundle.get("cross_df", pd.DataFrame())
    incidents_df = bundle.get("incidents_df", pd.DataFrame())
    detail_df = bundle.get("detail_df", pd.DataFrame())
    type_summary_df = bundle.get("type_summary_df", pd.DataFrame())
    summary_export_payloads = bundle.get("summary_export_payloads", {})
    chart_tables = bundle.get("chart_tables", {})
    metrics = bundle.get("metrics", {})
    log_lines = bundle.get("log_lines", [])
    render_material_status_metrics(metrics)
    if active_view == "Resumen":
        render_material_status_summary(metrics, summary_export_payloads, selected_code_value)
    elif active_view == "Material Status":
        render_material_status_information_labels(metrics, detail_df)
        render_material_type_classification(type_summary_df)
        render_material_status_table(detail_df, 560, MATERIAL_STATUS_DETAIL_DEFAULT_COLUMNS, f"material_status_merged_{selected_code_value}", True)
        render_material_status_amount_charts(chart_tables)
    elif active_view == "Incidencias":
        render_material_status_table(incidents_df, 520, MATERIAL_STATUS_INCIDENTS_DEFAULT_COLUMNS, f"material_status_incidents_{selected_code_value}", True)
    elif active_view == "Log de carga":
        render_material_status_log(log_lines)

