# Este fichero orquesta la aplicación Streamlit de costes, carga los ficheros de entrada y delega el render en los módulos funcionales.
import streamlit as st
from pathlib import Path
import pandas as pd

from data_common import save_uploaded_file_to_temp
from modules.dedicaciones import DedicacionesModule
from ppt.dedicaciones_ppt import build_committee_presentation
from ui_common import build_metric_card, inject_custom_theme, render_indra_branding
from modules.compras_gpi import ComprasGpiModule
from modules.compras_no_gpi import ComprasNoGpiModule
from modules.almacenaje import AlmacenajeModule
from modules.global_filters import apply_global_filters, render_global_sidebar_filters



def sum_numeric_column(df, column: str) -> float:
    if df is None or df.empty or column not in df.columns:
        return 0.0
    return float(pd.to_numeric(df[column], errors='coerce').fillna(0).sum())


def count_unique_text_values(dataframes: list, column: str) -> int:
    values = set()
    for item_df in dataframes:
        if item_df is None or item_df.empty or column not in item_df.columns:
            continue
        series = item_df[column].dropna().astype(str).str.strip()
        values.update([value for value in series.tolist() if value])
    return len(values)


def build_project_summary(dedicaciones_df, compras_gpi_df, compras_no_gpi_df, almacenaje_df) -> dict:
    cost_dataframes = [dedicaciones_df, compras_gpi_df, compras_no_gpi_df, almacenaje_df]
    total_cost = sum([sum_numeric_column(item_df, 'cantidad') for item_df in cost_dataframes])
    total_hours = sum([sum_numeric_column(item_df, 'horas_aplicadas') for item_df in cost_dataframes])
    total_departments = count_unique_text_values(cost_dataframes, 'departamento')
    total_employees = count_unique_text_values(cost_dataframes, 'empleado')
    return {'total_cost': total_cost, 'total_hours': total_hours, 'total_departments': total_departments, 'total_employees': total_employees}

