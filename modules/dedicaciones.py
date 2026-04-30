# Este fichero contiene toda la lógica funcional de dedicaciones y EDT: carga de datos, filtros, agregaciones, gráficos y render de pestañas.
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from data_common import normalize_text_key, read_excel_robust
from ui_common import DISPLAY_COLUMNS, PALETTE, PLOTLY_COLOR_SEQUENCE, build_metric_card, format_number, render_corporate_dataframe


class DedicacionesModule:
    RAW_COLUMNS = [
        'tipo_empleado', 'unidad_empresa_codigo', 'unidad_empresa_nombre', 'proyecto_codigo', 'proyecto_nombre', 'linea_negocio_codigo', 'linea_negocio_nombre', 'estado',
        'elemento_codigo', 'elemento_nombre', 'empleado_codigo', 'empleado_nombre', 'unidad_de_empresa_codigo', 'unidad_de_empresa_nombre', 'empresa_codigo', 'empresa_nombre',
        'fecha', 'categoria_codigo', 'categoria_nombre', 'horas_aplicadas', 'tasa', 'codigo_coste', 'codigo_coste_nombre', 'tipo_coste_codigo', 'tipo_coste_nombre',
        'cantidad', 'nota_cargo', 'integracion_sucursal'
    ]

    def format_number(self, value: float, decimals: int = 2) -> str:
        return format_number(value, decimals)

    def load_dedicaciones_dataframe(self, file_path: Path) -> pd.DataFrame:
        df_raw = read_excel_robust(file_path, sheet_name='Hoja1', header=None)
        if df_raw.shape[1] < len(self.RAW_COLUMNS):
            raise RuntimeError(f'El Excel no tiene las columnas esperadas. Columnas detectadas: {df_raw.shape[1]}')

        df = df_raw.iloc[12:, :len(self.RAW_COLUMNS)].copy()
        df.columns = self.RAW_COLUMNS
        df = df.dropna(how='all')
        df['elemento_codigo'] = df['elemento_codigo'].astype('string').str.strip()
        df['elemento_nombre'] = df['elemento_nombre'].astype('string').str.strip()
        df['empleado_codigo'] = df['empleado_codigo'].astype('string').str.strip()
        df['empleado_nombre'] = df['empleado_nombre'].astype('string').str.strip()
        df['elemento'] = df['elemento_codigo'].fillna('')
        df['nombre'] = df['empleado_nombre'].fillna('')
        df['departamento'] = (df['elemento_codigo'].fillna('') + ' - ' + df['elemento_nombre'].fillna('')).str.strip(' -')
        df['empleado'] = (df['empleado_codigo'].fillna('') + ' - ' + df['empleado_nombre'].fillna('')).str.strip(' -')
        df['departamento'] = df['departamento'].replace('', 'Sin departamento')
        df['empleado'] = df['empleado'].replace('', 'Sin empleado')
        df['fecha'] = pd.to_datetime(df['fecha'].astype('string').str.strip(), format='%m/%Y', errors='coerce')
        for col in ['horas_aplicadas', 'tasa', 'cantidad']:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        df = df[(df['horas_aplicadas'] != 0) | (df['cantidad'] != 0)].copy()
        df['periodo'] = df['fecha'].dt.strftime('%Y-%m').fillna('Sin periodo')
        return df

    def load_edt_dataframe(self, file_path: Path) -> pd.DataFrame:
        df_raw = pd.read_excel(file_path, sheet_name='EDT', header=None)
        header_row_idx = None

        for idx in range(min(20, len(df_raw))):
            row_values = [str(v).strip() for v in df_raw.iloc[idx].tolist()]
            if 'Código EDT' in row_values and 'Descripción' in row_values and 'RC' in row_values:
                header_row_idx = idx
                break

        if header_row_idx is None:
            raise RuntimeError('No se ha encontrado la cabecera esperada en la hoja EDT. Deben existir las columnas "Código EDT", "Descripción" y "RC".')

        df = df_raw.iloc[header_row_idx + 1:].copy()
        df.columns = [str(v).strip() for v in df_raw.iloc[header_row_idx].tolist()]
        df = df.dropna(how='all')

        required_cols = ['Código EDT', 'Descripción', 'RC']
        for col in required_cols:
            if col not in df.columns:
                raise RuntimeError(f'No existe la columna requerida "{col}" en la hoja EDT.')

        df['Código EDT'] = df['Código EDT'].astype('string').str.strip()
        df['Descripción'] = df['Descripción'].astype('string').str.strip()
        df['RC'] = pd.to_numeric(df['RC'], errors='coerce').fillna(0)
        df = df[(df['Código EDT'].fillna('') != '') & (df['Descripción'].fillna('') != '')].copy()
        df['departamento'] = (df['Código EDT'].fillna('') + ' - ' + df['Descripción'].fillna('')).str.strip(' -')
        df['departamento_key'] = df['departamento'].apply(normalize_text_key)
        df = df[df['RC'].notna()].copy()
        df_grouped = df.groupby(['departamento_key', 'departamento'], as_index=False).agg(estimado_rc=('RC', 'sum'))
        return df_grouped

    def aggregate_department_cost_comparison(self, df_incurrido: pd.DataFrame, df_edt: pd.DataFrame | None) -> pd.DataFrame:
        incurrido = df_incurrido.groupby('departamento', as_index=False).agg(incurrido=('cantidad', 'sum'))
        incurrido['departamento_key'] = incurrido['departamento'].apply(normalize_text_key)

        if df_edt is None or df_edt.empty:
            incurrido['estimado_rc'] = 0.0
            incurrido['desviacion'] = incurrido['incurrido'] - incurrido['estimado_rc']
            comparison = incurrido[['departamento', 'incurrido', 'estimado_rc', 'desviacion']].copy()
            comparison = comparison[~((comparison['incurrido'] == 0) & (comparison['estimado_rc'] == 0))].copy()
            return comparison.sort_values(['incurrido', 'estimado_rc'], ascending=False)

        edt = df_edt[['departamento_key', 'departamento', 'estimado_rc']].copy()
        edt = edt.rename(columns={'departamento': 'departamento_edt'})
        comparison = incurrido.merge(edt, on='departamento_key', how='outer')
        comparison['incurrido'] = pd.to_numeric(comparison['incurrido'], errors='coerce').fillna(0)
        comparison['estimado_rc'] = pd.to_numeric(comparison['estimado_rc'], errors='coerce').fillna(0)
        comparison['departamento'] = comparison['departamento'].fillna(comparison['departamento_edt']).fillna('')
        comparison['departamento'] = comparison['departamento'].astype('string').str.strip()
        comparison = comparison[comparison['departamento'] != ''].copy()
        comparison['desviacion'] = comparison['incurrido'] - comparison['estimado_rc']
        comparison = comparison[['departamento', 'incurrido', 'estimado_rc', 'desviacion']].copy()
        comparison = comparison[~((comparison['incurrido'] == 0) & (comparison['estimado_rc'] == 0))].copy()
        comparison = comparison.sort_values(['incurrido', 'estimado_rc'], ascending=False)
        return comparison

    def get_department_cost_comparison_status(self, df_comparison: pd.DataFrame) -> tuple[list, list]:
        if df_comparison is None or df_comparison.empty:
            return [], []
        no_incurrido = df_comparison[df_comparison['incurrido'] == 0]['departamento'].dropna().astype(str).tolist()
        no_estimado = df_comparison[df_comparison['estimado_rc'] == 0]['departamento'].dropna().astype(str).tolist()
        return no_incurrido, no_estimado

    def aggregate_for_dimension(self, df: pd.DataFrame, dimension: str, metric: str) -> pd.DataFrame:
        grouped = df.groupby(dimension, dropna=False, as_index=False).agg(horas_aplicadas=('horas_aplicadas', 'sum'), cantidad=('cantidad', 'sum'), empleados=('empleado', 'nunique'), departamentos=('departamento', 'nunique'))
        grouped = grouped.sort_values(metric, ascending=False)
        return grouped

    def aggregate_timeline(self, df: pd.DataFrame, dimension: str, metric: str) -> pd.DataFrame:
        timeline = df.groupby(['periodo', dimension], dropna=False, as_index=False)[metric].sum().sort_values(['periodo', metric], ascending=[True, False])
        return timeline

    def aggregate_monthly_entity(self, df: pd.DataFrame, metric: str, departamento: str, empleado: str) -> pd.DataFrame:
        filtered_df = df.copy()
        if departamento != 'Todos':
            filtered_df = filtered_df[filtered_df['departamento'] == departamento]
        if empleado != 'Todos':
            filtered_df = filtered_df[filtered_df['empleado'] == empleado]
        monthly = filtered_df.groupby('periodo', dropna=False, as_index=False)[metric].sum().sort_values('periodo')
        return monthly

    def aggregate_monthly_single_selector(self, df: pd.DataFrame, dimension: str, selected_value: str, metric: str = 'horas_aplicadas') -> pd.DataFrame:
        filtered_df = df.copy()
        if selected_value != 'Todos':
            filtered_df = filtered_df[filtered_df[dimension] == selected_value]
        monthly = filtered_df.groupby('periodo', dropna=False, as_index=False)[metric].sum().sort_values('periodo')
        return monthly

    def plot_general_metric_evolution(self, df_plot: pd.DataFrame, metric: str, title: str) -> None:
        metric_color_map = {'horas_aplicadas': PALETTE['turquesa'], 'cantidad': '#7BCFD4'}
        metric_label_map = {'horas_aplicadas': 'Horas', 'cantidad': 'Cantidad (€)'}
        color = metric_color_map.get(metric, PALETTE['turquesa'])
        y_title = metric_label_map.get(metric, metric)

        def abbreviate_value(value: float) -> str:
            abs_value = abs(value)
            if abs_value >= 1000000:
                return f"{value / 1000000:.1f}M".replace('.', ',')
            if abs_value >= 1000:
                return f"{value / 1000:.1f}k".replace('.', ',')
            return format_number(value, 0 if float(value).is_integer() else 2)

        plot_df = df_plot.copy()
        plot_df[metric] = plot_df[metric].fillna(0)
        plot_df['label_valor'] = plot_df[metric].apply(abbreviate_value)

        fig = px.bar(plot_df, x='periodo', y=metric, title=title, text='label_valor')
        fig.update_traces(marker_color=color, textposition='outside', textfont=dict(color=PALETTE['texto_claro'], size=12), cliponaxis=False, hovertemplate='%{x}<br>%{y:,.2f}<extra></extra>')
        fig.update_layout(height=520, xaxis_title='Periodo', yaxis_title=y_title, margin=dict(l=10, r=10, t=60, b=10), paper_bgcolor=PALETTE['azul_amazonico'], plot_bgcolor=PALETTE['azul_amazonico'], font=dict(color=PALETTE['texto_claro']), title_font=dict(color=PALETTE['texto_claro']), xaxis=dict(type='category', categoryorder='array', categoryarray=plot_df['periodo'].tolist(), tickmode='array', tickvals=plot_df['periodo'].tolist(), ticktext=plot_df['periodo'].tolist(), gridcolor='rgba(227,226,218,0.18)', zerolinecolor='rgba(227,226,218,0.18)', tickfont=dict(color=PALETTE['texto_claro']), title=dict(font=dict(color=PALETTE['texto_claro']))), yaxis=dict(gridcolor='rgba(227,226,218,0.18)', zerolinecolor='rgba(227,226,218,0.18)', tickfont=dict(color=PALETTE['texto_claro']), title=dict(font=dict(color=PALETTE['texto_claro']))), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    def plot_general_compras_gpi_monthly_amount(self, df_plot: pd.DataFrame, title: str, key: str) -> None:
        plot_df = df_plot.copy()
        plot_df['label_valor'] = plot_df['cantidad'].apply(lambda v: format_number(v, 0))
        fig = px.bar(plot_df, x='periodo', y='cantidad', title=title, text='label_valor')
        fig.update_traces(marker_color=PALETTE['turquesa'], textposition='outside', textfont=dict(color=PALETTE['texto_claro'], size=12), cliponaxis=False, hovertemplate='%{x}<br>%{y:,.2f} €<extra></extra>')
        fig.update_layout(height=520, xaxis_title='Periodo', yaxis_title='Importe (€)', margin=dict(l=10, r=10, t=60, b=10), paper_bgcolor=PALETTE['azul_amazonico'], plot_bgcolor=PALETTE['azul_amazonico'], font=dict(color=PALETTE['texto_claro']), title_font=dict(color=PALETTE['texto_claro']), xaxis=dict(type='category', gridcolor='rgba(227,226,218,0.18)', zerolinecolor='rgba(227,226,218,0.18)'), yaxis=dict(gridcolor='rgba(227,226,218,0.18)', zerolinecolor='rgba(227,226,218,0.18)'), showlegend=False)
        st.plotly_chart(fig, use_container_width=True, key=key)

    def plot_bar(self, df_plot: pd.DataFrame, x_col: str, y_col: str, title: str) -> None:
        plot_df = df_plot.copy()
        fig = px.bar(plot_df, x=y_col, y=x_col, orientation='h', text_auto='.2s', title=title, color=x_col, color_discrete_sequence=PLOTLY_COLOR_SEQUENCE)
        fig.update_traces(hovertemplate='%{y}<br>%{x:,.2f}<extra></extra>', marker_line_color=PALETTE['gris_ceramica'], marker_line_width=0.5)
        fig.update_layout(height=max(600, 34 * len(plot_df) + 180), yaxis_title='', xaxis_title=DISPLAY_COLUMNS.get(y_col, y_col.replace('_', ' ').title()), margin=dict(l=10, r=10, t=60, b=10), paper_bgcolor=PALETTE['azul_amazonico'], plot_bgcolor=PALETTE['azul_amazonico'], font=dict(color=PALETTE['texto_claro']), title_font=dict(color=PALETTE['texto_claro']), xaxis=dict(gridcolor='rgba(227,226,218,0.18)', zerolinecolor='rgba(227,226,218,0.18)', tickfont=dict(color=PALETTE['texto_claro']), title=dict(font=dict(color=PALETTE['texto_claro']))), yaxis=dict(gridcolor='rgba(227,226,218,0.10)', tickfont=dict(color=PALETTE['texto_claro']), title=dict(font=dict(color=PALETTE['texto_claro']))), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    def plot_department_cost_comparison(self, df_plot: pd.DataFrame, title: str) -> None:
        plot_df = df_plot.copy()
        plot_df = plot_df.melt(id_vars=['departamento'], value_vars=['incurrido', 'estimado_rc'], var_name='tipo_coste', value_name='valor')
        plot_df['tipo_coste'] = plot_df['tipo_coste'].replace({'incurrido': 'Incurrido (€)', 'estimado_rc': 'Estimado RC (€)'})
        plot_df['label_valor'] = plot_df['valor'].apply(lambda v: format_number(v, 0))

        fig = px.bar(plot_df, y='departamento', x='valor', color='tipo_coste', orientation='h', barmode='group', title=title, color_discrete_map={'Incurrido (€)': PALETTE['turquesa'], 'Estimado RC (€)': '#7BCFD4'}, text='label_valor')
        fig.update_traces(textposition='outside', textfont=dict(color=PALETTE['texto_claro'], size=12), cliponaxis=False, hovertemplate='%{y}<br>%{fullData.name}: %{x:,.2f} €<extra></extra>')
        fig.update_layout(height=max(760, 46 * df_plot['departamento'].nunique() + 180), xaxis_title='Cantidad (€)', yaxis_title='Departamento', margin=dict(l=10, r=40, t=60, b=10), paper_bgcolor=PALETTE['azul_amazonico'], plot_bgcolor=PALETTE['azul_amazonico'], font=dict(color=PALETTE['texto_claro']), title_font=dict(color=PALETTE['texto_claro']), legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0, title_text=''), xaxis=dict(gridcolor='rgba(227,226,218,0.18)', zerolinecolor='rgba(227,226,218,0.18)', tickfont=dict(color=PALETTE['texto_claro']), title=dict(font=dict(color=PALETTE['texto_claro']))), yaxis=dict(type='category', categoryorder='array', categoryarray=df_plot['departamento'].tolist(), tickfont=dict(color=PALETTE['texto_claro']), title=dict(font=dict(color=PALETTE['texto_claro']))))
        st.plotly_chart(fig, use_container_width=True)

    def plot_timeline(self, df_plot: pd.DataFrame, dimension: str, metric: str, title: str) -> None:
        fig = px.line(df_plot, x='periodo', y=metric, color=dimension, markers=True, title=title, color_discrete_sequence=PLOTLY_COLOR_SEQUENCE)
        total_traces = len(fig.data)

        for idx, trace in enumerate(fig.data):
            trace.line.width = 2
            trace.marker.size = 6
            trace.line.color = PLOTLY_COLOR_SEQUENCE[idx % len(PLOTLY_COLOR_SEQUENCE)]
            trace.marker.color = PLOTLY_COLOR_SEQUENCE[idx % len(PLOTLY_COLOR_SEQUENCE)]

        fig.update_layout(height=560, xaxis_title='Periodo', yaxis_title=DISPLAY_COLUMNS.get(metric, metric.replace('_', ' ').title()), margin=dict(l=10, r=260, t=110, b=10), title=dict(x=0.01, xanchor='left', y=0.98, yanchor='top', font=dict(color=PALETTE['texto_claro'])), legend=dict(orientation='v', yanchor='top', y=1, xanchor='left', x=1.02, title_text=DISPLAY_COLUMNS.get(dimension, dimension.capitalize()), font=dict(color=PALETTE['texto_claro']), title_font=dict(color=PALETTE['turquesa'])), legend_itemclick='toggle', legend_itemdoubleclick='toggleothers', paper_bgcolor=PALETTE['azul_amazonico'], plot_bgcolor=PALETTE['azul_amazonico'], font=dict(color=PALETTE['texto_claro']), xaxis=dict(gridcolor='rgba(227,226,218,0.18)', zerolinecolor='rgba(227,226,218,0.18)', tickfont=dict(color=PALETTE['texto_claro']), title=dict(font=dict(color=PALETTE['texto_claro']))), yaxis=dict(gridcolor='rgba(227,226,218,0.18)', zerolinecolor='rgba(227,226,218,0.18)', tickfont=dict(color=PALETTE['texto_claro']), title=dict(font=dict(color=PALETTE['texto_claro']))), updatemenus=[dict(type='buttons', direction='left', x=0.01, y=1.14, xanchor='left', yanchor='top', showactive=False, bgcolor=PALETTE['turquesa'], bordercolor=PALETTE['gris_ceramica'], font=dict(color=PALETTE['texto_oscuro']), buttons=[dict(label='Mostrar todo', method='update', args=[{'visible': [True] * total_traces}]), dict(label='Ocultar todo', method='update', args=[{'visible': ['legendonly'] * total_traces}])])])
        st.plotly_chart(fig, use_container_width=True)

    def render_summary_section(self, df: pd.DataFrame, dimension: str, metric: str, section_title: str, edt_df: pd.DataFrame | None = None) -> None:
        aggregated = self.aggregate_for_dimension(df, dimension, metric)
        top_label = aggregated.iloc[0][dimension] if not aggregated.empty else 'N/D'
        top_value = aggregated.iloc[0][metric] if not aggregated.empty else 0

        c1, c2, c3 = st.columns(3)
        with c1:
            build_metric_card('Total registros analizados', format_number(len(df), 0))
        with c2:
            build_metric_card(f'Total {DISPLAY_COLUMNS[metric].lower()}', format_number(df[metric].sum(), 2))
        with c3:
            build_metric_card(f'Máximo {section_title.lower()}', f'{top_label}<br><span style=\"font-size:1rem;color:#6B7280;\">{format_number(top_value, 2)}</span>')

        if dimension == 'departamento' and metric == 'cantidad':
            comparison_df = self.aggregate_department_cost_comparison(df, edt_df)
            c4, c5 = st.columns(2)

            with c4:
                build_metric_card('Estimado total RC (€)', format_number(comparison_df['estimado_rc'].sum(), 2))
            with c5:
                build_metric_card('Desviación total (€)', format_number(comparison_df['desviacion'].sum(), 2))

            no_incurrido, no_estimado = self.get_department_cost_comparison_status(comparison_df)

            st.markdown('')
            self.plot_department_cost_comparison(comparison_df, f'{section_title} - incurrido vs estimado RC')

            if no_incurrido:
                st.markdown('**Departamentos sin gasto incurrido en costes:**')
                st.markdown(', '.join(no_incurrido))
            else:
                st.markdown('**Departamentos sin gasto incurrido en costes:** ninguno')

            if no_estimado:
                st.markdown('**Departamentos sin gasto estimado en EDT:**')
                st.markdown(', '.join(no_estimado))
            else:
                st.markdown('**Departamentos sin gasto estimado en EDT:** ninguno')

            detail = comparison_df.rename(columns={'departamento': 'Departamento', 'incurrido': 'Incurrido (€)', 'estimado_rc': 'Estimado RC (€)', 'desviacion': 'Desviación (€)'})
            render_corporate_dataframe(detail, use_container_width=True, hide_index=True)
            return

        st.markdown('')
        self.plot_bar(aggregated, dimension, metric, f'{section_title} - ranking general')
        timeline = self.aggregate_timeline(df, dimension, metric)
        self.plot_timeline(timeline, dimension, metric, f'{section_title} - evolución mensual')
        detail = aggregated.rename(columns={dimension: DISPLAY_COLUMNS['departamento'] if dimension == 'departamento' else DISPLAY_COLUMNS['empleado'], 'horas_aplicadas': DISPLAY_COLUMNS['horas_aplicadas'], 'cantidad': DISPLAY_COLUMNS['cantidad'], 'empleados': 'Nº empleados', 'departamentos': 'Nº departamentos'})
        render_corporate_dataframe(detail, use_container_width=True, hide_index=True)

    def render_filtered_section(self, df: pd.DataFrame, filter_col: str, dimension_col: str, metric: str, title: str) -> None:
        options = ['Todos'] + sorted([v for v in df[filter_col].dropna().unique().tolist() if str(v).strip()])
        selected = st.selectbox(title, options=options, key=f'{title}_{metric}_{filter_col}')
        filtered_df = df if selected == 'Todos' else df[df[filter_col] == selected].copy()

        if filtered_df.empty:
            st.warning('No hay datos para la selección realizada.')
            return

        info1, info2, info3 = st.columns(3)
        with info1:
            build_metric_card('Selección', selected)
        with info2:
            build_metric_card(f'Total {DISPLAY_COLUMNS[metric].lower()}', format_number(filtered_df[metric].sum(), 2))
        with info3:
            build_metric_card('Registros', format_number(len(filtered_df), 0))

        aggregated = self.aggregate_for_dimension(filtered_df, dimension_col, metric)
        self.plot_bar(aggregated, dimension_col, metric, f'{title} - detalle')
        timeline = self.aggregate_timeline(filtered_df, dimension_col, metric)
        self.plot_timeline(timeline, dimension_col, metric, f'{title} - evolución mensual')
        detail_cols = ['periodo', 'departamento', 'empleado', 'categoria_nombre', 'horas_aplicadas', 'tasa', 'cantidad', 'tipo_coste_nombre']
        detail = filtered_df[detail_cols].copy()
        detail = detail.rename(columns={'periodo': 'Periodo', 'departamento': 'Departamento', 'empleado': 'Empleado', 'categoria_nombre': 'Categoría', 'horas_aplicadas': 'Horas Aplicadas', 'tasa': 'Tasa', 'cantidad': 'Cantidad', 'tipo_coste_nombre': 'Tipo de Coste'})
        detail = detail.sort_values(['Periodo', 'Departamento', 'Empleado'])
        render_corporate_dataframe(detail, use_container_width=True, hide_index=True)

    def render_global_filters(self, df: pd.DataFrame) -> pd.DataFrame:
        return df.copy()

    def render_tab_general(self, filtered: pd.DataFrame, project_summary: dict | None = None, project_summary_total: dict | None = None, project_summary_filtered: dict | None = None, compras_gpi_df: pd.DataFrame | None = None) -> None:
        st.subheader('Sección General · Evolución anual por departamento y empleado')

        def build_value_with_pct(selected_value: float, total_value: float, decimals: int = 2) -> str:
            pct = selected_value / total_value * 100 if total_value else 0
            return f'{format_number(selected_value, decimals)} / {format_number(total_value, decimals)}<br><span style="font-size:0.95rem;color:#E3E2DA;font-weight:600;">{format_number(pct, 1)}% del total</span>'

        general_departamentos = ['Todos'] + sorted([v for v in filtered['departamento'].dropna().unique().tolist() if str(v).strip()])
        general_empleados = ['Todos'] + sorted([v for v in filtered['empleado'].dropna().unique().tolist() if str(v).strip()])

        f1, f2 = st.columns(2)
        with f1:
            general_departamento_selected = st.selectbox('Departamento', options=general_departamentos, key='general_departamento_selected')
        with f2:
            general_empleado_selected = st.selectbox('Empleado', options=general_empleados, key='general_empleado_selected')

        if general_departamento_selected != 'Todos' and general_empleado_selected != 'Todos':
            general_filtered_view = filtered[(filtered['departamento'] == general_departamento_selected) & (filtered['empleado'] == general_empleado_selected)].copy()
        elif general_departamento_selected != 'Todos':
            general_filtered_view = filtered[filtered['departamento'] == general_departamento_selected].copy()
        elif general_empleado_selected != 'Todos':
            general_filtered_view = filtered[filtered['empleado'] == general_empleado_selected].copy()
        else:
            general_filtered_view = filtered.copy()

        project_summary_total = project_summary_total or project_summary or {}
        project_summary_filtered = project_summary_filtered or project_summary_total
        total_project_cost = float(project_summary_total.get('total_cost', filtered['cantidad'].sum()))
        total_project_hours = float(project_summary_total.get('total_hours', filtered['horas_aplicadas'].sum()))
        total_project_departments = int(project_summary_total.get('total_departments', filtered['departamento'].nunique()))
        total_project_employees = int(project_summary_total.get('total_employees', filtered['empleado'].nunique()))
        has_general_filter = general_departamento_selected != 'Todos' or general_empleado_selected != 'Todos'
        selected_cost = float(general_filtered_view['cantidad'].sum()) if has_general_filter else float(project_summary_filtered.get('total_cost', filtered['cantidad'].sum()))
        selected_hours = float(general_filtered_view['horas_aplicadas'].sum()) if has_general_filter else float(project_summary_filtered.get('total_hours', filtered['horas_aplicadas'].sum()))
        selected_departments = int(general_filtered_view['departamento'].nunique()) if has_general_filter else int(project_summary_filtered.get('total_departments', filtered['departamento'].nunique()))
        selected_employees = int(general_filtered_view['empleado'].nunique()) if has_general_filter else int(project_summary_filtered.get('total_employees', filtered['empleado'].nunique()))

        k1, k2, k3, k4 = st.columns(4)
        with k1:
            build_metric_card('Coste filtro / proyecto (€)', build_value_with_pct(selected_cost, total_project_cost, 2))
        with k2:
            build_metric_card('Horas filtro / proyecto', build_value_with_pct(selected_hours, total_project_hours, 2))
        with k3:
            build_metric_card('Departamentos filtro / proyecto', build_value_with_pct(selected_departments, total_project_departments, 0))
        with k4:
            build_metric_card('Empleados filtro / proyecto', build_value_with_pct(selected_employees, total_project_employees, 0))

        monthly_hours = self.aggregate_monthly_entity(filtered, 'horas_aplicadas', general_departamento_selected, general_empleado_selected)
        monthly_amount = self.aggregate_monthly_entity(filtered, 'cantidad', general_departamento_selected, general_empleado_selected)

        st.markdown('### Evolución anual en horas')
        self.plot_general_metric_evolution(monthly_hours, 'horas_aplicadas', 'Evolución mensual · Horas')
        st.markdown('### Evolución anual en cantidad (€)')
        self.plot_general_metric_evolution(monthly_amount, 'cantidad', 'Evolución mensual · Cantidad (€)')

        st.markdown('### Evolución mensual de compras GPI')
        if compras_gpi_df is None:
            st.info('No se está recibiendo el dataframe de Compras GPI en General. Revisa la llamada desde app_core.py.')
            return
        if compras_gpi_df.empty:
            st.info('Compras GPI está vacío después de aplicar los filtros globales.')
            return
        if 'periodo' not in compras_gpi_df.columns or 'cantidad' not in compras_gpi_df.columns:
            st.info('Compras GPI no contiene las columnas periodo y cantidad necesarias para pintar el gráfico.')
            return

        monthly_compras_gpi = compras_gpi_df.groupby('periodo', dropna=False, as_index=False).agg(cantidad=('cantidad', 'sum')).sort_values('periodo')
        self.plot_general_compras_gpi_monthly_amount(monthly_compras_gpi, 'Evolución mensual · Compras GPI (€)', 'general_compras_gpi_evolucion_mensual')

    def render_tab_departamento_horas(self, filtered: pd.DataFrame) -> None:
        st.subheader('Sección 1 · Horas por Elemento / Departamento')
        self.render_summary_section(filtered, 'departamento', 'horas_aplicadas', 'Coste operativo por departamento en horas')
        st.markdown('### Desplegable por departamento')
        self.render_filtered_section(filtered, 'departamento', 'empleado', 'horas_aplicadas', 'Filtro por departamento')

    def render_tab_empleado_horas(self, filtered: pd.DataFrame) -> None:
        st.subheader('Sección 2 · Horas por Empleado / Nombre')
        self.render_summary_section(filtered, 'empleado', 'horas_aplicadas', 'Coste operativo por empleado en horas')
        st.markdown('### Desplegable por empleado')
        self.render_filtered_section(filtered, 'empleado', 'departamento', 'horas_aplicadas', 'Filtro por empleado')

    def render_tab_departamento_cantidad(self, filtered: pd.DataFrame, edt_df: pd.DataFrame | None) -> None:
        st.subheader('Sección 3 · Cantidad por Elemento / Departamento')
        self.render_summary_section(filtered, 'departamento', 'cantidad', 'Coste económico por departamento', edt_df=edt_df)
        st.markdown('### Desplegable por departamento')
        self.render_filtered_section(filtered, 'departamento', 'empleado', 'cantidad', 'Filtro por departamento')

    def render_tab_empleado_cantidad(self, filtered: pd.DataFrame) -> None:
        st.subheader('Sección 4 · Cantidad por Empleado / Nombre')
        self.render_summary_section(filtered, 'empleado', 'cantidad', 'Coste económico por empleado')
        st.markdown('### Desplegable por empleado')
        self.render_filtered_section(filtered, 'empleado', 'departamento', 'cantidad', 'Filtro por empleado')