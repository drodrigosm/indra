# Este fichero contiene la carga, normalización, métricas, gráficos y render de la pestaña Compras NO GPI para analizar compras externas del proyecto.
from pathlib import Path
import html
import pandas as pd
import plotly.express as px
import streamlit as st
from data_common import try_convert_xls_to_xlsx
from ui_common import PALETTE, PLOTLY_COLOR_SEQUENCE, build_metric_card, format_number


class ComprasNoGpiModule:
    RAW_COLUMNS = ['unidad_empresa_codigo', 'unidad_empresa_nombre', 'proyecto_codigo', 'proyecto_nombre', 'estado', 'elemento_codigo', 'elemento_nombre', 'componente_coste_codigo', 'componente_coste_nombre', 'proveedor_codigo', 'proveedor_nombre', 'orden_grafo', 'orden_compra_numero', 'orden_compra_linea', 'articulo_codigo', 'articulo_nombre', 'clase_doc_compras_codigo', 'clase_doc_compras_nombre', 'fecha', 'factura', 'f_proveedor', 'importe', 'nota_cargo', 'integracion_sucursal']

    def load_dataframe(self, file_path: Path) -> pd.DataFrame:
        if 'ISPR_25C' not in file_path.name.upper():
            raise RuntimeError('El fichero de Compras NO GPI no es válido. El nombre del fichero debe incluir obligatoriamente el texto "ISPR_25C".')

        source_path = try_convert_xls_to_xlsx(file_path)
        df_raw = pd.read_excel(source_path, sheet_name='Hoja1', header=None)
        if df_raw.shape[1] < len(self.RAW_COLUMNS):
            raise RuntimeError(f'El Excel de Compras NO GPI no tiene las columnas esperadas. Columnas detectadas: {df_raw.shape[1]}')

        df = df_raw.iloc[3:, :len(self.RAW_COLUMNS)].copy()
        df.columns = self.RAW_COLUMNS
        df = df.dropna(how='all')
        text_cols = ['unidad_empresa_codigo', 'unidad_empresa_nombre', 'proyecto_codigo', 'proyecto_nombre', 'estado', 'elemento_codigo', 'elemento_nombre', 'componente_coste_codigo', 'componente_coste_nombre', 'proveedor_codigo', 'proveedor_nombre', 'orden_grafo', 'orden_compra_numero', 'orden_compra_linea', 'articulo_codigo', 'articulo_nombre', 'clase_doc_compras_codigo', 'clase_doc_compras_nombre', 'fecha', 'factura', 'f_proveedor', 'nota_cargo', 'integracion_sucursal']

        for col in text_cols:
            df[col] = df[col].astype('string').fillna('').str.strip()

        df['articulo_nombre'] = df['articulo_nombre'].apply(lambda v: html.unescape(v) if v else v)
        df['importe'] = pd.to_numeric(df['importe'], errors='coerce').fillna(0)
        df['cantidad'] = df['importe']
        df['departamento'] = (df['elemento_codigo'].fillna('') + ' - ' + df['elemento_nombre'].fillna('')).str.strip(' -')
        df['categoria'] = (df['componente_coste_codigo'].fillna('') + ' - ' + df['componente_coste_nombre'].fillna('')).str.strip(' -')
        df['proveedor'] = (df['proveedor_codigo'].fillna('') + ' - ' + df['proveedor_nombre'].fillna('')).str.strip(' -')
        df['articulo'] = (df['articulo_codigo'].fillna('') + ' - ' + df['articulo_nombre'].fillna('')).str.strip(' -')
        df['clase_documento'] = (df['clase_doc_compras_codigo'].fillna('') + ' - ' + df['clase_doc_compras_nombre'].fillna('')).str.strip(' -')
        df['fecha_dt'] = pd.to_datetime(df['fecha'], format='%m/%Y', errors='coerce')
        df['periodo'] = df['fecha_dt'].dt.strftime('%Y-%m').fillna('Sin periodo')
        df = df[(df['proveedor'] != '') & (df['departamento'] != '')].copy()
        return df

    def aggregate_dimension(self, df: pd.DataFrame, dimension: str) -> pd.DataFrame:
        grouped = df.groupby(dimension, dropna=False, as_index=False).agg(cantidad=('cantidad', 'sum'), operaciones=('cantidad', 'size'), ticket_medio=('cantidad', 'mean'), departamentos=('departamento', 'nunique'), proveedores=('proveedor', 'nunique'))
        return grouped.sort_values('cantidad', ascending=False)

    def aggregate_timeline(self, df: pd.DataFrame, dimension: str, top_n: int = 8) -> pd.DataFrame:
        top_values = self.aggregate_dimension(df, dimension).head(top_n)[dimension].tolist()
        timeline = df[df[dimension].isin(top_values)].groupby(['periodo', dimension], dropna=False, as_index=False).agg(cantidad=('cantidad', 'sum')).sort_values(['periodo', 'cantidad'], ascending=[True, False])
        return timeline

    def get_supplier_concentration(self, df: pd.DataFrame) -> tuple[float, float, float]:
        supplier_totals = self.aggregate_dimension(df, 'proveedor')
        total = float(supplier_totals['cantidad'].sum())
        if total <= 0:
            return 0.0, 0.0, 0.0
        top_1 = float(supplier_totals.head(1)['cantidad'].sum()) / total * 100
        top_3 = float(supplier_totals.head(3)['cantidad'].sum()) / total * 100
        top_5 = float(supplier_totals.head(5)['cantidad'].sum()) / total * 100
        return top_1, top_3, top_5

    def plot_monthly_amount(self, df_plot: pd.DataFrame, title: str) -> None:
        plot_df = df_plot.copy()
        plot_df['label_valor'] = plot_df['cantidad'].apply(lambda v: format_number(v, 0))
        fig = px.bar(plot_df, x='periodo', y='cantidad', title=title, text='label_valor')
        fig.update_traces(marker_color=PALETTE['turquesa'], textposition='outside', textfont=dict(color=PALETTE['texto_claro'], size=12), cliponaxis=False, hovertemplate='%{x}<br>%{y:,.2f} €<extra></extra>')
        fig.update_layout(height=520, xaxis_title='Periodo', yaxis_title='Importe (€)', margin=dict(l=10, r=10, t=60, b=10), paper_bgcolor=PALETTE['azul_amazonico'], plot_bgcolor=PALETTE['azul_amazonico'], font=dict(color=PALETTE['texto_claro']), title_font=dict(color=PALETTE['texto_claro']), xaxis=dict(type='category', gridcolor='rgba(227,226,218,0.18)', zerolinecolor='rgba(227,226,218,0.18)'), yaxis=dict(gridcolor='rgba(227,226,218,0.18)', zerolinecolor='rgba(227,226,218,0.18)'), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    def plot_bar(self, df_plot: pd.DataFrame, dimension: str, title: str) -> None:
        plot_df = df_plot.copy()
        fig = px.bar(plot_df, x='cantidad', y=dimension, orientation='h', text_auto='.2s', title=title, color=dimension, color_discrete_sequence=PLOTLY_COLOR_SEQUENCE)
        fig.update_traces(hovertemplate='%{y}<br>%{x:,.2f} €<extra></extra>', marker_line_color=PALETTE['gris_ceramica'], marker_line_width=0.5)
        fig.update_layout(height=max(600, 34 * len(plot_df) + 180), yaxis_title='', xaxis_title='Importe (€)', margin=dict(l=10, r=10, t=60, b=10), paper_bgcolor=PALETTE['azul_amazonico'], plot_bgcolor=PALETTE['azul_amazonico'], font=dict(color=PALETTE['texto_claro']), title_font=dict(color=PALETTE['texto_claro']), xaxis=dict(gridcolor='rgba(227,226,218,0.18)', zerolinecolor='rgba(227,226,218,0.18)'), yaxis=dict(gridcolor='rgba(227,226,218,0.10)'), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    def plot_supplier_pareto(self, df_plot: pd.DataFrame) -> None:
        plot_df = df_plot.copy().sort_values('cantidad', ascending=False)
        total = float(plot_df['cantidad'].sum())
        plot_df['porcentaje_acumulado'] = plot_df['cantidad'].cumsum() / total * 100 if total > 0 else 0
        plot_df['proveedor_corto'] = plot_df['proveedor'].astype(str).str.slice(0, 50)
        fig = px.line(plot_df, x='proveedor_corto', y='porcentaje_acumulado', markers=True, title='Curva acumulada de gasto por proveedor')
        fig.update_traces(line_color=PALETTE['turquesa'], marker_color=PALETTE['turquesa'], hovertemplate='%{x}<br>% acumulado: %{y:.1f}%<extra></extra>')
        fig.update_layout(height=520, xaxis_title='Proveedor', yaxis_title='% acumulado', margin=dict(l=10, r=10, t=60, b=120), paper_bgcolor=PALETTE['azul_amazonico'], plot_bgcolor=PALETTE['azul_amazonico'], font=dict(color=PALETTE['texto_claro']), title_font=dict(color=PALETTE['texto_claro']), xaxis=dict(tickangle=-35, gridcolor='rgba(227,226,218,0.18)', zerolinecolor='rgba(227,226,218,0.18)'), yaxis=dict(range=[0, 105], gridcolor='rgba(227,226,218,0.18)', zerolinecolor='rgba(227,226,218,0.18)'))
        st.plotly_chart(fig, use_container_width=True)

    def plot_timeline(self, df_plot: pd.DataFrame, dimension: str, title: str) -> None:
        fig = px.line(df_plot, x='periodo', y='cantidad', color=dimension, markers=True, title=title, color_discrete_sequence=PLOTLY_COLOR_SEQUENCE)
        total_traces = len(fig.data)
        for idx, trace in enumerate(fig.data):
            trace.line.width = 2
            trace.marker.size = 6
            trace.line.color = PLOTLY_COLOR_SEQUENCE[idx % len(PLOTLY_COLOR_SEQUENCE)]
            trace.marker.color = PLOTLY_COLOR_SEQUENCE[idx % len(PLOTLY_COLOR_SEQUENCE)]
        fig.update_layout(height=560, xaxis_title='Periodo', yaxis_title='Importe (€)', margin=dict(l=10, r=260, t=110, b=10), title=dict(x=0.01, xanchor='left', y=0.98, yanchor='top', font=dict(color=PALETTE['texto_claro'])), legend=dict(orientation='v', yanchor='top', y=1, xanchor='left', x=1.02, title_text=dimension.capitalize(), font=dict(color=PALETTE['texto_claro']), title_font=dict(color=PALETTE['turquesa'])), legend_itemclick='toggle', legend_itemdoubleclick='toggleothers', paper_bgcolor=PALETTE['azul_amazonico'], plot_bgcolor=PALETTE['azul_amazonico'], font=dict(color=PALETTE['texto_claro']), xaxis=dict(gridcolor='rgba(227,226,218,0.18)', zerolinecolor='rgba(227,226,218,0.18)'), yaxis=dict(gridcolor='rgba(227,226,218,0.18)', zerolinecolor='rgba(227,226,218,0.18)'), updatemenus=[dict(type='buttons', direction='left', x=0.01, y=1.14, xanchor='left', yanchor='top', showactive=False, bgcolor=PALETTE['turquesa'], bordercolor=PALETTE['gris_ceramica'], font=dict(color=PALETTE['texto_oscuro']), buttons=[dict(label='Mostrar todo', method='update', args=[{'visible': [True] * total_traces}]), dict(label='Ocultar todo', method='update', args=[{'visible': ['legendonly'] * total_traces}])])])
        st.plotly_chart(fig, use_container_width=True)

    def plot_amount_distribution(self, df: pd.DataFrame, chart_key: str) -> None:
        plot_df = df.copy()
        plot_df = plot_df[plot_df['cantidad'] > 0].copy()

        if plot_df.empty:
            st.info('No hay importes positivos para calcular la distribución estratégica de compras.')
            return

        supplier_df = self.aggregate_dimension(plot_df, 'proveedor').copy()
        supplier_df = supplier_df.sort_values('cantidad', ascending=False).reset_index(drop=True)

        total_gasto = float(supplier_df['cantidad'].sum())
        total_proveedores = int(len(supplier_df))

        supplier_df['proveedor_index'] = supplier_df.index + 1
        supplier_df['porcentaje_gasto_acumulado'] = supplier_df['cantidad'].cumsum() / total_gasto * 100 if total_gasto else 0
        supplier_df['porcentaje_proveedores_acumulado'] = supplier_df['proveedor_index'] / total_proveedores * 100 if total_proveedores else 0

        strategic_cut = supplier_df[supplier_df['porcentaje_gasto_acumulado'] <= 80]
        strategic_supplier_count = int(len(strategic_cut))
        if strategic_supplier_count == 0:
            strategic_supplier_count = 1

        strategic_supplier_pct = strategic_supplier_count / total_proveedores * 100 if total_proveedores else 0
        indirect_supplier_pct = 100 - strategic_supplier_pct

        fig = px.line(supplier_df, x='porcentaje_proveedores_acumulado', y='porcentaje_gasto_acumulado', markers=True, title='Distribución estratégica del gasto por proveedores')
        fig.update_traces(line_color=PALETTE['turquesa'], marker_color=PALETTE['turquesa'], line_width=5, marker_size=7, hovertemplate='Proveedores acumulados: %{x:.1f}%<br>Gasto acumulado: %{y:.1f}%<extra></extra>')

        fig.add_vrect(x0=0, x1=strategic_supplier_pct, fillcolor=PALETTE['turquesa'], opacity=0.12, line_width=0)
        fig.add_vrect(x0=strategic_supplier_pct, x1=100, fillcolor='#7BCFD4', opacity=0.07, line_width=0)
        fig.add_shape(type='line', x0=strategic_supplier_pct, y0=0, x1=strategic_supplier_pct, y1=100, line=dict(color=PALETTE['gris_ceramica'], width=2, dash='dot'))
        fig.add_shape(type='line', x0=0, y0=80, x1=strategic_supplier_pct, y1=80, line=dict(color=PALETTE['gris_ceramica'], width=1, dash='dot'))

        fig.add_annotation(x=max(strategic_supplier_pct / 2, 8), y=92, text=f"<b>Compras estratégicas</b><br><span style='font-size:30px'>80%</span> de gasto<br>{format_number(strategic_supplier_pct, 1)}% de proveedores", showarrow=False, align='left', font=dict(color=PALETTE['texto_claro'], size=16))
        fig.add_annotation(x=strategic_supplier_pct + ((100 - strategic_supplier_pct) / 2), y=92, text=f"<b>Compras indirectas</b><br><span style='font-size:30px'>20%</span> de gasto<br>{format_number(indirect_supplier_pct, 1)}% de proveedores", showarrow=False, align='left', font=dict(color=PALETTE['texto_claro'], size=16))

        fig.update_layout(height=560, xaxis_title='Número de proveedores acumulado (%)', yaxis_title='Volumen de gasto acumulado (%)', margin=dict(l=10, r=10, t=80, b=10), paper_bgcolor=PALETTE['azul_amazonico'], plot_bgcolor=PALETTE['azul_amazonico'], font=dict(color=PALETTE['texto_claro']), title_font=dict(color=PALETTE['texto_claro']), xaxis=dict(range=[0, 100], gridcolor='rgba(227,226,218,0.18)', zerolinecolor='rgba(227,226,218,0.18)', tickfont=dict(color=PALETTE['texto_claro']), title=dict(font=dict(color=PALETTE['texto_claro']))), yaxis=dict(range=[0, 105], gridcolor='rgba(227,226,218,0.18)', zerolinecolor='rgba(227,226,218,0.18)', tickfont=dict(color=PALETTE['texto_claro']), title=dict(font=dict(color=PALETTE['texto_claro']))), showlegend=False)

        st.plotly_chart(fig, use_container_width=True, key=chart_key)

    def render_tab(self, df: pd.DataFrame | None, coste_interno_total: float | None = None, estimado_total: float | None = None) -> None:
        st.subheader('Compras NO GPI · Compras externas del proyecto')
        if df is None or df.empty:
            st.info('Carga el fichero de Compras NO GPI para visualizar esta pestaña.')
            return

        periodos = ['Todos'] + sorted([p for p in df['periodo'].dropna().unique().tolist() if str(p).strip()])
        proveedores = ['Todos'] + sorted([p for p in df['proveedor'].dropna().unique().tolist() if str(p).strip()])
        categorias = ['Todos'] + sorted([c for c in df['categoria'].dropna().unique().tolist() if str(c).strip()])
        departamentos = ['Todos'] + sorted([d for d in df['departamento'].dropna().unique().tolist() if str(d).strip()])

        f1, f2, f3, f4 = st.columns(4)
        with f1:
            periodo_selected = st.selectbox('Periodo Compras NO GPI', options=periodos, key='compras_no_gpi_periodo')
        with f2:
            proveedor_selected = st.selectbox('Proveedor', options=proveedores, key='compras_no_gpi_proveedor')
        with f3:
            categoria_selected = st.selectbox('Categoría', options=categorias, key='compras_no_gpi_categoria')
        with f4:
            departamento_selected = st.selectbox('Elemento / Departamento', options=departamentos, key='compras_no_gpi_departamento')

        filtered = df.copy()
        if periodo_selected != 'Todos':
            filtered = filtered[filtered['periodo'] == periodo_selected]
        if proveedor_selected != 'Todos':
            filtered = filtered[filtered['proveedor'] == proveedor_selected]
        if categoria_selected != 'Todos':
            filtered = filtered[filtered['categoria'] == categoria_selected]
        if departamento_selected != 'Todos':
            filtered = filtered[filtered['departamento'] == departamento_selected]

        if filtered.empty:
            st.warning('No hay datos de Compras NO GPI para la selección realizada.')
            return

        total_importe = float(filtered['cantidad'].sum())
        total_operaciones = int(len(filtered))
        total_proveedores = int(filtered['proveedor'].nunique())
        ticket_medio = total_importe / total_operaciones if total_operaciones else 0.0
        top_1_pct, top_3_pct, top_5_pct = self.get_supplier_concentration(filtered)

        k1, k2, k3, k4, k5 = st.columns(5)
        with k1:
            build_metric_card('Importe total compras (€)', format_number(total_importe, 2))
        with k2:
            build_metric_card('Nº compras', format_number(total_operaciones, 0))
        with k3:
            build_metric_card('Proveedores', format_number(total_proveedores, 0))
        with k4:
            build_metric_card('Ticket medio (€)', format_number(ticket_medio, 2))
        with k5:
            build_metric_card('Concentración Top 3', f'{format_number(top_3_pct, 1)}%')

        if coste_interno_total is not None:
            total_proyecto = float(coste_interno_total) + total_importe
            pct_interno = float(coste_interno_total) / total_proyecto * 100 if total_proyecto else 0
            pct_compras = total_importe / total_proyecto * 100 if total_proyecto else 0
            v1, v2, v3 = st.columns(3)
            with v1:
                build_metric_card('Coste total proyecto (€)', format_number(total_proyecto, 2))
            with v2:
                build_metric_card('% coste interno', f'{format_number(pct_interno, 1)}%')
            with v3:
                build_metric_card('% compras NO GPI', f'{format_number(pct_compras, 1)}%')

        if estimado_total is not None:
            desviacion_global = (float(coste_interno_total or 0) + total_importe) - float(estimado_total)
            build_metric_card('Desviación global vs EDT (€)', format_number(desviacion_global, 2))

        monthly_amount = filtered.groupby('periodo', dropna=False, as_index=False).agg(cantidad=('cantidad', 'sum')).sort_values('periodo')
        ranking_proveedores = self.aggregate_dimension(filtered, 'proveedor').head(15)
        ranking_departamentos = self.aggregate_dimension(filtered, 'departamento').head(15)
        ranking_categorias = self.aggregate_dimension(filtered, 'categoria').head(15)
        timeline_proveedores = self.aggregate_timeline(filtered, 'proveedor', top_n=8)

        st.markdown('### Evolución mensual de compras NO GPI')
        self.plot_monthly_amount(monthly_amount, 'Evolución mensual · Compras NO GPI (€)')

        
        self.plot_supplier_pareto(ranking_proveedores)

        c1, c2, c3 = st.columns(3)
        with c1:
            build_metric_card('Concentración Top 1', f'{format_number(top_1_pct, 1)}%')
        with c2:
            build_metric_card('Concentración Top 3', f'{format_number(top_3_pct, 1)}%')
        with c3:
            build_metric_card('Concentración Top 5', f'{format_number(top_5_pct, 1)}%')

        st.markdown('### Gasto por categoría')
        self.plot_bar(ranking_categorias, 'categoria', 'Gasto por componente de coste / categoría')

        st.markdown('### Gasto por elemento / departamento')
        self.plot_bar(ranking_departamentos, 'departamento', 'Gasto por elemento / departamento')

        st.markdown('### Evolución mensual por proveedor')
        self.plot_timeline(timeline_proveedores, 'proveedor', 'Evolución mensual · Top proveedores')

        st.markdown('### Distribución de importes')
        self.plot_amount_distribution(filtered, chart_key='compras_no_gpi_pareto_proveedores_tab5')

        st.markdown('### Detalle de compras NO GPI')
        detail_cols = ['periodo', 'departamento', 'categoria', 'proveedor', 'clase_documento', 'orden_compra_numero', 'orden_compra_linea', 'articulo', 'factura', 'f_proveedor', 'cantidad']
        detail = filtered[detail_cols].copy()
        detail = detail.rename(columns={'periodo': 'Periodo', 'departamento': 'Elemento / Departamento', 'categoria': 'Categoría', 'proveedor': 'Proveedor', 'clase_documento': 'Clase documento compras', 'orden_compra_numero': 'Orden compra', 'orden_compra_linea': 'Línea', 'articulo': 'Artículo', 'factura': 'Factura', 'f_proveedor': 'Factura proveedor', 'cantidad': 'Importe (€)'})
        detail = detail.sort_values(['Periodo', 'Proveedor', 'Elemento / Departamento'])
        st.dataframe(detail, use_container_width=True, hide_index=True)