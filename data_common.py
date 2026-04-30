# Este fichero reúne utilidades comunes de tratamiento de ficheros, conversión de Excel, lectura robusta y normalización de claves de texto.
import shutil
import subprocess
import tempfile
from pathlib import Path
import pandas as pd


def try_convert_xls_to_xlsx(input_path: Path) -> Path:
    if input_path.suffix.lower() != '.xls':
        return input_path
    temp_dir = Path(tempfile.mkdtemp(prefix='costes_xls_'))
    office_bin = shutil.which('libreoffice') or shutil.which('soffice')
    if office_bin:
        result = subprocess.run([office_bin, '--headless', '--convert-to', 'xlsx', str(input_path), '--outdir', str(temp_dir)], capture_output=True, text=True)
        converted_path = temp_dir / f'{input_path.stem}.xlsx'
        if result.returncode == 0 and converted_path.exists():
            return converted_path
    return input_path


def save_uploaded_file_to_temp(uploaded_file, prefix: str) -> Path:
    safe_file_name = Path(uploaded_file.name).name
    temp_input = Path(tempfile.mkdtemp(prefix=prefix)) / safe_file_name
    temp_input.write_bytes(uploaded_file.getbuffer())
    return temp_input


def read_excel_robust(file_path: Path, sheet_name='Hoja1', header=None) -> pd.DataFrame:
    source_path = try_convert_xls_to_xlsx(file_path)
    suffix = source_path.suffix.lower()
    try:
        if suffix == '.xls':
            return pd.read_excel(source_path, sheet_name=sheet_name, header=header, engine='xlrd')
        if suffix == '.xlsx':
            return pd.read_excel(source_path, sheet_name=sheet_name, header=header, engine='openpyxl')
        return pd.read_excel(source_path, sheet_name=sheet_name, header=header)
    except ImportError as exc:
        raise RuntimeError('No se puede leer el Excel antiguo .xls. Instala xlrd con: pip install xlrd') from exc
    except Exception as exc:
        raise RuntimeError(f'No se ha podido leer el Excel "{Path(file_path).name}": {exc}') from exc


def normalize_text_key(value: str | None) -> str:
    if value is None:
        return ''
    normalized = str(value).strip().upper()
    normalized = ' '.join(normalized.split())
    return normalized