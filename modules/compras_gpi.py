# Este fichero contiene la carga, normalización, métricas, gráficos y render de la pestaña Compras GPI para analizar materiales cargados en GPI.
from pathlib import Path
import html
import pandas as pd
import plotly.express as px
import streamlit as st
from data_common import try_convert_xls_to_xlsx
from ui_common import PALETTE, PLOTLY_COLOR_SEQUENCE, build_metric_card, format_number, render_corporate_dataframe


class ComprasGpiModule:
    REQUIRED_NAME_TOKENS = ['GPI', 'MAT']

    def validate_file_name(self, file_path: Path) -> None:
        file_name = file_path.name.upper()
        if 'ISPR25PX' not in file_name:
            raise RuntimeError('El fichero de Compras GPI no es válido. El nombre debe incluir obligatoriamente "ISPR25PX".')

    def normalize_column_name(self, value: str) -> str:
        value = html.unescape(str(value).strip()).lower()
        value = value.replace('\n', ' ').replace('\r', ' ')
        value = ' '.join(value.split())
        value = value.replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
        return value

    def find_header_row(self, df_raw: pd.DataFrame) -> int:
        for idx in range(min(100, len(df_raw))):
            row_values = [self.normalize_column_name(v) for v in df_raw.iloc[idx].tolist()]
            row_text = ' | '.join(row_values)
            has_unidad = 'unidad de empresa' in row_text or 'unidad empresa' in row_text
            has_descripcion = 'descripcion' in row_text or 'material' in row_text
            has_base = has_unidad and 'proyecto' in row_text and 'estado' in row_text and 'elemento' in row_text and 'componente de coste' in row_text and 'fecha' in row_text and 'importe' in row_text and has_descripcion
            if has_base:
                return idx
        raise RuntimeError('No se ha encontrado la cabecera esperada en el fichero Compras GPI. Deben existir Unidad de Empresa, Proyecto, Estado, Elemento, Componente de Coste, Fecha, Importe y Descripción o Material.')

    def map_columns(self, columns: list) -> dict:
        normalized_columns = {idx: self.normalize_column_name(col) for idx, col in enumerate(columns)}
        column_map = {}
        for idx, normalized_col in normalized_columns.items():
            if normalized_col in ['unidad de empresa', 'unidad empresa'] and 'unidad_empresa' not in column_map:
                column_map['unidad_empresa'] = idx
            elif normalized_col == 'linea de negocio' and 'linea_negocio' not in column_map:
                column_map['linea_negocio'] = idx
            elif normalized_col == 'proyecto' and 'proyecto' not in column_map:
                column_map['proyecto'] = idx
            elif normalized_col == 'estado' and 'estado' not in column_map:
                column_map['estado'] = idx
            elif normalized_col == 'elemento' and 'elemento' not in column_map:
                column_map['elemento'] = idx
            elif normalized_col == 'tipo reparto' and 'tipo_reparto' not in column_map:
                column_map['tipo_reparto'] = idx
            elif normalized_col == 'componente de coste' and 'componente_coste' not in column_map:
                column_map['componente_coste'] = idx
            elif normalized_col == 'material' and 'material' not in column_map:
                column_map['material'] = idx
            elif normalized_col == 'descripcion' and 'descripcion' not in column_map:
                column_map['descripcion'] = idx
            elif normalized_col == 'responsable' and 'responsable' not in column_map:
                column_map['responsable'] = idx
            elif normalized_col == 'origen' and 'origen' not in column_map:
                column_map['origen'] = idx
            elif normalized_col == 'fecha' and 'fecha' not in column_map:
                column_map['fecha'] = idx
            elif normalized_col == 'importe' and 'importe' not in column_map:
                column_map['importe'] = idx
        required = ['unidad_empresa', 'proyecto', 'estado', 'elemento', 'componente_coste', 'fecha', 'importe']
        missing = [col for col in required if col not in column_map]
        if missing:
            raise RuntimeError(f'El fichero de Compras GPI no contiene las columnas obligatorias: {", ".join(missing)}')
        if 'descripcion' not in column_map and 'material' not in column_map:
            raise RuntimeError('El fichero de Compras GPI debe contener la columna Descripción o Material.')
        return column_map

    def build_code_name_value(self, df: pd.DataFrame, base_idx: int) -> pd.Series:
        code = df.iloc[:, base_idx].astype('string').fillna('').str.strip()
        name = df.iloc[:, base_idx + 1].astype('string').fillna('').str.strip() if base_idx + 1 < df.shape[1] else ''
        if isinstance(name, str):
            return code
        return (code + ' - ' + name).str.strip(' -')

    def parse_importe(self, series: pd.Series) -> pd.Series:
        def normalize_amount(value):
            if pd.isna(value):
                return 0.0
            if isinstance(value, int) or isinstance(value, float):
                return float(value)
            text = str(value).strip().replace('€', '').replace(' ', '')
            if text == '':
                return 0.0
            if ',' in text and '.' in text:
                text = text.replace('.', '').replace(',', '.')
            elif ',' in text:
                text = text.replace(',', '.')
            return pd.to_numeric(text, errors='coerce')
        return series.apply(normalize_amount).fillna(0).astype(float)
    def parse_period(self, series: pd.Series) -> pd.Series:
        parsed = pd.to_datetime(series.astype('string').str.strip(), format='%m/%Y', errors='coerce')
        if parsed.isna().all():
            parsed = pd.to_datetime(series.astype('string').str.strip(), errors='coerce')
        return parsed.dt.strftime('%Y-%m').fillna('Sin periodo')

    def load_dataframe(self, file_path: Path) -> pd.DataFrame:
        self.validate_file_name(file_path)
        source_path = try_convert_xls_to_xlsx(file_path)
        df_raw = pd.read_excel(source_path, sheet_name='Hoja1', header=None)
        header_row_idx = self.find_header_row(df_raw)
        raw_headers = df_raw.iloc[header_row_idx].tolist()
        column_map = self.map_columns(raw_headers)
        df_data = df_raw.iloc[header_row_idx + 1:].copy()
        df_data = df_data.dropna(how='all')
        df = pd.DataFrame()
        df['unidad_empresa'] = self.build_code_name_value(df_data, column_map['unidad_empresa'])
        df['linea_negocio'] = self.build_code_name_value(df_data, column_map['linea_negocio']) if 'linea_negocio' in column_map else 'Sin línea de negocio'
        df['proyecto'] = self.build_code_name_value(df_data, column_map['proyecto'])
        df['estado'] = df_data.iloc[:, column_map['estado']].astype('string').fillna('').str.strip()
        df['departamento'] = self.build_code_name_value(df_data, column_map['elemento'])
        df['categoria'] = self.build_code_name_value(df_data, column_map['componente_coste'])
        df['tipo_reparto'] = self.build_code_name_value(df_data, column_map['tipo_reparto']) if 'tipo_reparto' in column_map else 'Sin tipo de reparto'
        if 'material' in column_map:
            material_idx = column_map['material']
            material_name_idx = material_idx + 1 if material_idx + 1 < df_data.shape[1] else material_idx
            df['material'] = df_data.iloc[:, material_name_idx].astype('string').fillna('').str.strip()
        else:
            df['material'] = df_data.iloc[:, column_map['descripcion']].astype('string').fillna('').str.strip()
        df['responsable'] = df_data.iloc[:, column_map['responsable']].astype('string').fillna('').str.strip() if 'responsable' in column_map else ''
        df['origen'] = df_data.iloc[:, column_map['origen']].astype('string').fillna('').str.strip() if 'origen' in column_map else ''
        df['fecha'] = df_data.iloc[:, column_map['fecha']].astype('string').fillna('').str.strip()
        df['importe'] = self.parse_importe(df_data.iloc[:, column_map['importe']])
        df['cantidad'] = df['importe']
        df['periodo'] = self.parse_period(df['fecha'])
        df['fichero_origen'] = file_path.name
        for col in ['unidad_empresa', 'linea_negocio', 'proyecto', 'estado', 'departamento', 'categoria', 'tipo_reparto', 'material', 'responsable', 'origen', 'fecha']:
            df[col] = df[col].astype('string').fillna('').str.strip().apply(lambda v: html.unescape(v) if v else v)
        df['estado'] = df['estado'].replace('', 'Sin estado')
        df['tipo_reparto'] = df['tipo_reparto'].replace('', 'Sin tipo de reparto')
        df['material'] = df['material'].replace('', 'Sin descripción')
        df = df[(df['proyecto'] != '') | (df['departamento'] != '') | (df['categoria'] != '') | (df['material'] != 'Sin descripción')].copy()
        df['duplicado_posible'] = df.duplicated(subset=['periodo', 'unidad_empresa', 'proyecto', 'estado', 'departamento', 'categoria', 'tipo_reparto', 'material', 'cantidad'], keep=False)
        return df

    def aggregate_dimension(self, df: pd.DataFrame, dimension: str) -> pd.DataFrame:
        grouped = df.groupby(dimension, dropna=False, as_index=False).agg(cantidad=('cantidad', 'sum'), registros=('cantidad', 'size'), ticket_medio=('cantidad', 'mean'), proyectos=('proyecto', 'nunique'), elementos=('departamento', 'nunique'))
        return grouped.sort_values('cantidad', ascending=False)

    def aggregate_timeline(self, df: pd.DataFrame, dimension: str, top_n: int = 8) -> pd.DataFrame:
        top_values = self.aggregate_dimension(df, dimension).head(top_n)[dimension].tolist()
        timeline = df[df[dimension].isin(top_values)].groupby(['periodo', dimension], dropna=False, as_index=False).agg(cantidad=('cantidad', 'sum')).sort_values(['periodo', 'cantidad'], ascending=[True, False])
        return timeline

    def get_top_concentration(self, df: pd.DataFrame, top_n: int) -> float:
        total = float(df['cantidad'].sum())
        if total <= 0:
            return 0.0
        top_amount = float(df.sort_values('cantidad', ascending=False).head(top_n)['cantidad'].sum())
        return top_amount / total * 100

    def plot_monthly_amount(self, df_plot: pd.DataFrame, title: str, key: str) -> None:
        plot_df = df_plot.copy()
        plot_df['label_valor'] = plot_df['cantidad'].apply(lambda v: format_number(v, 0))
        fig = px.bar(plot_df, x='periodo', y='cantidad', title=title, text='label_valor')
        fig.update_traces(marker_color=PALETTE['turquesa'], textposition='outside', textfont=dict(color=PALETTE['texto_claro'], size=12), cliponaxis=False, hovertemplate='%{x}<br>%{y:,.2f} €<extra></extra>')
        fig.update_layout(height=520, xaxis_title='Periodo', yaxis_title='Importe (€)', margin=dict(l=10, r=10, t=60, b=10), paper_bgcolor=PALETTE['azul_amazonico'], plot_bgcolor=PALETTE['azul_amazonico'], font=dict(color=PALETTE['texto_claro']), title_font=dict(color=PALETTE['texto_claro']), xaxis=dict(type='category', gridcolor='rgba(227,226,218,0.18)', zerolinecolor='rgba(227,226,218,0.18)'), yaxis=dict(gridcolor='rgba(227,226,218,0.18)', zerolinecolor='rgba(227,226,218,0.18)'), showlegend=False)
        st.plotly_chart(fig, use_container_width=True, key=key)

    def plot_bar(self, df_plot: pd.DataFrame, dimension: str, title: str, key: str) -> None:
        plot_df = df_plot.copy()
        fig = px.bar(plot_df, x='cantidad', y=dimension, orientation='h', text_auto='.2s', title=title, color=dimension, color_discrete_sequence=PLOTLY_COLOR_SEQUENCE)
        fig.update_traces(hovertemplate='%{y}<br>%{x:,.2f} €<extra></extra>', marker_line_color=PALETTE['gris_ceramica'], marker_line_width=0.5)
        fig.update_layout(height=max(600, 34 * len(plot_df) + 180), yaxis_title='', xaxis_title='Importe (€)', margin=dict(l=10, r=10, t=60, b=10), paper_bgcolor=PALETTE['azul_amazonico'], plot_bgcolor=PALETTE['azul_amazonico'], font=dict(color=PALETTE['texto_claro']), title_font=dict(color=PALETTE['texto_claro']), xaxis=dict(gridcolor='rgba(227,226,218,0.18)', zerolinecolor='rgba(227,226,218,0.18)'), yaxis=dict(gridcolor='rgba(227,226,218,0.10)'), showlegend=False)
        st.plotly_chart(fig, use_container_width=True, key=key)

    def plot_timeline(self, df_plot: pd.DataFrame, dimension: str, title: str, key: str) -> None:
        fig = px.line(df_plot, x='periodo', y='cantidad', color=dimension, markers=True, title=title, color_discrete_sequence=PLOTLY_COLOR_SEQUENCE)
        total_traces = len(fig.data)
        for idx, trace in enumerate(fig.data):
            trace.line.width = 2
            trace.marker.size = 6
            trace.line.color = PLOTLY_COLOR_SEQUENCE[idx % len(PLOTLY_COLOR_SEQUENCE)]
            trace.marker.color = PLOTLY_COLOR_SEQUENCE[idx % len(PLOTLY_COLOR_SEQUENCE)]
        fig.update_layout(height=560, xaxis_title='Periodo', yaxis_title='Importe (€)', margin=dict(l=10, r=260, t=110, b=10), title=dict(x=0.01, xanchor='left', y=0.98, yanchor='top', font=dict(color=PALETTE['texto_claro'])), legend=dict(orientation='v', yanchor='top', y=1, xanchor='left', x=1.02, title_text=dimension.capitalize(), font=dict(color=PALETTE['texto_claro']), title_font=dict(color=PALETTE['turquesa'])), legend_itemclick='toggle', legend_itemdoubleclick='toggleothers', paper_bgcolor=PALETTE['azul_amazonico'], plot_bgcolor=PALETTE['azul_amazonico'], font=dict(color=PALETTE['texto_claro']), xaxis=dict(gridcolor='rgba(227,226,218,0.18)', zerolinecolor='rgba(227,226,218,0.18)'), yaxis=dict(gridcolor='rgba(227,226,218,0.18)', zerolinecolor='rgba(227,226,218,0.18)'), updatemenus=[dict(type='buttons', direction='left', x=0.01, y=1.14, xanchor='left', yanchor='top', showactive=False, bgcolor=PALETTE['turquesa'], bordercolor=PALETTE['gris_ceramica'], font=dict(color=PALETTE['texto_oscuro']), buttons=[dict(label='Mostrar todo', method='update', args=[{'visible': [True] * total_traces}]), dict(label='Ocultar todo', method='update', args=[{'visible': ['legendonly'] * total_traces}])])])
        st.plotly_chart(fig, use_container_width=True, key=key)

    def render_tab(self, df: pd.DataFrame | None, coste_total_proyecto: float | None = None) -> None:
        st.subheader('Compras GPI · Materiales cargados en GPI')
        if df is None or df.empty:
            st.info('Carga el fichero de Compras GPI para visualizar esta pestaña.')
            return
        periodos = ['Todos'] + sorted([p for p in df['periodo'].dropna().unique().tolist() if str(p).strip()])
        estados = ['Todos'] + sorted([e for e in df['estado'].dropna().unique().tolist() if str(e).strip()])
        proyectos = ['Todos'] + sorted([p for p in df['proyecto'].dropna().unique().tolist() if str(p).strip()])
        categorias = ['Todos'] + sorted([c for c in df['categoria'].dropna().unique().tolist() if str(c).strip()])
        departamentos = ['Todos'] + sorted([d for d in df['departamento'].dropna().unique().tolist() if str(d).strip()])
        tipos_reparto = ['Todos'] + sorted([t for t in df['tipo_reparto'].dropna().unique().tolist() if str(t).strip()])
        f1, f2, f3 = st.columns(3)
        with f1:
            periodo_selected = st.selectbox('Periodo Compras GPI', options=periodos, key='compras_gpi_periodo')
        with f2:
            estado_selected = st.selectbox('Estado Compras GPI', options=estados, key='compras_gpi_estado')
        with f3:
            proyecto_selected = st.selectbox('Proyecto Compras GPI', options=proyectos, key='compras_gpi_proyecto')
        f4, f5, f6 = st.columns(3)
        with f4:
            categoria_selected = st.selectbox('Componente de coste GPI', options=categorias, key='compras_gpi_categoria')
        with f5:
            departamento_selected = st.selectbox('Elemento GPI', options=departamentos, key='compras_gpi_departamento')
        with f6:
            tipo_reparto_selected = st.selectbox('Tipo reparto GPI', options=tipos_reparto, key='compras_gpi_tipo_reparto')
        filtered = df.copy()
        if periodo_selected != 'Todos':
            filtered = filtered[filtered['periodo'] == periodo_selected]
        if estado_selected != 'Todos':
            filtered = filtered[filtered['estado'] == estado_selected]
        if proyecto_selected != 'Todos':
            filtered = filtered[filtered['proyecto'] == proyecto_selected]
        if categoria_selected != 'Todos':
            filtered = filtered[filtered['categoria'] == categoria_selected]
        if departamento_selected != 'Todos':
            filtered = filtered[filtered['departamento'] == departamento_selected]
        if tipo_reparto_selected != 'Todos':
            filtered = filtered[filtered['tipo_reparto'] == tipo_reparto_selected]
        if filtered.empty:
            st.warning('No hay datos de Compras GPI para la selección realizada.')
            return
        total_importe = float(filtered['cantidad'].sum())
        total_registros = int(len(filtered))
        total_proyectos = int(filtered['proyecto'].nunique())
        ticket_medio = total_importe / total_registros if total_registros else 0.0
        top10_pct = self.get_top_concentration(filtered, 10)
        duplicados = int(filtered['duplicado_posible'].sum()) if 'duplicado_posible' in filtered.columns else 0
        k1, k2, k3, k4, k5 = st.columns(5)
        with k1:
            build_metric_card('Total compras GPI (€)', format_number(total_importe, 2))
        with k2:
            build_metric_card('Registros', format_number(total_registros, 0))
        with k3:
            build_metric_card('Proyectos', format_number(total_proyectos, 0))
        with k4:
            build_metric_card('Ticket medio (€)', format_number(ticket_medio, 2))
        with k5:
            build_metric_card('Concentración Top 10', f'{format_number(top10_pct, 1)}%')
        if coste_total_proyecto is not None and coste_total_proyecto > 0:
            pct_gpi = total_importe / coste_total_proyecto * 100
            build_metric_card('% compras GPI sobre coste proyecto', f'{format_number(pct_gpi, 2)}%')
        monthly = filtered.groupby('periodo', dropna=False, as_index=False).agg(cantidad=('cantidad', 'sum')).sort_values('periodo')
        ranking_categoria = self.aggregate_dimension(filtered, 'categoria').head(15)
        ranking_departamento = self.aggregate_dimension(filtered, 'departamento').head(15)
        ranking_material = self.aggregate_dimension(filtered, 'material').head(15)
        timeline_categoria = self.aggregate_timeline(filtered, 'categoria', top_n=8)
        st.markdown('### Evolución mensual de compras GPI')
        self.plot_monthly_amount(monthly, 'Evolución mensual · Compras GPI (€)', 'compras_gpi_evolucion_mensual')
        st.markdown('### Gasto por componente de coste')
        self.plot_bar(ranking_categoria, 'categoria', 'Ranking por componente de coste', 'compras_gpi_ranking_categoria')
        st.markdown('### Gasto por elemento')
        self.plot_bar(ranking_departamento, 'departamento', 'Ranking por elemento', 'compras_gpi_ranking_departamento')
        st.markdown('### Gasto por descripción / material')
        self.plot_bar(ranking_material, 'material', 'Ranking por descripción / material', 'compras_gpi_ranking_material')
        st.markdown('### Evolución mensual por componente de coste')
        self.plot_timeline(timeline_categoria, 'categoria', 'Evolución mensual · Top componentes de coste GPI', 'compras_gpi_timeline_categoria')
        st.markdown('### Calidad de datos')
        sin_proyecto = int((filtered['proyecto'].fillna('').astype(str).str.strip() == '').sum())
        sin_elemento = int((filtered['departamento'].fillna('').astype(str).str.strip() == '').sum())
        sin_componente = int((filtered['categoria'].fillna('').astype(str).str.strip() == '').sum())
        importe_cero_negativo = int((filtered['cantidad'] <= 0).sum())
        q1, q2, q3, q4, q5 = st.columns(5)
        with q1:
            build_metric_card('Sin proyecto', format_number(sin_proyecto, 0))
        with q2:
            build_metric_card('Sin elemento', format_number(sin_elemento, 0))
        with q3:
            build_metric_card('Sin componente', format_number(sin_componente, 0))
        with q4:
            build_metric_card('Importe <= 0', format_number(importe_cero_negativo, 0))
        with q5:
            build_metric_card('Posibles duplicados', format_number(duplicados, 0))
        st.markdown('### Top compras individuales')
        top_cols = ['periodo', 'proyecto', 'departamento', 'categoria', 'tipo_reparto', 'material', 'responsable', 'origen', 'cantidad']
        top_detail = filtered.sort_values('cantidad', ascending=False).head(30)[top_cols].rename(columns={'periodo': 'Periodo', 'proyecto': 'Proyecto', 'departamento': 'Elemento', 'categoria': 'Componente de Coste', 'tipo_reparto': 'Tipo Reparto', 'material': 'Descripción / Material', 'responsable': 'Responsable', 'origen': 'Origen', 'cantidad': 'Importe (€)'})
        
        st.markdown('### Detalle de compras GPI')
        detail_cols = ['periodo', 'unidad_empresa', 'linea_negocio', 'proyecto', 'estado', 'departamento', 'categoria', 'tipo_reparto', 'material', 'responsable', 'origen', 'cantidad', 'fichero_origen', 'duplicado_posible']
        detail = filtered[detail_cols].copy()
        detail = detail.rename(columns={'periodo': 'Periodo', 'unidad_empresa': 'Unidad de Empresa', 'linea_negocio': 'Línea de Negocio', 'proyecto': 'Proyecto', 'estado': 'Estado', 'departamento': 'Elemento', 'categoria': 'Componente de Coste', 'tipo_reparto': 'Tipo Reparto', 'material': 'Descripción / Material', 'responsable': 'Responsable', 'origen': 'Origen', 'cantidad': 'Importe (€)', 'fichero_origen': 'Fichero origen', 'duplicado_posible': 'Posible duplicado'})
        detail = detail.sort_values(['Periodo', 'Proyecto', 'Elemento'])
        render_corporate_dataframe(top_detail, use_container_width=True, hide_index=True)
        render_corporate_dataframe(detail, use_container_width=True, hide_index=True)
