# Este fichero orquesta la aplicación Streamlit de costes, carga los ficheros de entrada y delega el render en los módulos funcionales.
import streamlit as st
from pathlib import Path
import pandas as pd

from data_common import save_uploaded_file_to_temp
from modules.dedicaciones import DedicacionesModule
from ppt.dedicaciones_ppt import build_committee_presentation
from HW_ui_common import build_metric_card, inject_custom_theme, render_indra_branding
from modules.compras_gpi import ComprasGpiModule
from modules.compras_no_gpi import ComprasNoGpiModule
from modules.almacenaje import AlmacenajeModule
from modules.global_filters import apply_global_filters, render_global_sidebar_filters
from modules.gastos_viaje import GastosViajeModule

def build_navigation_sections(compras_gpi_enabled: bool, compras_no_gpi_enabled: bool, almacenaje_enabled: bool, gastos_viaje_enabled: bool) -> list[dict]:
    sections = [{'key': 'general', 'label': 'General', 'sidebar_label': '1. General', 'icon': '▣'}, {'key': 'departamento_horas', 'label': 'Departamento (hs)', 'sidebar_label': '2. Departamento (hs)', 'icon': '▦'}, {'key': 'empleado_horas', 'label': 'Empleado (hs)', 'sidebar_label': '3. Empleado (hs)', 'icon': '▦'}, {'key': 'departamento_cantidad', 'label': 'Departamento (€)', 'sidebar_label': '4. Departamento (€)', 'icon': '▦'}, {'key': 'empleado_cantidad', 'label': 'Empleado (€)', 'sidebar_label': '5. Empleado (€)', 'icon': '▦'}]
    if compras_gpi_enabled:
        sections.append({'key': 'compras_gpi', 'label': 'Compras GPI', 'sidebar_label': f'{len(sections) + 1}. Compras GPI', 'icon': '🛒'})
    if compras_no_gpi_enabled:
        sections.append({'key': 'compras_no_gpi', 'label': 'Compras NO GPI', 'sidebar_label': f'{len(sections) + 1}. Compras NO GPI', 'icon': '▤'})
    if almacenaje_enabled:
        sections.append({'key': 'almacenaje', 'label': 'Almacenaje', 'sidebar_label': f'{len(sections) + 1}. Almacenaje', 'icon': '▧'})
    if gastos_viaje_enabled:
        sections.append({'key': 'gastos_viaje', 'label': 'Gastos Viaje', 'sidebar_label': f'{len(sections) + 1}. Gastos Viaje', 'icon': '✈'})
    return sections


def sync_navigation_from_sidebar() -> None:
    st.session_state.active_navigation_section = st.session_state.sidebar_navigation_section
    st.session_state.top_navigation_section = st.session_state.sidebar_navigation_section


def sync_navigation_from_top() -> None:
    st.session_state.active_navigation_section = st.session_state.top_navigation_section
    st.session_state.sidebar_navigation_section = st.session_state.top_navigation_section


def render_navigation(sections: list[dict]) -> str:
    section_keys = [section['key'] for section in sections]
    default_key = section_keys[0]
    if 'active_navigation_section' not in st.session_state or st.session_state.active_navigation_section not in section_keys:
        st.session_state.active_navigation_section = default_key
    st.session_state.sidebar_navigation_section = st.session_state.active_navigation_section
    st.session_state.top_navigation_section = st.session_state.active_navigation_section
    label_by_key = {section['key']: f"{section['icon']}  {section['sidebar_label']}" for section in sections}
    top_label_by_key = {section['key']: section['label'] for section in sections}
    st.sidebar.markdown("<div class='indra-sidebar-section-title indra-navigation-title'>NAVEGACIÓN</div>", unsafe_allow_html=True)
    st.sidebar.radio('Navegación', options=section_keys, format_func=lambda key: label_by_key[key], key='sidebar_navigation_section', label_visibility='collapsed', on_change=sync_navigation_from_sidebar)
    st.radio('Secciones', options=section_keys, format_func=lambda key: top_label_by_key[key], key='top_navigation_section', label_visibility='collapsed', horizontal=True, on_change=sync_navigation_from_top)
    return st.session_state.active_navigation_section


