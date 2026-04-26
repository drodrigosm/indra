# Este fichero arranca la aplicación Streamlit localmente desde el ejecutable y abre el navegador del usuario.
import os
import sys
import time
import socket
import threading
import webbrowser
from pathlib import Path


def get_base_dir() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS).resolve()
    return Path(__file__).resolve().parent


def find_free_port(start_port: int = 8501) -> int:
    for port in range(start_port, start_port + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(('127.0.0.1', port)) != 0:
                return port
    return start_port


def open_browser_later(url: str) -> None:
    time.sleep(4)
    webbrowser.open_new_tab(url)


def run_streamlit_app() -> None:
    from streamlit.web import cli as stcli
    base_dir = get_base_dir()
    app_path = base_dir / 'Costes.py'
    port = find_free_port()
    url = f'http://127.0.0.1:{port}'
    os.environ['STREAMLIT_SERVER_HEADLESS'] = 'true'
    os.environ['STREAMLIT_BROWSER_GATHER_USAGE_STATS'] = 'false'
    os.environ['STREAMLIT_GLOBAL_DEVELOPMENT_MODE'] = 'false'
    threading.Thread(target=open_browser_later, args=(url,), daemon=True).start()
    sys.argv = ['streamlit', 'run', str(app_path), '--server.port', str(port), '--server.address', '127.0.0.1', '--browser.gatherUsageStats', 'false', '--global.developmentMode', 'false']
    stcli.main()


if __name__ == '__main__':
    run_streamlit_app()