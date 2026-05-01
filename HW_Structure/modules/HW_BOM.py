# Modulo principal BOM. Mostrara informacion BOM asociada al elemento HW seleccionado en el sidebar global.

import streamlit as st
from HW_scanner import get_main_element_row


def render_bom(df, selected_code):
    selected_row = get_main_element_row(df, selected_code)
    if selected_row is None:
        st.warning("No hay elemento HW seleccionado.")
        return
    st.subheader(f"BOM - {selected_row.get('code', '')} - {selected_row.get('component', '')}")
    st.info("Modulo BOM pendiente de implementacion.")