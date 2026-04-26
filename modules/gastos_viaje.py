# Este fichero contiene la carga multi-fichero, normalización, métricas, gráficos y render de la pestaña Gastos de Viaje.
from pathlib import Path
import html
import pandas as pd
import plotly.express as px
import streamlit as st
from data_common import try_convert_xls_to_xlsx
from ui_common import PALETTE, PLOTLY_COLOR_SEQUENCE, build_metric_card, format_number, render_corporate_dataframe


class GastosViajeModule:
    VALID_NAME_TOKENS = ['ISPR_25F', 'ISPR_25G']

    def validate_file_name(self, file_path: Path) -> None:
        file_name = file_path.name.upper()
        if 'ISPR_25F' not in file_name and 'ISPR_25G' not in file_name:
            raise RuntimeError('El fichero de Gastos de Viaje no es válido. El nombre debe incluir "ISPR_25F" o "ISPR_25G".')

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
            has_base = ('unidad de empresa' in row_text or 'unidad empresa' in row_text) and 'proyecto' in row_text and 'elemento' in row_text and 'fecha' in row_text and 'importe' in row_text
            if has_base:
                return idx
        raise RuntimeError('No se ha encontrado la cabecera esperada en el fichero de Gastos de Viaje. Deben existir Unidad de Empresa, Proyecto, Elemento, Fecha e Importe.')

    def map_columns(self, columns: list) -> dict:
        normalized_columns = {idx: self.normalize_column_name(col) for idx, col in enumerate(columns)}
        column_map = {}
        for idx, normalized_col in normalized_columns.items():
            if normalized_col in ['unidad de empresa', 'unidad empresa'] and 'unidad_empresa' not in column_map:
                column_map['unidad_empresa'] = idx
            elif normalized_col == 'proyecto' and 'proyecto' not in column_map:
                column_map['proyecto'] = idx
            elif normalized_col == 'estado' and 'estado' not in column_map:
                column_map['estado'] = idx
            elif normalized_col == 'elemento' and 'elemento' not in column_map:
                column_map['elemento'] = idx
            elif normalized_col in ['empleado', 'persona', 'recurso'] and 'empleado' not in column_map:
                column_map['empleado'] = idx
            elif normalized_col in ['componente de coste', 'componente coste', 'tipo gasto', 'tipo de gasto', 'concepto'] and 'categoria' not in column_map:
                column_map['categoria'] = idx
            elif normalized_col in ['descripcion', 'descripción', 'texto', 'motivo'] and 'descripcion' not in column_map:
                column_map['descripcion'] = idx
            elif normalized_col == 'fecha' and 'fecha' not in column_map:
                column_map['fecha'] = idx
            elif normalized_col == 'importe' and 'importe' not in column_map:
                column_map['importe'] = idx
        required = ['unidad_empresa', 'proyecto', 'elemento', 'fecha', 'importe']
        missing = [col for col in required if col not in column_map]
        if missing:
            raise RuntimeError(f'El fichero de Gastos de Viaje no contiene las columnas obligatorias: {", ".join(missing)}')
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

    def load_single_dataframe(self, file_path: Path) -> pd.DataFrame:
        self.validate_file_name(file_path)
        source_path = try_convert_xls_to_xlsx(file_path)
        df_raw = pd.read_excel(source_path, sheet_name='Hoja1', header=None)
        header_row_idx = self.find_header_row(df_raw)
        column_map = self.map_columns(df_raw.iloc[header_row_idx].tolist())
        df_data = df_raw.iloc[header_row_idx + 1:].copy()
        df_data = df_data.dropna(how='all')
        df = pd.DataFrame()
        df['unidad_empresa'] = self.build_code_name_value(df_data, column_map['unidad_empresa'])
        df['proyecto'] = self.build_code_name_value(df_data, column_map['proyecto'])
        df['estado'] = df_data.iloc[:, column_map['estado']].astype('string').fillna('').str.strip() if 'estado' in column_map else 'Sin estado'
        df['departamento'] = self.build_code_name_value(df_data, column_map['elemento'])
        df['empleado'] = self.build_code_name_value(df_data, column_map['empleado']) if 'empleado' in column_map else 'Sin empleado'
        df['categoria'] = self.build_code_name_value(df_data, column_map['categoria']) if 'categoria' in column_map else 'Sin categoría'
        df['descripcion'] = df_data.iloc[:, column_map['descripcion']].astype('string').fillna('').str.strip() if 'descripcion' in column_map else ''
        df['fecha'] = df_data.iloc[:, column_map['fecha']].astype('string').fillna('').str.strip()
        df['importe'] = self.parse_importe(df_data.iloc[:, column_map['importe']])
        df['cantidad'] = df['importe']
        df['periodo'] = self.parse_period(df['fecha'])
        df['fichero_origen'] = file_path.name
        for col in ['unidad_empresa', 'proyecto', 'estado', 'departamento', 'empleado', 'categoria', 'descripcion', 'fecha']:
            df[col] = df[col].astype('string').fillna('').str.strip().apply(lambda v: html.unescape(v) if v else v)
        df['estado'] = df['estado'].replace('', 'Sin estado')
        df['empleado'] = df['empleado'].replace('', 'Sin empleado')
        df['categoria'] = df['categoria'].replace('', 'Sin categoría')
        df = df[(df['departamento'] != '') & (df['cantidad'] != 0)].copy()
        return df

    def load_dataframes(self, file_paths: list[Path]) -> pd.DataFrame:
        if not file_paths:
            raise RuntimeError('No se ha recibido ningún fichero de Gastos de Viaje.')
        frames = [self.load_single_dataframe(file_path) for file_path in file_paths]
        combined = pd.concat(frames, ignore_index=True)
        combined['duplicado_posible'] = combined.duplicated(subset=['periodo', 'proyecto', 'departamento', 'empleado', 'categoria', 'descripcion', 'cantidad'], keep=False)
        return combined

    def aggregate_dimension(self, df: pd.DataFrame, dimension: str) -> pd.DataFrame:
        grouped = df.groupby(dimension, dropna=False, as_index=False).agg(cantidad=('cantidad', 'sum'), registros=('cantidad', 'size'), gasto_medio=('cantidad', 'mean'), periodos=('periodo', 'nunique'))
        return grouped.sort_values('cantidad', ascending=False)

    def get_concentration(self, df: pd.DataFrame, dimension: str, top_n: int) -> float:
        grouped = self.aggregate_dimension(df, dimension)
        total = float(grouped['cantidad'].sum())
        if total <= 0:
            return 0.0
        return float(grouped.head(top_n)['cantidad'].sum()) / total * 100

    def plot_monthly_amount(self, df_plot: pd.DataFrame, title: str, key: str) -> None:
        plot_df = df_plot.groupby('periodo', dropna=False, as_index=False).agg(cantidad=('cantidad', 'sum')).sort_values('periodo')
        plot_df['label_valor'] = plot_df['cantidad'].apply(lambda v: format_number(v, 0))
        fig = px.bar(plot_df, x='periodo', y='cantidad', title=title, text='label_valor')
        fig.update_traces(marker_color=PALETTE['turquesa'], textposition='outside', textfont=dict(color=PALETTE['texto_claro'], size=12), cliponaxis=False, hovertemplate='%{x}<br>%{y:,.2f} €<extra></extra>')
        fig.update_layout(height=520, xaxis_title='Periodo', yaxis_title='Importe (€)', margin=dict(l=10, r=10, t=60, b=10), paper_bgcolor=PALETTE['azul_amazonico'], plot_bgcolor=PALETTE['azul_amazonico'], font=dict(color=PALETTE['texto_claro']), title_font=dict(color=PALETTE['texto_claro']), xaxis=dict(type='category', gridcolor='rgba(227,226,218,0.18)'), yaxis=dict(gridcolor='rgba(227,226,218,0.18)'), showlegend=False)
        st.plotly_chart(fig, use_container_width=True, key=key)

    def plot_bar(self, df_plot: pd.DataFrame, dimension: str, title: str, key: str) -> None:
        plot_df = self.aggregate_dimension(df_plot, dimension).head(20)
        fig = px.bar(plot_df, x='cantidad', y=dimension, orientation='h', text_auto='.2s', title=title, color=dimension, color_discrete_sequence=PLOTLY_COLOR_SEQUENCE)
        fig.update_traces(hovertemplate='%{y}<br>%{x:,.2f} €<extra></extra>', marker_line_color=PALETTE['gris_ceramica'], marker_line_width=0.5)
        fig.update_layout(height=max(600, 34 * len(plot_df) + 180), yaxis_title='', xaxis_title='Importe (€)', margin=dict(l=10, r=10, t=60, b=10), paper_bgcolor=PALETTE['azul_amazonico'], plot_bgcolor=PALETTE['azul_amazonico'], font=dict(color=PALETTE['texto_claro']), title_font=dict(color=PALETTE['texto_claro']), xaxis=dict(gridcolor='rgba(227,226,218,0.18)'), yaxis=dict(gridcolor='rgba(227,226,218,0.10)'), showlegend=False)
        st.plotly_chart(fig, use_container_width=True, key=key)

    def plot_distribution(self, df_plot: pd.DataFrame, key: str) -> None:
        plot_df = df_plot[df_plot['cantidad'] != 0].copy()
        fig = px.histogram(plot_df, x='cantidad', nbins=30, title='Distribución de importes de gastos de viaje')
        fig.update_traces(marker_color=PALETTE['turquesa'], hovertemplate='Importe: %{x:,.2f} €<br>Registros: %{y}<extra></extra>')
        fig.update_layout(height=520, xaxis_title='Importe (€)', yaxis_title='Registros', margin=dict(l=10, r=10, t=60, b=10), paper_bgcolor=PALETTE['azul_amazonico'], plot_bgcolor=PALETTE['azul_amazonico'], font=dict(color=PALETTE['texto_claro']), title_font=dict(color=PALETTE['texto_claro']), xaxis=dict(gridcolor='rgba(227,226,218,0.18)'), yaxis=dict(gridcolor='rgba(227,226,218,0.18)'), showlegend=False)
        st.plotly_chart(fig, use_container_width=True, key=key)

    def render_tab(self, df: pd.DataFrame | None, coste_total_proyecto: float | None = None) -> None:
        st.subheader('Gastos de Viaje · Control de gasto operativo del proyecto')
        if df is None or df.empty:
            st.info('Carga los ficheros ISPR_25F o ISPR_25G para visualizar esta pestaña.')
            return
        periodos = ['Todos'] + sorted([p for p in df['periodo'].dropna().unique().tolist() if str(p).strip()])
        empleados = ['Todos'] + sorted([e for e in df['empleado'].dropna().unique().tolist() if str(e).strip()])
        categorias = ['Todos'] + sorted([c for c in df['categoria'].dropna().unique().tolist() if str(c).strip()])
        departamentos = ['Todos'] + sorted([d for d in df['departamento'].dropna().unique().tolist() if str(d).strip()])
        f1, f2, f3, f4 = st.columns(4)
        with f1:
            periodo_selected = st.selectbox('Periodo Gastos Viaje', options=periodos, key='gastos_viaje_periodo')
        with f2:
            empleado_selected = st.selectbox('Empleado viaje', options=empleados, key='gastos_viaje_empleado')
        with f3:
            categoria_selected = st.selectbox('Categoría viaje', options=categorias, key='gastos_viaje_categoria')
        with f4:
            departamento_selected = st.selectbox('Elemento / Departamento viaje', options=departamentos, key='gastos_viaje_departamento')
        filtered = df.copy()
        if periodo_selected != 'Todos':
            filtered = filtered[filtered['periodo'] == periodo_selected]
        if empleado_selected != 'Todos':
            filtered = filtered[filtered['empleado'] == empleado_selected]
        if categoria_selected != 'Todos':
            filtered = filtered[filtered['categoria'] == categoria_selected]
        if departamento_selected != 'Todos':
            filtered = filtered[filtered['departamento'] == departamento_selected]
        if filtered.empty:
            st.warning('No hay datos de Gastos de Viaje para la selección realizada.')
            return
        total_importe = float(filtered['cantidad'].sum())
        total_registros = int(len(filtered))
        total_empleados = int(filtered['empleado'].nunique())
        gasto_medio = total_importe / total_registros if total_registros else 0.0
        top_5_empleados = self.get_concentration(filtered, 'empleado', 5)
        peso_proyecto = total_importe / coste_total_proyecto * 100 if coste_total_proyecto and coste_total_proyecto > 0 else 0.0
        k1, k2, k3, k4, k5 = st.columns(5)
        with k1:
            build_metric_card('Importe total viajes (€)', format_number(total_importe, 2))
        with k2:
            build_metric_card('Registros viaje', format_number(total_registros, 0))
        with k3:
            build_metric_card('Empleados con viaje', format_number(total_empleados, 0))
        with k4:
            build_metric_card('Gasto medio (€)', format_number(gasto_medio, 2))
        with k5:
            build_metric_card('Peso sobre proyecto', f'{format_number(peso_proyecto, 1)} %')
        st.markdown('---')
        self.plot_monthly_amount(filtered, 'Evolución mensual de gastos de viaje', 'gastos_viaje_monthly')
        c1, c2 = st.columns(2)
        with c1:
            self.plot_bar(filtered, 'empleado', 'Top empleados por gasto de viaje', 'gastos_viaje_empleado_bar')
        with c2:
            self.plot_bar(filtered, 'departamento', 'Gasto de viaje por departamento', 'gastos_viaje_departamento_bar')
        c3, c4 = st.columns(2)
        with c3:
            self.plot_bar(filtered, 'categoria', 'Gasto de viaje por categoría', 'gastos_viaje_categoria_bar')
        with c4:
            self.plot_distribution(filtered, 'gastos_viaje_distribution')
        st.markdown('### Control de gastos relevantes')
        st.caption(f'El Top 5 de empleados concentra el {format_number(top_5_empleados, 1)} % del gasto filtrado.')
        top_expenses = filtered.sort_values('cantidad', ascending=False).head(25)[['periodo', 'empleado', 'departamento', 'categoria', 'descripcion', 'cantidad', 'fichero_origen']]
        render_corporate_dataframe(top_expenses, use_container_width=True, hide_index=True)