def run_app() -> None:
    st.set_page_config(page_title='Informe de Costes del Proyecto', layout='wide')
    inject_custom_theme()
    render_indra_branding()
    st.markdown("<div style='margin-top:-8px;'></div>", unsafe_allow_html=True)
    st.title('Informe de Costes del Proyecto')

    dedicaciones_module = DedicacionesModule()
    compras_gpi_module = ComprasGpiModule()
    compras_no_gpi_module = ComprasNoGpiModule()
    almacenaje_module = AlmacenajeModule()

    with st.expander('Carga de ficheros del proyecto', expanded=True):
        col_upload_1, col_upload_2, col_upload_3 = st.columns(3)
        with col_upload_1:
            uploaded_file = st.file_uploader('Dedicaciones personal', type=['xls', 'xlsx'], key='uploaded_dedicaciones_file')
            uploaded_compras_gpi_file = st.file_uploader('Compras GPI', type=['xls', 'xlsx'], key='uploaded_compras_gpi_file')
        with col_upload_2:
            uploaded_edt_file = st.file_uploader('EDT costes estimados', type=['xlsx'], key='uploaded_edt_file')
            uploaded_compras_no_gpi_file = st.file_uploader('Compras NO GPI', type=['xls', 'xlsx'], key='uploaded_compras_no_gpi_file')
        with col_upload_3:
            uploaded_almacenaje_files = st.file_uploader('Almacenaje', type=['xls', 'xlsx'], accept_multiple_files=True, key='uploaded_almacenaje_files')

    default_path = Path('DedicacionesS24B05_ENERO2024_ABRIL2026.xls')

    if uploaded_file is None and not default_path.exists():
        st.info('Carga el fichero Excel para generar el informe.')
        st.stop()

    source_file = save_uploaded_file_to_temp(uploaded_file, 'costes_input_') if uploaded_file is not None else default_path

    try:
        df = dedicaciones_module.load_dedicaciones_dataframe(source_file)
    except Exception as exc:
        st.error(f'No se ha podido procesar el fichero: {exc}')
        st.stop()

    filtered = df.copy()

    edt_df = None
    if uploaded_edt_file is not None:
        try:
            temp_edt_input = save_uploaded_file_to_temp(uploaded_edt_file, 'costes_edt_input_')
            edt_df = dedicaciones_module.load_edt_dataframe(temp_edt_input)
        except Exception as exc:
            st.error(f'No se ha podido procesar el fichero EDT: {exc}')
            edt_df = None

    compras_gpi_df = None
    compras_gpi_enabled = False
    if uploaded_compras_gpi_file is not None:
        try:
            temp_compras_gpi_input = save_uploaded_file_to_temp(uploaded_compras_gpi_file, 'costes_compras_gpi_input_')
            compras_gpi_df = compras_gpi_module.load_dataframe(temp_compras_gpi_input)
            compras_gpi_enabled = compras_gpi_df is not None and not compras_gpi_df.empty
        except Exception as exc:
            st.error(f'No se ha podido procesar el fichero Compras GPI: {exc}')
            compras_gpi_df = None
            compras_gpi_enabled = False

    compras_no_gpi_df = None
    compras_no_gpi_enabled = False
    if uploaded_compras_no_gpi_file is not None:
        try:
            temp_compras_input = save_uploaded_file_to_temp(uploaded_compras_no_gpi_file, 'costes_compras_no_gpi_input_')
            compras_no_gpi_df = compras_no_gpi_module.load_dataframe(temp_compras_input)
            compras_no_gpi_enabled = compras_no_gpi_df is not None and not compras_no_gpi_df.empty
        except Exception as exc:
            st.error(f'No se ha podido procesar el fichero Compras NO GPI: {exc}')
            compras_no_gpi_df = None
            compras_no_gpi_enabled = False

    almacenaje_df = None
    almacenaje_enabled = False
    if uploaded_almacenaje_files:
        try:
            temp_almacenaje_paths = [save_uploaded_file_to_temp(uploaded_file_item, 'costes_almacenaje_input_') for uploaded_file_item in uploaded_almacenaje_files]
            almacenaje_df = almacenaje_module.load_dataframes(temp_almacenaje_paths)
            almacenaje_enabled = almacenaje_df is not None and not almacenaje_df.empty
        except Exception as exc:
            st.error(f'No se ha podido procesar el fichero de Almacenaje: {exc}')
            almacenaje_df = None
            almacenaje_enabled = False

    script_dir = Path(__file__).resolve().parent
    project_summary_total = build_project_summary(df, compras_gpi_df, compras_no_gpi_df, almacenaje_df)
    global_filters = render_global_sidebar_filters([df, compras_gpi_df, compras_no_gpi_df, almacenaje_df])
    filtered = apply_global_filters(df, global_filters)
    compras_gpi_df = apply_global_filters(compras_gpi_df, global_filters)
    compras_no_gpi_df = apply_global_filters(compras_no_gpi_df, global_filters)
    almacenaje_df = apply_global_filters(almacenaje_df, global_filters)
    compras_gpi_enabled = compras_gpi_df is not None and not compras_gpi_df.empty
    compras_no_gpi_enabled = compras_no_gpi_df is not None and not compras_no_gpi_df.empty
    almacenaje_enabled = almacenaje_df is not None and not almacenaje_df.empty
    project_summary_filtered = build_project_summary(filtered, compras_gpi_df, compras_no_gpi_df, almacenaje_df)
    template_ppt_path = script_dir / 'template.pptx'

    st.markdown('### Exportación PowerPoint')
    st.caption('Genera y descarga una presentación clásica de comité de dirección con el dataset actual cargado en la app.')

    if 'ppt_bytes' not in st.session_state:
        st.session_state.ppt_bytes = None

    if st.button('Generar y descargar PowerPoint', use_container_width=True):
        if filtered.empty:
            st.error('No hay datos para generar la presentación.')
            st.session_state.ppt_bytes = None
        elif not template_ppt_path.exists():
            st.error(f'No se encuentra la plantilla PowerPoint requerida: {template_ppt_path}')
            st.session_state.ppt_bytes = None
        else:
            with st.spinner('Preparando PowerPoint...'):
                st.session_state.ppt_bytes = build_committee_presentation(filtered, str(template_ppt_path), report_title='Informe de Costes del Proyecto', document_name='Informe de Costes del Proyecto')

    
    if st.session_state.ppt_bytes is not None:
        st.download_button('Descargar PowerPoint generado', data=st.session_state.ppt_bytes, file_name='Informe_Costes_Proyecto_Indra.pptx', mime='application/vnd.openxmlformats-officedocument.presentationml.presentation', use_container_width=True)

    project_summary = build_project_summary(filtered, compras_gpi_df, compras_no_gpi_df, almacenaje_df)

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        build_metric_card('Coste total', dedicaciones_module.format_number(project_summary_total['total_cost'], 2))
    with k2:
        build_metric_card('Horas totales', dedicaciones_module.format_number(project_summary_total['total_hours'], 2))
    with k3:
        build_metric_card('Departamentos', dedicaciones_module.format_number(project_summary_total['total_departments'], 0))
    with k4:
        build_metric_card('Empleados', dedicaciones_module.format_number(project_summary_total['total_employees'], 0))

    st.markdown('---')

    tab_names = ['0. General', '1. Elemento + Departamento (Horas)', '2. Empleado + Nombre (Horas)', '3. Elemento + Departamento (Cantidad)', '4. Empleado + Nombre (Cantidad)']
    if compras_gpi_enabled:
        tab_names.append('5. Compras GPI')
    if compras_no_gpi_enabled:
        tab_names.append('6. Compras NO GPI')
    if almacenaje_enabled:
        tab_names.append('7. Almacenaje')

    tabs = st.tabs(tab_names)

    with tabs[0]:
        dedicaciones_module.render_tab_general(filtered, project_summary_total=project_summary_total, project_summary_filtered=project_summary_filtered)
    with tabs[1]:
        dedicaciones_module.render_tab_departamento_horas(filtered)
    with tabs[2]:
        dedicaciones_module.render_tab_empleado_horas(filtered)
    with tabs[3]:
        dedicaciones_module.render_tab_departamento_cantidad(filtered, edt_df)
    with tabs[4]:
        dedicaciones_module.render_tab_empleado_cantidad(filtered)

    current_tab_index = 5

    if compras_gpi_enabled:
        with tabs[current_tab_index]:
            coste_total_proyecto = float(filtered['cantidad'].sum())
            if compras_no_gpi_enabled and compras_no_gpi_df is not None:
                coste_total_proyecto += float(compras_no_gpi_df['cantidad'].sum())
            if almacenaje_enabled and almacenaje_df is not None:
                coste_total_proyecto += float(almacenaje_df['cantidad'].sum())
            compras_gpi_module.render_tab(compras_gpi_df, coste_total_proyecto=coste_total_proyecto)
        current_tab_index += 1

    if compras_no_gpi_enabled:
        with tabs[current_tab_index]:
            estimado_total = float(edt_df['estimado_rc'].sum()) if edt_df is not None and not edt_df.empty else None
            compras_no_gpi_module.render_tab(compras_no_gpi_df, coste_interno_total=float(filtered['cantidad'].sum()), estimado_total=estimado_total)
        current_tab_index += 1

    if almacenaje_enabled:
        with tabs[current_tab_index]:
            coste_total_proyecto = float(filtered['cantidad'].sum())
            if compras_gpi_enabled and compras_gpi_df is not None:
                coste_total_proyecto += float(compras_gpi_df['cantidad'].sum())
            if compras_no_gpi_enabled and compras_no_gpi_df is not None:
                coste_total_proyecto += float(compras_no_gpi_df['cantidad'].sum())
            almacenaje_module.render_tab(almacenaje_df, coste_total_proyecto=coste_total_proyecto)
