# Funciones de escaneo y normalizacion de la estructura HW del simulador a partir de un directorio raiz.

import json
import os
import re
from pathlib import Path
import pandas as pd

PADDED_CODE_PATTERN = re.compile(r"^(A\d+)")

DEFAULT_MAIN_HW_ELEMENTS = [{"code": "A01", "component": "COCKPIT", "sica": ""}, {"code": "A02", "component": "AFTERCABIN", "sica": ""}, {"code": "A03", "component": "VISUAL DISPLAY SYSTEM", "sica": ""}, {"code": "A04", "component": "BASEFRAME", "sica": ""}, {"code": "A05", "component": "DRAWBRIDGE", "sica": ""}, {"code": "A07", "component": "MOTION SYSTEM", "sica": ""}, {"code": "A08", "component": "PROCESSOR RACK #1", "sica": ""}, {"code": "A09", "component": "PROCESSOR RACK #2", "sica": ""}, {"code": "A12", "component": "UPS", "sica": ""}, {"code": "A14", "component": "BREATHING AIR", "sica": ""}, {"code": "A15", "component": "AIR CONDITIONING SYSTEM", "sica": ""}, {"code": "A18", "component": "FIRE DETECTION", "sica": ""}, {"code": "A21", "component": "POWER CABINET", "sica": ""}, {"code": "A26", "component": "PLANNER STATION", "sica": ""}, {"code": "A27", "component": "DEBRIEFING STATION", "sica": ""}]
MAIN_HW_ELEMENTS_JSON_PATH = Path(__file__).resolve().parent / "main_hw_elements.json"

def load_main_hw_elements():
    if not MAIN_HW_ELEMENTS_JSON_PATH.exists():
        return DEFAULT_MAIN_HW_ELEMENTS
    try:
        with open(MAIN_HW_ELEMENTS_JSON_PATH, "r", encoding="utf-8") as file:
            data = json.load(file)
        elements = data.get("main_hw_elements", [])
        valid_elements = []
        for item in elements:
            code = normalize_code(item.get("code", ""))
            component = str(item.get("component", "")).strip()
            sica = str(item.get("sica", "")).strip()
            if code and component:
                valid_elements.append({"code": code, "component": component, "sica": sica})
        return valid_elements if valid_elements else DEFAULT_MAIN_HW_ELEMENTS
    except Exception:
        return DEFAULT_MAIN_HW_ELEMENTS


def get_main_hw_elements():
    return load_main_hw_elements()

def normalize_code(raw_code):
    if raw_code is None:
        return ""
    value = str(raw_code).strip().upper()
    match = PADDED_CODE_PATTERN.match(value)
    if not match:
        return ""
    code = match.group(1)
    digits = code[1:]
    while len(digits) > 2 and digits.endswith("00"):
        digits = digits[:-2]
    return "A" + digits


def get_code_from_name(name):
    if not name:
        return ""
    value = str(name).strip().upper()
    match = PADDED_CODE_PATTERN.match(value)
    if not match:
        return ""
    return normalize_code(match.group(1))


def get_description_from_name(name):
    if not name:
        return ""
    value = str(name).strip()
    if " - " in value:
        return value.split(" - ", 1)[1].strip()
    parts = value.split(maxsplit=1)
    if len(parts) == 2 and get_code_from_name(parts[0]):
        return parts[1].strip()
    return value


def get_level_from_code(code):
    if not code or not code.startswith("A"):
        return 0
    return int(len(code[1:]) / 2)


def get_parent_code(code):
    if not code or get_level_from_code(code) <= 1:
        return ""
    return "A" + code[1:-2]


def get_main_code(code):
    if not code or len(code) < 3:
        return code
    return "A" + code[1:3]


def get_main_catalog_dict():
    return {item["code"]: item for item in get_main_hw_elements()}


def safe_iterdir(path):
    try:
        return sorted(list(Path(path).iterdir()), key=lambda item: (not item.is_dir(), item.name.lower()))
    except Exception:
        return []


def count_content(path):
    total_dirs = 0
    total_files = 0
    for root, dirs, files in os.walk(path):
        total_dirs += len(dirs)
        total_files += len(files)
    return total_dirs, total_files


def format_size(size_bytes):
    try:
        size = float(size_bytes)
    except Exception:
        return ""
    if size < 1024:
        return f"{int(size)} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    if size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    return f"{size / (1024 * 1024 * 1024):.1f} GB"