def calculate_project_cost(filtered, compras_gpi_df, compras_no_gpi_df, almacenaje_df, gastos_viaje_df=None) -> float:
    total = sum_numeric_column(filtered, 'cantidad')
    total += sum_numeric_column(compras_gpi_df, 'cantidad')
    total += sum_numeric_column(compras_no_gpi_df, 'cantidad')
    total += sum_numeric_column(almacenaje_df, 'cantidad')
    total += sum_numeric_column(gastos_viaje_df, 'cantidad')
    return total

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


def build_project_summary(dedicaciones_df, compras_gpi_df, compras_no_gpi_df, almacenaje_df, gastos_viaje_df=None) -> dict:
    cost_dataframes = [dedicaciones_df, compras_gpi_df, compras_no_gpi_df, almacenaje_df, gastos_viaje_df]
    total_cost = sum([sum_numeric_column(item_df, 'cantidad') for item_df in cost_dataframes])
    total_hours = sum([sum_numeric_column(item_df, 'horas_aplicadas') for item_df in cost_dataframes])
    total_departments = count_unique_text_values(cost_dataframes, 'departamento')
    total_employees = count_unique_text_values(cost_dataframes, 'empleado')
    return {'total_cost': total_cost, 'total_hours': total_hours, 'total_departments': total_departments, 'total_employees': total_employees}

def filename_contains(file_name: str, tokens: list[str], match_all: bool = False) -> bool:
    normalized_name = file_name.upper()
    normalized_tokens = [token.upper() for token in tokens]
    return all(token in normalized_name for token in normalized_tokens) if match_all else any(token in normalized_name for token in normalized_tokens)


