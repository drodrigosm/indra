# Modulo principal Secuencia de Montaje. Mostrara la secuencia de montaje asociada al elemento HW seleccionado en el sidebar global.

import streamlit as st
from HW_scanner import get_main_element_row


def render_assembly_sequence(df, selected_code):
    selected_row = get_main_element_row(df, selected_code)
    if selected_row is None:
        st.warning("No hay elemento HW seleccionado.")
        return
    st.subheader(f"Secuencia de Montaje - {selected_row.get('code', '')} - {selected_row.get('component', '')}")
    st.info("Modulo Secuencia de Montaje pendiente de implementacion.")