def get_direct_content(path):
    rows = []
    for item in safe_iterdir(path):
        try:
            item_type = "Carpeta" if item.is_dir() else "Fichero"
            item_code = get_code_from_name(item.name)
            item_level = str(get_level_from_code(item_code)) if item_code else "NOT AVAILABLE"
            item_size = "" if item.is_dir() else format_size(item.stat().st_size)
            rows.append({"tipo": item_type, "codigo": item_code if item_code else "NOT AVAILABLE", "nivel": item_level, "nombre": item.name, "ruta": str(item), "tamano": item_size})
        except Exception:
            rows.append({"tipo": "Error", "codigo": "NOT AVAILABLE", "nivel": "NOT AVAILABLE", "nombre": item.name, "ruta": str(item), "tamano": ""})
    return pd.DataFrame(rows)


def scan_hw_folders(root_path):
    rows = []
    root = Path(root_path)
    main_catalog = get_main_catalog_dict()
    columns = ["code", "level", "name", "description", "component", "sica", "path", "parent_code", "main_code", "dirs", "files", "exists"]
    if not root.exists() or not root.is_dir():
        return pd.DataFrame(columns=columns)
    for current_root, dirs, files in os.walk(root):
        current_path = Path(current_root)
        folder_name = current_path.name
        code = get_code_from_name(folder_name)
        if not code:
            continue
        level = get_level_from_code(code)
        parent_code = get_parent_code(code)
        main_code = get_main_code(code)
        child_dirs, child_files = count_content(current_path)
        catalog_item = main_catalog.get(code, {})
        description = get_description_from_name(folder_name)
        component = catalog_item.get("component", description)
        sica = catalog_item.get("sica", "")
        rows.append({"code": code, "level": level, "name": folder_name, "description": description, "component": component, "sica": sica, "path": str(current_path), "parent_code": parent_code, "main_code": main_code, "dirs": child_dirs, "files": child_files, "exists": True})
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=columns)
    df = df.drop_duplicates(subset=["path"]).sort_values(["main_code", "level", "code", "path"]).reset_index(drop=True)
    return df


def add_missing_main_elements(df):
    existing_codes = set(df["code"].astype(str).tolist()) if not df.empty else set()
    rows = []
    for item in get_main_hw_elements():
        if item["code"] not in existing_codes:
            rows.append({"code": item["code"], "level": 1, "name": item["component"], "description": item["component"], "component": item["component"], "sica": item.get("sica", ""), "path": "", "parent_code": "", "main_code": item["code"], "dirs": 0, "files": 0, "exists": False})
    if not rows:
        return df
    return pd.concat([df, pd.DataFrame(rows)], ignore_index=True).sort_values(["main_code", "level", "code", "path"]).reset_index(drop=True)


def get_sidebar_main_elements(df):
    result = []
    configured_elements = get_main_hw_elements()
    for item in configured_elements:
        element_df = df[df["main_code"] == item["code"]] if not df.empty else pd.DataFrame()
        exists = not element_df[element_df["exists"] == True].empty if not element_df.empty and "exists" in element_df.columns else False
        result.append({"code": item["code"], "component": item["component"], "sica": item.get("sica", ""), "exists": exists})
    return result


def get_main_element_row(df, code):
    if df.empty or not code:
        return None
    exact = df[(df["code"] == code) & (df["exists"] == True)].copy()
    if exact.empty:
        exact = df[df["code"] == code].copy()
    if exact.empty:
        return None
    exact["path_len"] = exact["path"].astype(str).str.len()
    exact = exact.sort_values(["exists", "path_len"], ascending=[False, True])
    return exact.iloc[0]


def get_children_by_code(df, parent_code):
    if df.empty or not parent_code:
        return pd.DataFrame()
    if parent_code == "A00":
        children = df[(df["level"] == 1) & (df["code"] != "A00") & (df["exists"] == True)].copy()
        return children.sort_values(["level", "code", "component", "path"]).reset_index(drop=True)
    children = df[(df["parent_code"] == parent_code) & (df["exists"] == True)].copy()
    return children.sort_values(["level", "code", "component", "path"]).reset_index(drop=True)

def get_descendant_rows_by_code(df, selected_code):
    if df.empty or not selected_code:
        return pd.DataFrame()
    if selected_code == "A00":
        descendants = df[df["exists"] == True].copy()
        return descendants.sort_values(["level", "code", "component", "path"]).reset_index(drop=True)
    descendants = df[(df["code"].astype(str).str.startswith(selected_code)) & (df["exists"] == True)].copy()
    return descendants.sort_values(["level", "code", "component", "path"]).reset_index(drop=True)