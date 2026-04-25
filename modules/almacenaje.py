# Este fichero contiene la carga multi-fichero, validación, normalización, métricas, gráficos y render de la pestaña Almacenaje.
from pathlib import Path
import html
import pandas as pd
import plotly.express as px
import streamlit as st
from data_common import try_convert_xls_to_xlsx
from ui_common import PALETTE, PLOTLY_COLOR_SEQUENCE, build_metric_card, format_number


class AlmacenajeModule:
    REQUIRED_NAME_TOKENS = ['ISPR_25', 'ALMACENAJE']

    COLUMN_ALIASES = {
        'unidad_empresa': ['unidad de empresa', 'unidad de empresa codigo', 'unidad empresa', 'unidad de empresA'.lower()],
        'proyecto': ['proyecto', 'proyecto codigo', 'codigo proyecto'],
        'estado': ['estado'],
        'elemento': ['elemento', 'elemento codigo'],
        'componente_coste': ['componente de coste', 'componente coste'],
        'fecha': ['fecha'],
        'importe': ['importe'],
        'descripcion': ['descripcion', 'descripción', 'material']
    }

    def validate_file_name(self, file_path: Path) -> None:
        file_name = file_path.name.upper()
        if 'ISPR_25S' not in file_name and 'ISPR_25U' not in file_name:
            raise RuntimeError('El fichero de Almacenaje no es válido. El nombre debe incluir obligatoriamente "ISPR_25S" o "ISPR_25U".')

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
            has_base = has_unidad and 'proyecto' in row_text and 'elemento' in row_text and 'componente de coste' in row_text and 'fecha' in row_text and 'importe' in row_text
            if has_base:
                return idx
        raise RuntimeError('No se ha encontrado la cabecera esperada en el fichero de Almacenaje. Deben existir Unidad de Empresa, Proyecto, Elemento, Componente de Coste, Fecha e Importe.')

    def build_code_name_value(self, df: pd.DataFrame, base_idx: int) -> pd.Series:
        code = df.iloc[:, base_idx].astype('string').fillna('').str.strip()
        name = df.iloc[:, base_idx + 1].astype('string').fillna('').str.strip() if base_idx + 1 < df.shape[1] else ''
        if isinstance(name, str):
            return code
        return (code + ' - ' + name).str.strip(' -')
    
    def map_columns(self, columns: list) -> dict:
        normalized_columns = {idx: self.normalize_column_name(col) for idx, col in enumerate(columns)}
        column_map = {}

        for idx, normalized_col in normalized_columns.items():
            if normalized_col in ['unidad de empresa', 'unidad empresa']:
                column_map['unidad_empresa'] = idx
            elif normalized_col == 'proyecto':
                column_map['proyecto'] = idx
            elif normalized_col == 'estado':
                column_map['estado'] = idx
            elif normalized_col == 'elemento':
                column_map['elemento'] = idx
            elif normalized_col == 'componente de coste':
                column_map['componente_coste'] = idx
            elif normalized_col == 'fecha':
                column_map['fecha'] = idx
            elif normalized_col == 'importe':
                column_map['importe'] = idx
            elif normalized_col == 'material':
                column_map['material'] = idx
            elif normalized_col in ['descripcion', 'descripción'] and 'descripcion' not in column_map:
                column_map['descripcion'] = idx

        required = ['unidad_empresa', 'proyecto', 'elemento', 'componente_coste', 'fecha', 'importe']
        missing = [col for col in required if col not in column_map]
        if missing:
            raise RuntimeError(f'El fichero de Almacenaje no contiene las columnas obligatorias: {", ".join(missing)}')

        return column_map

    def parse_period(self, series: pd.Series) -> pd.Series:
        parsed = pd.to_datetime(series.astype('string').str.strip(), format='%m/%Y', errors='coerce')
        if parsed.isna().all():
            parsed = pd.to_datetime(series.astype('string').str.strip(), errors='coerce')
        return parsed.dt.strftime('%Y-%m').fillna('Sin periodo')

    def load_single_dataframe(self, file_path: Path) -> pd.DataFrame:
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
        df['proyecto'] = self.build_code_name_value(df_data, column_map['proyecto'])
        df['estado'] = df_data.iloc[:, column_map['estado']].astype('string').fillna('').str.strip() if 'estado' in column_map else ''
        df['departamento'] = self.build_code_name_value(df_data, column_map['elemento'])
        df['categoria'] = self.build_code_name_value(df_data, column_map['componente_coste'])

        if 'material' in column_map:
            material_idx = column_map['material']
            material_name_idx = material_idx + 1 if material_idx + 1 < df_data.shape[1] else material_idx
            df['material'] = df_data.iloc[:, material_name_idx].astype('string').fillna('').str.strip()
        elif 'descripcion' in column_map:
            df['material'] = df_data.iloc[:, column_map['descripcion']].astype('string').fillna('').str.strip()
        else:
            df['material'] = df['departamento']

        df['fecha'] = df_data.iloc[:, column_map['fecha']].astype('string').fillna('').str.strip()
        df['importe'] = pd.to_numeric(df_data.iloc[:, column_map['importe']], errors='coerce').fillna(0)
        df['cantidad'] = df['importe']
        df['periodo'] = self.parse_period(df['fecha'])
        df['fichero_origen'] = file_path.name

        for col in ['unidad_empresa', 'proyecto', 'estado', 'departamento', 'categoria', 'material', 'fecha']:
            df[col] = df[col].astype('string').fillna('').str.strip().apply(lambda v: html.unescape(v) if v else v)

        df['estado'] = df['estado'].replace('', 'Sin estado')
        df = df[(df['departamento'] != '') & (df['categoria'] != '') & (df['cantidad'] != 0)].copy()
        return df

    def load_dataframes(self, file_paths: list[Path]) -> pd.DataFrame:
        if not file_paths:
            raise RuntimeError('No se ha recibido ningún fichero de Almacenaje.')
        frames = []
        reference_columns = None

        for file_path in file_paths:
            df = self.load_single_dataframe(file_path)
            current_columns = sorted([col for col in df.columns if col not in ['fichero_origen']])
            if reference_columns is None:
                reference_columns = current_columns
            elif current_columns != reference_columns:
                raise RuntimeError(f'El fichero "{file_path.name}" no es consistente con el resto de ficheros de Almacenaje.')
            frames.append(df)

        combined = pd.concat(frames, ignore_index=True)
        combined['duplicado_posible'] = combined.duplicated(subset=['periodo', 'unidad_empresa', 'proyecto', 'estado', 'departamento', 'categoria', 'material', 'cantidad'], keep=False)
        return combined

    def aggregate_dimension(self, df: pd.DataFrame, dimension: str) -> pd.DataFrame:
        grouped = df.groupby(dimension, dropna=False, as_index=False).agg(cantidad=('cantidad', 'sum'), registros=('cantidad', 'size'), coste_medio=('cantidad', 'mean'), periodos=('periodo', 'nunique'))
        return grouped.sort_values('cantidad', ascending=False)

    def aggregate_timeline(self, df: pd.DataFrame, dimension: str, top_n: int = 8) -> pd.DataFrame:
        top_values = self.aggregate_dimension(df, dimension).head(top_n)[dimension].tolist()
        timeline = df[df[dimension].isin(top_values)].groupby(['periodo', dimension], dropna=False, as_index=False).agg(cantidad=('cantidad', 'sum')).sort_values(['periodo', 'cantidad'], ascending=[True, False])
        return timeline

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
        for idx, trace in enumerate(fig.data):
            trace.line.width = 2
            trace.marker.size = 6
            trace.line.color = PLOTLY_COLOR_SEQUENCE[idx % len(PLOTLY_COLOR_SEQUENCE)]
            trace.marker.color = PLOTLY_COLOR_SEQUENCE[idx % len(PLOTLY_COLOR_SEQUENCE)]
        fig.update_layout(height=560, xaxis_title='Periodo', yaxis_title='Importe (€)', margin=dict(l=10, r=260, t=110, b=10), title=dict(x=0.01, xanchor='left', y=0.98, yanchor='top', font=dict(color=PALETTE['texto_claro'])), legend=dict(orientation='v', yanchor='top', y=1, xanchor='left', x=1.02, title_text=dimension.capitalize(), font=dict(color=PALETTE['texto_claro']), title_font=dict(color=PALETTE['turquesa'])), paper_bgcolor=PALETTE['azul_amazonico'], plot_bgcolor=PALETTE['azul_amazonico'], font=dict(color=PALETTE['texto_claro']), xaxis=dict(gridcolor='rgba(227,226,218,0.18)', zerolinecolor='rgba(227,226,218,0.18)'), yaxis=dict(gridcolor='rgba(227,226,218,0.18)', zerolinecolor='rgba(227,226,218,0.18)'))
        st.plotly_chart(fig, use_container_width=True, key=key)

    def render_tab(self, df: pd.DataFrame | None, coste_total_proyecto: float | None = None) -> None:
        st.subheader('Almacenaje · Costes logísticos del proyecto')
        if df is None or df.empty:
            st.info('Carga uno o varios ficheros de Almacenaje para visualizar esta pestaña.')
            return

        periodos = ['Todos'] + sorted([p for p in df['periodo'].dropna().unique().tolist() if str(p).strip()])
        estados = ['Todos'] + sorted([e for e in df['estado'].dropna().unique().tolist() if str(e).strip()])
        ficheros = ['Todos'] + sorted([f for f in df['fichero_origen'].dropna().unique().tolist() if str(f).strip()])
        categorias = ['Todos'] + sorted([c for c in df['categoria'].dropna().unique().tolist() if str(c).strip()])
        departamentos = ['Todos'] + sorted([d for d in df['departamento'].dropna().unique().tolist() if str(d).strip()])

        f1, f2, f3, f4, f5 = st.columns(5)
        with f1:
            periodo_selected = st.selectbox('Periodo Almacenaje', options=periodos, key='almacenaje_periodo')
        with f2:
            estado_selected = st.selectbox('Estado Almacenaje', options=estados, key='almacenaje_estado')
        with f3:
            fichero_selected = st.selectbox('Fichero origen', options=ficheros, key='almacenaje_fichero')
        with f4:
            categoria_selected = st.selectbox('Categoría almacenaje', options=categorias, key='almacenaje_categoria')
        with f5:
            departamento_selected = st.selectbox('Elemento / Departamento almacenaje', options=departamentos, key='almacenaje_departamento')

        filtered = df.copy()
        if periodo_selected != 'Todos':
            filtered = filtered[filtered['periodo'] == periodo_selected]
        if estado_selected != 'Todos':
            filtered = filtered[filtered['estado'] == estado_selected]
        if fichero_selected != 'Todos':
            filtered = filtered[filtered['fichero_origen'] == fichero_selected]
        if categoria_selected != 'Todos':
            filtered = filtered[filtered['categoria'] == categoria_selected]
        if departamento_selected != 'Todos':
            filtered = filtered[filtered['departamento'] == departamento_selected]

        if filtered.empty:
            st.warning('No hay datos de Almacenaje para la selección realizada.')
            return

        total_importe = float(filtered['cantidad'].sum())
        total_registros = int(len(filtered))
        total_periodos = int(filtered['periodo'].nunique())
        coste_medio_mensual = total_importe / total_periodos if total_periodos else 0.0
        duplicados = int(filtered['duplicado_posible'].sum()) if 'duplicado_posible' in filtered.columns else 0

        k1, k2, k3, k4, k5 = st.columns(5)
        with k1:
            build_metric_card('Coste total almacenaje (€)', format_number(total_importe, 2))
        with k2:
            build_metric_card('Coste medio mensual (€)', format_number(coste_medio_mensual, 2))
        with k3:
            build_metric_card('Registros', format_number(total_registros, 0))
        with k4:
            build_metric_card('Periodos', format_number(total_periodos, 0))
        with k5:
            build_metric_card('Posibles duplicados', format_number(duplicados, 0))

        if coste_total_proyecto is not None and coste_total_proyecto > 0:
            pct_almacenaje = total_importe / coste_total_proyecto * 100
            build_metric_card('% almacenaje sobre coste proyecto', f'{format_number(pct_almacenaje, 2)}%')

        monthly = filtered.groupby('periodo', dropna=False, as_index=False).agg(cantidad=('cantidad', 'sum')).sort_values('periodo')
        ranking_categoria = self.aggregate_dimension(filtered, 'categoria').head(15)
        ranking_departamento = self.aggregate_dimension(filtered, 'departamento').head(15)
        ranking_material = self.aggregate_dimension(filtered, 'material').head(15)
        timeline_categoria = self.aggregate_timeline(filtered, 'categoria', top_n=8)

        st.markdown('### Evolución mensual del coste de almacenaje')
        self.plot_monthly_amount(monthly, 'Evolución mensual · Almacenaje (€)', 'almacenaje_evolucion_mensual')

        st.markdown('### Coste por componente de coste')
        self.plot_bar(ranking_categoria, 'categoria', 'Ranking por componente de coste', 'almacenaje_ranking_categoria')

        st.markdown('### Coste por elemento')
        self.plot_bar(ranking_departamento, 'departamento', 'Ranking por elemento', 'almacenaje_ranking_departamento')

        st.markdown('### Coste por descripción / material')
        self.plot_bar(ranking_material, 'material', 'Ranking por descripción / material', 'almacenaje_ranking_material')

        st.markdown('### Evolución mensual por componente de coste')
        self.plot_timeline(timeline_categoria, 'categoria', 'Evolución mensual · Top componentes de coste', 'almacenaje_timeline_categoria')

        st.markdown('### Detalle de almacenaje')
        detail_cols = ['periodo', 'unidad_empresa', 'proyecto', 'estado', 'departamento', 'categoria', 'material', 'cantidad', 'fichero_origen', 'duplicado_posible']
        detail = filtered[detail_cols].copy()
        detail = detail.rename(columns={'periodo': 'Periodo', 'unidad_empresa': 'Unidad de Empresa', 'proyecto': 'Proyecto', 'estado': 'Estado', 'departamento': 'Elemento', 'categoria': 'Componente de Coste', 'material': 'Descripción / Material', 'cantidad': 'Importe (€)', 'fichero_origen': 'Fichero origen', 'duplicado_posible': 'Posible duplicado'})
        detail = detail.sort_values(['Periodo', 'Elemento', 'Componente de Coste'])
        st.dataframe(detail, use_container_width=True, hide_index=True)