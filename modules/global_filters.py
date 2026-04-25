# Este fichero contiene los filtros globales del sidebar y aplica esos filtros a los dataframes de la aplicación de costes.
import pandas as pd
import streamlit as st


GLOBAL_PERIOD_FROM_KEY = 'global_filter_period_from'
GLOBAL_PERIOD_TO_KEY = 'global_filter_period_to'
GLOBAL_DEPARTAMENTO_KEY = 'global_filter_departamento'
GLOBAL_EMPLEADO_KEY = 'global_filter_empleado'


def get_unique_values(dataframes: list[pd.DataFrame | None], column: str) -> list[str]:
    values = set()
    for df in dataframes:
        if df is None or df.empty or column not in df.columns:
            continue
        current_values = [str(v).strip() for v in df[column].dropna().unique().tolist() if str(v).strip()]
        values.update(current_values)
    return sorted(values)


def get_available_periods(dataframes: list[pd.DataFrame | None]) -> list[str]:
    values = get_unique_values(dataframes, 'periodo')
    return [v for v in values if v != 'Sin periodo']


def reset_global_filter_state(periods: list[str]) -> None:
    # Limpia todos los filtros globales dejando Periodo, Departamento y Empleado sin selección activa.
    st.session_state[GLOBAL_PERIOD_FROM_KEY] = 'Todos'
    st.session_state[GLOBAL_PERIOD_TO_KEY] = 'Todos'
    st.session_state[GLOBAL_DEPARTAMENTO_KEY] = []
    st.session_state[GLOBAL_EMPLEADO_KEY] = []


def initialize_global_filter_state(periods: list[str]) -> None:
    # Inicializa los widgets sin aplicar filtros por defecto.
    period_options = ['Todos'] + periods
    if GLOBAL_PERIOD_FROM_KEY not in st.session_state or st.session_state[GLOBAL_PERIOD_FROM_KEY] not in period_options:
        st.session_state[GLOBAL_PERIOD_FROM_KEY] = 'Todos'
    if GLOBAL_PERIOD_TO_KEY not in st.session_state or st.session_state[GLOBAL_PERIOD_TO_KEY] not in period_options:
        st.session_state[GLOBAL_PERIOD_TO_KEY] = 'Todos'
    if GLOBAL_DEPARTAMENTO_KEY not in st.session_state:
        st.session_state[GLOBAL_DEPARTAMENTO_KEY] = []
    if GLOBAL_EMPLEADO_KEY not in st.session_state:
        st.session_state[GLOBAL_EMPLEADO_KEY] = []


def render_global_sidebar_filters(dataframes: list[pd.DataFrame | None]) -> dict:
    periods = get_available_periods(dataframes)
    period_options = ['Todos'] + periods
    departamentos = get_unique_values(dataframes, 'departamento')
    empleados = get_unique_values(dataframes, 'empleado')
    initialize_global_filter_state(periods)

    st.sidebar.markdown("<div class='indra-sidebar-section-title'>FILTROS GLOBALES</div>", unsafe_allow_html=True)

    with st.sidebar.expander('🗓️ Periodo', expanded=False):
        if periods:
            period_from_index = period_options.index(st.session_state[GLOBAL_PERIOD_FROM_KEY]) if st.session_state[GLOBAL_PERIOD_FROM_KEY] in period_options else 0
            period_to_index = period_options.index(st.session_state[GLOBAL_PERIOD_TO_KEY]) if st.session_state[GLOBAL_PERIOD_TO_KEY] in period_options else 0
            st.selectbox('Desde', options=period_options, index=period_from_index, key=GLOBAL_PERIOD_FROM_KEY)
            st.selectbox('Hasta', options=period_options, index=period_to_index, key=GLOBAL_PERIOD_TO_KEY)
        else:
            st.caption('No hay periodos disponibles.')

    with st.sidebar.expander('🏢 Departamento (Elemento)', expanded=False):
        st.multiselect('Departamento', options=departamentos, key=GLOBAL_DEPARTAMENTO_KEY)

    with st.sidebar.expander('👤 Empleado', expanded=False):
        st.multiselect('Empleado', options=empleados, key=GLOBAL_EMPLEADO_KEY)

    st.sidebar.button('🔄 Limpiar filtros', key='global_filters_clear_button', use_container_width=True, on_click=reset_global_filter_state, args=(periods,))
    st.sidebar.markdown("<div class='indra-sidebar-reset-text'>Restablecer todos los filtros</div>", unsafe_allow_html=True)

    return {'period_from': st.session_state.get(GLOBAL_PERIOD_FROM_KEY), 'period_to': st.session_state.get(GLOBAL_PERIOD_TO_KEY), 'departamentos': st.session_state.get(GLOBAL_DEPARTAMENTO_KEY, []), 'empleados': st.session_state.get(GLOBAL_EMPLEADO_KEY, [])}


def apply_period_range_filter(df: pd.DataFrame | None, period_from: str | None, period_to: str | None) -> pd.DataFrame | None:
    if df is None or df.empty or 'periodo' not in df.columns:
        return df
    if (not period_from or period_from == 'Todos') and (not period_to or period_to == 'Todos'):
        return df
    filtered = df.copy()
    if period_from and period_from != 'Todos':
        filtered = filtered[filtered['periodo'].astype(str) >= str(period_from)]
    if period_to and period_to != 'Todos':
        filtered = filtered[filtered['periodo'].astype(str) <= str(period_to)]
    return filtered


def apply_multivalue_filter(df: pd.DataFrame | None, column: str, selected_values: list[str]) -> pd.DataFrame | None:
    if df is None or df.empty or column not in df.columns or not selected_values:
        return df
    return df[df[column].astype(str).isin([str(v) for v in selected_values])].copy()


def apply_global_filters(df: pd.DataFrame | None, filters: dict) -> pd.DataFrame | None:
    filtered = apply_period_range_filter(df, filters.get('period_from'), filters.get('period_to'))
    filtered = apply_multivalue_filter(filtered, 'departamento', filters.get('departamentos', []))
    filtered = apply_multivalue_filter(filtered, 'empleado', filters.get('empleados', []))
    return filtered