def classify_uploaded_project_files(uploaded_files: list) -> dict:
    classified = {'dedicaciones': None, 'edt': None, 'compras_gpi': None, 'compras_no_gpi': None, 'almacenaje': [], 'gastos_viaje': [], 'ignored': []}
    for uploaded_file in uploaded_files or []:
        file_name = uploaded_file.name.upper()
        if filename_contains(file_name, ['DEDICACIONES', 'ISPR_25D']):
            classified['dedicaciones'] = uploaded_file
        elif filename_contains(file_name, ['ISPR_25C']):
            classified['compras_no_gpi'] = uploaded_file
        elif filename_contains(file_name, ['ISPR25PX','ISPR_25PX']):
            classified['compras_gpi'] = uploaded_file
        elif filename_contains(file_name, ['ISPR_25S', 'ISPR_25U']):
            classified['almacenaje'].append(uploaded_file)
        elif filename_contains(file_name, ['ISPR_25F', 'ISPR_25G']):
            classified['gastos_viaje'].append(uploaded_file)
        elif filename_contains(file_name, ['EDT']):
            classified['edt'] = uploaded_file
        else:
            classified['ignored'].append(uploaded_file.name)
    return classified

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
    gastos_viaje_module = GastosViajeModule()

    with st.expander('Carga de carpeta del proyecto', expanded=True):
        uploaded_project_files = st.file_uploader('Selecciona la carpeta del proyecto', type=['xls', 'xlsx'], accept_multiple_files=True, key='uploaded_project_folder')
        st.caption('La app detecta automáticamente: Dedicaciones (ISPR_25D), Compras NO GPI (ISPR_25C), Compras GPI (ISPR_25PX), Almacenaje (IPSR_25S y/o ISPR_25U) y Gastos de Viaje (ISPR_25F y/o ISPR_25G) según el nombre del fichero.')

    classified_files = classify_uploaded_project_files(uploaded_project_files)
    if classified_files['ignored']:
        st.warning('Ficheros ignorados por no coincidir con ninguna regla: ' + ', '.join(classified_files['ignored']))

    df = None
    filtered = None
    dedicaciones_enabled = False
    if classified_files['dedicaciones'] is not None:
        try:
            temp_dedicaciones_input = save_uploaded_file_to_temp(classified_files['dedicaciones'], 'costes_dedicaciones_input_')
            df = dedicaciones_module.load_dedicaciones_dataframe(temp_dedicaciones_input)
            filtered = df.copy()
            dedicaciones_enabled = df is not None and not df.empty
        except Exception as exc:
            st.error(f'No se ha podido procesar el fichero de Dedicaciones: {exc}')
            df = None
            filtered = None
            dedicaciones_enabled = False

    edt_df = None
    if classified_files['edt'] is not None:
        try:
            temp_edt_input = save_uploaded_file_to_temp(classified_files['edt'], 'costes_edt_input_')
            edt_df = dedicaciones_module.load_edt_dataframe(temp_edt_input)
        except Exception as exc:
            st.error(f'No se ha podido procesar el fichero EDT: {exc}')
            edt_df = None

    compras_gpi_df = None
    compras_gpi_enabled = False
    if classified_files['compras_gpi'] is not None:
        try:
            temp_compras_gpi_input = save_uploaded_file_to_temp(classified_files['compras_gpi'], 'costes_compras_gpi_input_')
            compras_gpi_df = compras_gpi_module.load_dataframe(temp_compras_gpi_input)
            compras_gpi_enabled = compras_gpi_df is not None and not compras_gpi_df.empty
        except Exception as exc:
            st.error(f'No se ha podido procesar el fichero Compras GPI: {exc}')
            compras_gpi_df = None
            compras_gpi_enabled = False

    compras_no_gpi_df = None
    compras_no_gpi_enabled = False
    if classified_files['compras_no_gpi'] is not None:
        try:
            temp_compras_input = save_uploaded_file_to_temp(classified_files['compras_no_gpi'], 'costes_compras_no_gpi_input_')
            compras_no_gpi_df = compras_no_gpi_module.load_dataframe(temp_compras_input)
            compras_no_gpi_enabled = compras_no_gpi_df is not None and not compras_no_gpi_df.empty
        except Exception as exc:
            st.error(f'No se ha podido procesar el fichero Compras NO GPI: {exc}')
            compras_no_gpi_df = None
            compras_no_gpi_enabled = False

    almacenaje_df = None
    almacenaje_enabled = False
    if classified_files['almacenaje']:
        try:
            temp_almacenaje_paths = [save_uploaded_file_to_temp(uploaded_file_item, 'costes_almacenaje_input_') for uploaded_file_item in classified_files['almacenaje']]
            almacenaje_df = almacenaje_module.load_dataframes(temp_almacenaje_paths)
            almacenaje_enabled = almacenaje_df is not None and not almacenaje_df.empty
        except Exception as exc:
            st.error(f'No se ha podido procesar el fichero de Almacenaje: {exc}')
            almacenaje_df = None
            almacenaje_enabled = False

    gastos_viaje_df = None
    gastos_viaje_enabled = False
    if classified_files['gastos_viaje']:
        try:
            temp_gastos_viaje_paths = [save_uploaded_file_to_temp(uploaded_file_item, 'costes_gastos_viaje_input_') for uploaded_file_item in classified_files['gastos_viaje']]
            gastos_viaje_df = gastos_viaje_module.load_dataframes(temp_gastos_viaje_paths)
            gastos_viaje_enabled = gastos_viaje_df is not None and not gastos_viaje_df.empty
        except Exception as exc:
            st.error(f'No se ha podido procesar el fichero de Gastos de Viaje: {exc}')
            gastos_viaje_df = None
            gastos_viaje_enabled = False

    if not dedicaciones_enabled and not compras_gpi_enabled and not compras_no_gpi_enabled and not almacenaje_enabled and not gastos_viaje_enabled:
        st.info('Carga al menos un fichero válido del proyecto para generar el informe.')
        st.stop()

    script_dir = Path(__file__).resolve().parent
    project_summary_total = build_project_summary(df, compras_gpi_df, compras_no_gpi_df, almacenaje_df, gastos_viaje_df)
    global_filters = render_global_sidebar_filters([df, compras_gpi_df, compras_no_gpi_df, almacenaje_df, gastos_viaje_df])
    filtered = apply_global_filters(df, global_filters)
    compras_gpi_df = apply_global_filters(compras_gpi_df, global_filters)
    compras_no_gpi_df = apply_global_filters(compras_no_gpi_df, global_filters)
    almacenaje_df = apply_global_filters(almacenaje_df, global_filters)
    gastos_viaje_df = apply_global_filters(gastos_viaje_df, global_filters)
    compras_gpi_enabled = compras_gpi_df is not None and not compras_gpi_df.empty
    compras_no_gpi_enabled = compras_no_gpi_df is not None and not compras_no_gpi_df.empty
    almacenaje_enabled = almacenaje_df is not None and not almacenaje_df.empty
    gastos_viaje_enabled = gastos_viaje_df is not None and not gastos_viaje_df.empty
    project_summary_filtered = build_project_summary(filtered, compras_gpi_df, compras_no_gpi_df, almacenaje_df, gastos_viaje_df)
    template_ppt_path = script_dir / 'template.pptx'

    st.markdown('### Exportación PowerPoint')

    if 'ppt_bytes' not in st.session_state:
        st.session_state.ppt_bytes = None

    if st.button('Generar y descargar PowerPoint', use_container_width=True):
        if filtered is None or filtered.empty:
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
        build_metric_card('Coste total', dedicaciones_module.format_number(project_summary_total['total_cost'], 2))
    with k2:
        build_metric_card('Horas totales', dedicaciones_module.format_number(project_summary_total['total_hours'], 2))
    with k3:
        build_metric_card('Departamentos', dedicaciones_module.format_number(project_summary_total['total_departments'], 0))
    with k4:
        build_metric_card('Empleados', dedicaciones_module.format_number(project_summary_total['total_employees'], 0))

    st.markdown('---')

    navigation_sections = build_navigation_sections(compras_gpi_enabled, compras_no_gpi_enabled, almacenaje_enabled, gastos_viaje_enabled)
    selected_section = render_navigation(navigation_sections)

    if selected_section == 'general':
        dedicaciones_module.render_tab_general(filtered, project_summary_total=project_summary_total, project_summary_filtered=project_summary_filtered, compras_gpi_df=compras_gpi_df)
    elif selected_section == 'departamento_horas':
        dedicaciones_module.render_tab_departamento_horas(filtered)
    elif selected_section == 'empleado_horas':
        dedicaciones_module.render_tab_empleado_horas(filtered)
    elif selected_section == 'departamento_cantidad':
        dedicaciones_module.render_tab_departamento_cantidad(filtered, edt_df)
    elif selected_section == 'empleado_cantidad':
        dedicaciones_module.render_tab_empleado_cantidad(filtered)
    elif selected_section == 'compras_gpi':
        compras_gpi_module.render_tab(compras_gpi_df, coste_total_proyecto=calculate_project_cost(filtered, compras_gpi_df, compras_no_gpi_df, almacenaje_df, gastos_viaje_df))
    elif selected_section == 'compras_no_gpi':
        estimado_total = float(edt_df['estimado_rc'].sum()) if edt_df is not None and not edt_df.empty else None
        compras_no_gpi_module.render_tab(compras_no_gpi_df, coste_interno_total=sum_numeric_column(filtered, 'cantidad'), estimado_total=estimado_total)
    elif selected_section == 'almacenaje':
        almacenaje_module.render_tab(almacenaje_df, coste_total_proyecto=calculate_project_cost(filtered, compras_gpi_df, compras_no_gpi_df, almacenaje_df, gastos_viaje_df))
    elif selected_section == 'gastos_viaje':
        gastos_viaje_module.render_tab(gastos_viaje_df, coste_total_proyecto=calculate_project_cost(filtered, compras_gpi_df, compras_no_gpi_df, almacenaje_df, gastos_viaje_df))