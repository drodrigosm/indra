# Este fichero reúne utilidades comunes de tratamiento de ficheros, conversión de Excel y normalización de claves de texto.
import shutil
import subprocess
import tempfile
from pathlib import Path


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


def normalize_text_key(value: str | None) -> str:
    if value is None:
        return ''
    normalized = str(value).strip().upper()
    normalized = ' '.join(normalized.split())
    return normalized