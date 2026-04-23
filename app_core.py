# Este fichero orquesta la aplicación Streamlit de costes, carga los ficheros de entrada y delega el render en los módulos funcionales.
import streamlit as st
from pathlib import Path

from data_common import save_uploaded_file_to_temp
from modules.dedicaciones import DedicacionesModule
from ppt.dedicaciones_ppt import build_committee_presentation
from ui_common import build_metric_card, inject_custom_theme, render_indra_branding


def run_app() -> None:
    st.set_page_config(page_title='Informe de Costes del Proyecto', layout='wide')
    inject_custom_theme()
    render_indra_branding()
    st.markdown("<div style='margin-top:-8px;'></div>", unsafe_allow_html=True)
    st.title('Informe de Costes del Proyecto')

    dedicaciones_module = DedicacionesModule()

    uploaded_file = st.file_uploader('Carga el Excel de dedicaciones (.xls o .xlsx)', type=['xls', 'xlsx'])
    uploaded_edt_file = st.file_uploader('Carga el Excel EDT de costes estimados (.xlsx)', type=['xlsx'], key='uploaded_edt_file')
    default_path = Path('DedicacionesS24B05_ENERO2024_ABRIL2026.xls')

    if uploaded_file is None and not default_path.exists():
        st.info('Carga el fichero Excel para generar el informe.')
        st.stop()

    if uploaded_file is not None:
        source_file = save_uploaded_file_to_temp(uploaded_file, 'costes_input_')
    else:
        source_file = default_path

    try:
        df = dedicaciones_module.load_dedicaciones_dataframe(source_file)
    except Exception as exc:
        st.error(f'No se ha podido procesar el fichero: {exc}')
        st.stop()

    filtered = dedicaciones_module.render_global_filters(df)

    edt_df = None
    if uploaded_edt_file is not None:
        try:
            temp_edt_input = save_uploaded_file_to_temp(uploaded_edt_file, 'costes_edt_input_')
            edt_df = dedicaciones_module.load_edt_dataframe(temp_edt_input)
        except Exception as exc:
            st.error(f'No se ha podido procesar el fichero EDT: {exc}')
            edt_df = None

    script_dir = Path(__file__).resolve().parent
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

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        build_metric_card('Coste total', dedicaciones_module.format_number(filtered['cantidad'].sum(), 2))
    with k2:
        build_metric_card('Horas totales', dedicaciones_module.format_number(filtered['horas_aplicadas'].sum(), 2))
    with k3:
        build_metric_card('Departamentos', dedicaciones_module.format_number(filtered['departamento'].nunique(), 0))
    with k4:
        build_metric_card('Empleados', dedicaciones_module.format_number(filtered['empleado'].nunique(), 0))

    st.markdown('---')

    tab0, tab1, tab2, tab3, tab4 = st.tabs(['0. General', '1. Elemento + Departamento (Horas)', '2. Empleado + Nombre (Horas)', '3. Elemento + Departamento (Cantidad)', '4. Empleado + Nombre (Cantidad)'])

    with tab0:
        dedicaciones_module.render_tab_general(filtered)
    with tab1:
        dedicaciones_module.render_tab_departamento_horas(filtered)
    with tab2:
        dedicaciones_module.render_tab_empleado_horas(filtered)
    with tab3:
        dedicaciones_module.render_tab_departamento_cantidad(filtered, edt_df)
    with tab4:
        dedicaciones_module.render_tab_empleado_cantidad(filtered)