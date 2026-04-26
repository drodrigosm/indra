# Componentes visuales comunes de Streamlit reutilizables por los distintos modulos de la aplicacion.

import streamlit as st
from hw_scanner import get_direct_content


def render_file_table(path):
    content = get_direct_content(path)
    if content.empty:
        st.caption("Sin contenido directo.")
        return
    st.dataframe(content[["tipo", "codigo", "nivel", "nombre", "tamano", "ruta"]], use_container_width=True, hide_index=True)


def render_level_summary(df):
    if df.empty:
        return
    summary = df.groupby("level").agg(elementos=("code", "count"), carpetas=("dirs", "sum"), ficheros=("files", "sum")).reset_index()
    summary["nivel"] = summary["level"].apply(lambda value: f"Nivel {int(value)}")
    st.dataframe(summary[["nivel", "elementos", "carpetas", "ficheros"]], use_container_width=True, hide_index=True)