import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import time
import io
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import google.generativeai as genai
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import tempfile
import os

# ─────────────────────────────────────────────
# 1. CONFIGURACIÓN DE PÁGINA
# ─────────────────────────────────────────────
st.set_page_config(page_title="Inteligencia de Flota Jujuy", layout="wide")
if "mensaje_confirmacion" in st.session_state:
    st.success(st.session_state["mensaje_confirmacion"])
    del st.session_state["mensaje_confirmacion"]

# (Estilos CSS sin cambios)
st.markdown("""
<style>
    [data-testid="stNumberInput"] button { display: none; }
    .metric-card { background-color: #1e2130; padding: 15px; border-radius: 12px; border: 1px solid #3d425a; text-align: center; }
    .desvio-item { padding: 12px; border-radius: 8px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #3d425a; }
    .desvio-critico { background: #421212 !important; border: 1px solid #FF4B4B !important; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 2. CONFIGURACIÓN IA, USUARIOS Y CONEXIÓN
# ─────────────────────────────────────────────
# (Se mantiene tu configuración de IA y login intacta)
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

# [Configuración de USUARIOS omitida por brevedad en visualización, pero debe estar en tu archivo]
USUARIOS = {"ema_admin": {"pass": "jujuy2024", "rol": "admin"}, "visualizador": {"pass": "ver2024", "rol": "visualizador"}}
if "auth" not in st.session_state:
    st.title("🚚 Sistema de Control de Flota")
    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")
    if st.button("Ingresar"):
        if u in USUARIOS and USUARIOS[u]["pass"] == p:
            st.session_state["auth"] = True
            st.session_state["usuario"] = u
            st.session_state["rol"] = USUARIOS[u]["rol"]
            st.rerun()
    st.stop()

ROL = st.session_state.get("rol", "visualizador")
conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1PEH7lbtoq_oAHwom0O5YYYskFm6ALJ6LCj1FfQKzpmQ/edit?gid=0#gid=0"

if "precio_gasoil" not in st.session_state: st.session_state["precio_gasoil"] = 2065.0
if "umbral_consumo" not in st.session_state: st.session_state["umbral_consumo"] = 35.0

# Funciones de datos
@st.cache_data(ttl=600)
def cargar_historial():
    try:
        df = conn.read(spreadsheet=URL, ttl=0)
        cols_int = ["Movil", "KM_Ini", "KM_Fin", "KM_Recorr", "L_Ralenti", "L_Ticket", "L_Tablero", "L_Cisterna", "L_YPF"]
        for col in cols_int:
            if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
        if 'Fecha' in df.columns: df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=True, errors='coerce')
        return df
    except: 
        return pd.DataFrame()

def cargar_lista_choferes():
    try: return sorted(pd.read_excel("choferes.xlsx").iloc[:, 0].dropna().unique().tolist())
    except: return []

def cargar_historial():
    try:
        df = conn.read(spreadsheet=URL, ttl=0)
        cols_int = ["Movil", "KM_Ini", "KM_Fin", "KM_Recorr", "L_Ralenti", "L_Ticket", "L_Tablero", "L_Cisterna", "L_YPF"]
        for col in cols_int:
            if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
        if 'Fecha' in df.columns: df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=True, errors='coerce')
        return df
    except: return pd.DataFrame()

def guardar_historial(df_nuevo):
    try:
        st.write("DEBUG: Intentando guardar en Google Sheets...")
        st.write(f"DEBUG: Filas a guardar: {len(df_nuevo)}")
        
        # Intentar guardar
        conn.update(spreadsheet=URL, data=df_nuevo)
        
        st.success("✅ ¡Datos guardados exitosamente!")
    except Exception as e:
        st.error(f"❌ FALLÓ EL GUARDADO. Error técnico: {e}")
        # Esto nos mostrará el error real en pantalla, en lugar de ocultarlo
        st.exception(e)

df_h = cargar_historial()
lista_personal = cargar_lista_choferes()

# Sidebar
with st.sidebar:
    st.subheader("⚙️ Configuración")
    
    # Inicializamos valores por defecto si no existen
    if "umbral_consumo" not in st.session_state:
        st.session_state["umbral_consumo"] = 35.0
    if "precio_gasoil" not in st.session_state:
        st.session_state["precio_gasoil"] = 2065.0

    # Inputs del sidebar que actualizan el session_state
    st.session_state["umbral_consumo"] = st.number_input("Umbral Consumo (L/100km)", value=st.session_state["umbral_consumo"])
    st.session_state["precio_gasoil"] = st.number_input("Precio Gasoil ($)", value=st.session_state["precio_gasoil"])

# ─────────────────────────────────────────────
# ESTRUCTURA DE TABS (Corregida)
# ─────────────────────────────────────────────
st.title("🚚 Inteligencia de Flota y Costos")

if ROL == "admin":
    tabs = st.tabs(["📝 Registro", "👁️ Ojo de Halcón", "📜 Historial", "🤖 Asistente IA", "📈 Analítica", "💰 Costos", "📄 Reporte PDF"])
    TAB_REG, TAB_HALCON, TAB_HIST, TAB_IA, TAB_ANA, TAB_COSTOS, TAB_PDF = tabs
else:
    tabs = st.tabs(["👁️ Ojo de Halcón", "📜 Historial", "🤖 Asistente IA", "📈 Analítica", "💰 Costos", "📄 Reporte PDF"])
    TAB_HALCON, TAB_HIST, TAB_IA, TAB_ANA, TAB_COSTOS, TAB_PDF = tabs
    TAB_REG = None

# ─────────────────────────────────────────────
# 1. TAB REGISTRO (Corregido: Incluye L_Cisterna y L_YPF)
# ─────────────────────────────────────────────
if TAB_REG:
    with TAB_REG:
        st.subheader("📝 Nuevo Registro")
        
        # 1. Precarga de datos
        col_sel, col_espacio = st.columns([1, 3])
        with col_sel:
            movil_sel = st.selectbox("🔢 Selecciona Móvil", list(range(1, 101)), index=34, key="movil_reg")
        
        idx_marca, idx_chofer, km_sugerido = 0, 0, 0
        traza_ex = ["➕ NUEVA"]
        
        if not df_h.empty:
            hist_movil = df_h[df_h["Movil"] == int(movil_sel)]
            if not hist_movil.empty:
                ult_r = hist_movil.sort_values("Fecha").iloc[-1]
                km_sugerido = float(ult_r["KM_Fin"])
                if ult_r["Chofer"] in lista_personal: idx_chofer = lista_personal.index(ult_r["Chofer"])
                if ult_r["Marca"] == "SCANIA": idx_marca = 0
                elif ult_r["Marca"] == "MERCEDES BENZ": idx_marca = 1
                traza_ex = ["➕ NUEVA"] + sorted(df_h["Traza"].unique().tolist())

        # 2. Formulario
        with st.form("registro_form_final", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                marca = st.radio("🏷️ Marca", ["SCANIA", "MERCEDES BENZ"], index=idx_marca, horizontal=True)
                chofer = st.selectbox("👤 Chofer", options=lista_personal, index=idx_chofer)
                fecha_input = st.date_input("📅 Fecha de Carga", datetime.now())
            with c2:
                ruta_tipo = st.radio("🏔️ Tipo de Ruta", ["Llano", "Alta Montaña"], horizontal=True)
                traza_sel = st.selectbox("🗺️ Traza", traza_ex)
                nt = st.text_input("✍️ Nombre Nueva Traza").upper()
                t_final = nt if traza_sel == "➕ NUEVA" else traza_sel
            with c3:
                kmi = st.number_input("🛣️ KM Inicial", value=int(km_sugerido), step=1)
                kmf = st.number_input("🏁 KM Final", value=0, step=1)
                l_cisterna = st.number_input("⛽ L. Cisterna", value=0.0, step=0.1)
                l_ypf = st.number_input("⛽ L. YPF", value=0.0, step=0.1)
                ltab = st.number_input("📟 L. Tablero", value=0.0, step=0.1)
                lral = st.number_input("⏳ L. Ralentí", value=0.0, step=0.1)
            
            submit_button = st.form_submit_button("💾 GUARDAR REGISTRO", use_container_width=True)

        # 3. Lógica única de procesamiento al hacer clic
        if submit_button:
            lt_total = l_cisterna + l_ypf
            dist_v = max(0, int(kmf - kmi))
            
            # Validación
            if kmf <= kmi:
                st.error("⚠️ Error: El KM Final debe ser mayor al KM Inicial.")
            elif dist_v == 0:
                st.warning("⚠️ Atención: El recorrido es 0 KM, revisa los datos.")
            elif lt_total <= 0:
                st.error("⚠️ La suma de litros debe ser mayor a 0.")
            else:
                # Guardado
                nuevo_reg = {
                    "Fecha": fecha_input.strftime('%d/%m/%Y'),
                    "Chofer": chofer,
                    "Movil": int(movil_sel),
                    "Marca": marca,
                    "Ruta": ruta_tipo,
                    "Traza": t_final,
                    "KM_Ini": int(kmi),
                    "KM_Fin": int(kmf),
                    "KM_Recorr": dist_v,
                    "L_Ticket": lt_total,
                    "L_Cisterna": float(l_cisterna),
                    "L_YPF": float(l_ypf),
                    "L_Tablero": float(ltab),
                    "L_Ralenti": float(lral),
                    "Consumo_L100": (lt_total / dist_v * 100) if dist_v > 0 else 0,
                    "Costo_Total_ARS": lt_total * st.session_state.get("precio_gasoil", 2065.0)
                }
                
                df_final = pd.concat([df_h, pd.DataFrame([nuevo_reg])], ignore_index=True)
                guardar_historial(df_final)
                st.session_state["mensaje_confirmacion"] = "✅ Registro guardado correctamente."
                st.rerun()
# ─────────────────────────────────────────────
# TAB: OJO DE HALCÓN
# ─────────────────────────────────────────────
with TAB_HALCON:
    if df_h.empty:
        st.info("Sin datos disponibles.")
    else:
        df_ana = df_h.copy()
        # MODIFICACIÓN: Agregamos dayfirst=True y errors='coerce' para mayor seguridad
        df_ana['Fecha'] = pd.to_datetime(df_ana['Fecha'], dayfirst=True, errors='coerce')
        df_ana['Mes_Año'] = df_ana['Fecha'].dt.to_period('M').astype(str)
        st.markdown("### 🔍 Filtros")
        c_f1, c_f2 = st.columns(2)
        mes_sel = c_f1.selectbox("📅 Mes", ["Todos"] + sorted(df_ana['Mes_Año'].dropna().unique().tolist(), reverse=True))
        ruta_sel = c_f2.multiselect("🏔️ Ruta", df_ana['Ruta'].unique(), default=list(df_ana['Ruta'].unique()))
        df_filtrado = df_ana[df_ana['Ruta'].isin(ruta_sel)]
        if mes_sel != "Todos":
            df_filtrado = df_filtrado[df_filtrado['Mes_Año'] == mes_sel]
        
        csv = df_filtrado.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Descargar reporte filtrado (CSV)", csv, 'reporte_flota.csv', 'text/csv')
        st.divider()
        st.subheader("🏆 Ranking de Eficiencia (Top 5)")
        top_5 = df_filtrado.groupby("Chofer")["Consumo_L100"].mean().sort_values().head(5).reset_index()
        cols_m = st.columns(min(5, len(top_5)))
        medallas = ["🥇", "🥈", "🥉", "👤", "👤"]
        for i, row in top_5.iterrows():
            with cols_m[i]:
                st.markdown(f'<div class="metric-card"><div class="medal-icon">{medallas[i]}</div><div class="driver-name">{row["Chofer"]}</div><div class="driver-score">{row["Consumo_L100"]:.1f}</div><div style="color:#aab;font-size:12px;">L/100</div></div>', unsafe_allow_html=True)
        st.divider()
        st.subheader("⚠️ Ranking de Desvíos Críticos por Chofer (>50L)")
        df_desv = (df_filtrado.groupby("Chofer")["Desvio_Neto"].sum().reset_index().pipe(lambda d: d[d['Desvio_Neto'] > 50]).sort_values("Desvio_Neto", ascending=False))
        if df_desv.empty: st.info("✅ No hay desvíos críticos.")
        else:
            for _, row in df_desv.iterrows():
                st.markdown(f'<div class="desvio-item desvio-critico"><div><b>{row["Chofer"]}</b><br><small>🚨 Crítico (>50L)</small></div><b>{row["Desvio_Neto"]:.1f} L</b></div>', unsafe_allow_html=True)
        st.divider()
        st.subheader("📊 Desvíos Críticos por Unidad (>50L)")
        df_movil = (df_filtrado.groupby("Movil")["Desvio_Neto"].sum().reset_index().pipe(lambda d: d[d['Desvio_Neto'] > 50]).sort_values("Desvio_Neto", ascending=False))
        if df_movil.empty: st.info("✅ No hay desvíos críticos por unidad.")
        else:
            for _, row in df_movil.iterrows():
                st.markdown(f'<div class="desvio-item desvio-critico"><div><b>Unidad Nº {int(row["Movil"])}</b><br><small>🚨 Crítico (>50L)</small></div><b>{row["Desvio_Neto"]:.1f} L</b></div>', unsafe_allow_html=True)
        st.divider()
        st.subheader("📊 Comparativa: Scania vs Mercedes por Ruta")
        df_comp = df_filtrado.groupby(["Ruta", "Marca"])["Consumo_L100"].mean().reset_index()
        fig_comp = px.bar(df_comp, x="Ruta", y="Consumo_L100", color="Marca", barmode="group", text_auto='.1f', template="plotly_dark")
        st.plotly_chart(fig_comp, use_container_width=True)
        
        # --- AQUÍ ESTÁ EL BLOQUE MOVIDO (SOLO APARECERÁ EN OJO DE HALCÓN) ---
        st.divider()
        st.subheader("🗺️ Consumo Promedio por Traza")
        df_traza = (
            df_filtrado.groupby("Traza")
            .agg(
                Consumo_Promedio=("Consumo_L100", "mean"),
                Viajes=("Fecha", "count"),
                KM_Totales=("KM_Recorr", "sum"),
                Litros_Totales=("L_Ticket", "sum"),
            )
            .reset_index()
            .sort_values("Consumo_Promedio", ascending=True)
        )
        cols = st.columns(4)
        for i, (_, row) in enumerate(df_traza.iterrows()):
            with cols[i % 4]:
                is_alert = row["Consumo_Promedio"] > st.session_state.get("umbral_consumo", 35.0)
                with st.container(border=True):
                    st.metric(label=row["Traza"], value=f"{row['Consumo_Promedio']:.1f} L/100km", delta="🚨 Supera límite" if is_alert else "✅ Eficiente", delta_color="inverse" if is_alert else "normal")
                    progreso = min(row["Consumo_Promedio"] / 60, 1.0)
                    st.progress(progreso)
                    st.caption(f"{int(row['Viajes'])} viajes · {int(row['KM_Totales']):,} km")
        st.markdown("---")
        st.markdown("#### 📊 Detalle por traza")
        st.dataframe(
            df_traza.sort_values("Consumo_Promedio", ascending=False).style.map(
                lambda v: 'background-color: #421212; color: white' if isinstance(v, float) and v > st.session_state["umbral_consumo"] else '',
                subset=["Consumo_Promedio"]
            ),
            use_container_width=True,
            column_config={
                "Traza": st.column_config.TextColumn("Traza"),
                "Consumo_Promedio": st.column_config.NumberColumn("L/100km", format="%.2f"),
                "Viajes": st.column_config.NumberColumn("Viajes", format="%d"),
                "KM_Totales": st.column_config.NumberColumn("KM Total", format="%d"),
                "Litros_Totales": st.column_config.NumberColumn("Litros", format="%.1f"),
            }
        )

# ─────────────────────────────────────────────
# TAB: ANALÍTICA
# ─────────────────────────────────────────────
with TAB_ANA:
    st.subheader("📈 Analítica y Diagnóstico")

    if df_h.empty:
        st.info("Sin datos disponibles.")
    else:
        df_ana2 = df_h.copy()
        df_ana2['Fecha'] = pd.to_datetime(df_ana2['Fecha'], errors='coerce')
        df_ana2['Mes']   = df_ana2['Fecha'].dt.to_period('M').astype(str)

        st.markdown("### 📉 Tendencia de Consumo vs. Promedio Flota")
        df_prom_flota = df_ana2.groupby('Mes')['Consumo_L100'].mean().reset_index()
        df_prom_flota.rename(columns={'Consumo_L100': 'Promedio_Flota'}, inplace=True)

        moviles_sel = st.multiselect(
            "Seleccionar Móviles para comparar",
            options=sorted(df_ana2['Movil'].unique()),
            default=[df_ana2['Movil'].iloc[0]]
        )
        if moviles_sel:
            df_tend = df_ana2[df_ana2['Movil'].isin(moviles_sel)]
            df_tend = df_tend.groupby(['Mes', 'Movil'])['Consumo_L100'].mean().reset_index()
            fig_line = px.line(df_tend, x="Mes", y="Consumo_L100", color="Movil",
                               markers=True, template="plotly_dark",
                               labels={"Consumo_L100": "Consumo (L/100km)", "Mes": "Periodo"})
            fig_line.add_scatter(
                x=df_prom_flota['Mes'], y=df_prom_flota['Promedio_Flota'],
                mode='lines', name='Promedio Flota',
                line=dict(color='white', width=2, dash='dash')
            )
            # Línea de umbral
            fig_line.add_hline(
            y=st.session_state["umbral_consumo"], 
            line_dash="dot", 
            line_color="red",
            annotation_text=f"Umbral ({st.session_state['umbral_consumo']:.0f} L/100)", 
            annotation_position="top left"
            )
            fig_line.update_layout(hovermode="x unified")
            st.plotly_chart(fig_line, use_container_width=True)
            st.info("💡 La línea punteada blanca es el promedio de la flota. La línea roja es el umbral de alerta.")
        else:
            st.warning("Seleccioná al menos un móvil.")

        st.markdown("### ⚖️ Benchmark: Marca vs Ruta")
        df_bench = df_ana2.groupby(['Marca', 'Ruta'])['Consumo_L100'].mean().reset_index()
        fig_bar  = px.bar(df_bench, x="Ruta", y="Consumo_L100", color="Marca",
                          barmode="group", text_auto='.1f', template="plotly_dark",
                          title="Consumo Promedio (L/100km)")
        st.plotly_chart(fig_bar, use_container_width=True)

# ─────────────────────────────────────────────
# TAB: COSTOS
# ─────────────────────────────────────────────
with TAB_COSTOS:
    st.subheader("💰 Análisis de Costos")

    if df_h.empty:
        st.info("Sin datos disponibles.")
    else:
        df_cos = df_h.copy()
        df_cos['Fecha'] = pd.to_datetime(df_cos['Fecha'], errors='coerce')
        df_cos['Mes']   = df_cos['Fecha'].dt.to_period('M').astype(str)

        # ── Métricas resumen ──
        mes_actual    = pd.Timestamp.today().to_period('M').strftime('%Y-%m')
        df_mes_act    = df_cos[df_cos['Mes'] == mes_actual]
        df_mes_ant_dt = pd.Timestamp.today() - pd.DateOffset(months=1)
        mes_ant       = df_mes_ant_dt.to_period('M').strftime('%Y-%m')
        df_mes_ant    = df_cos[df_cos['Mes'] == mes_ant]

        costo_actual  = df_mes_act['Costo_Total_ARS'].sum()
        costo_ant     = df_mes_ant['Costo_Total_ARS'].sum()
        delta_costo   = costo_actual - costo_ant

        litros_actual = df_mes_act['L_Ticket'].sum()
        km_actual     = df_mes_act['KM_Recorr'].sum() if 'KM_Recorr' in df_mes_act.columns else 0
        costo_x_km    = (costo_actual / km_actual) if km_actual > 0 else 0

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("💰 Costo mes actual",    f"${costo_actual:,.0f}",  delta=f"${delta_costo:,.0f} vs mes ant.")
        m2.metric("⛽ Litros mes actual",   f"{litros_actual:,.0f} L")
        m3.metric("📏 KM mes actual",       f"{km_actual:,.0f} km")
        m4.metric("💵 Costo por KM",        f"${costo_x_km:,.1f}/km")

        st.divider()

        # ── Gasto mensual ──
        st.markdown("### 📅 Gasto mensual")
        df_mensual = df_cos.groupby('Mes').agg(
            Costo_Total=('Costo_Total_ARS', 'sum'),
            Litros=('L_Ticket', 'sum'),
            Viajes=('Fecha', 'count')
        ).reset_index().sort_values('Mes')

        fig_cos = px.bar(df_mensual, x='Mes', y='Costo_Total',
                         text_auto='.2s', template='plotly_dark',
                         labels={'Costo_Total': 'Costo ARS', 'Mes': 'Período'},
                         title='Gasto total por mes')
        st.plotly_chart(fig_cos, use_container_width=True)

        # ── Proyección del mes en curso ──
        st.markdown("### 🔮 Proyección del mes en curso")
        hoy        = pd.Timestamp.today()
        dias_trans = hoy.day
        dias_mes   = hoy.days_in_month
        proyeccion = (costo_actual / dias_trans * dias_mes) if dias_trans > 0 else 0

        col_p1, col_p2 = st.columns(2)
        col_p1.metric("📈 Proyección de cierre del mes", f"${proyeccion:,.0f}")
        col_p2.metric("📆 Días transcurridos",           f"{dias_trans} / {dias_mes}")

        # ── Costo por unidad ──
        st.markdown("### 🚛 Costo acumulado por unidad")
        df_x_movil = df_cos.groupby('Movil')['Costo_Total_ARS'].sum().reset_index().sort_values('Costo_Total_ARS', ascending=False)
        fig_movil  = px.bar(df_x_movil, x='Movil', y='Costo_Total_ARS',
                            text_auto='.2s', template='plotly_dark',
                            labels={'Costo_Total_ARS': 'Costo ARS', 'Movil': 'Unidad'},
                            title='Costo total por unidad')
        st.plotly_chart(fig_movil, use_container_width=True)

        # ── Costo por chofer ──
        st.markdown("### 👤 Costo acumulado por chofer")
        df_x_chof = df_cos.groupby('Chofer')['Costo_Total_ARS'].sum().reset_index().sort_values('Costo_Total_ARS', ascending=False).head(10)
        fig_chof  = px.bar(df_x_chof, x='Chofer', y='Costo_Total_ARS',
                           text_auto='.2s', template='plotly_dark',
                           labels={'Costo_Total_ARS': 'Costo ARS'},
                           title='Top 10 choferes por costo acumulado')
        st.plotly_chart(fig_chof, use_container_width=True)

# ─────────────────────────────────────────────
# TAB: REPORTE PDF
# ─────────────────────────────────────────────
with TAB_PDF:
    st.subheader("📄 Generar Reporte PDF Mensual")

    if df_h.empty:
        st.info("Sin datos para generar el reporte.")
    else:
        df_pdf_base = df_h.copy()
        df_pdf_base['Fecha'] = pd.to_datetime(df_pdf_base['Fecha'], errors='coerce')
        df_pdf_base['Mes']   = df_pdf_base['Fecha'].dt.to_period('M').astype(str)

        meses_disp = sorted(df_pdf_base['Mes'].dropna().astype(str).unique().tolist(), reverse=True)
        mes_pdf    = st.selectbox("📅 Seleccioná el mes para el reporte", meses_disp)

        if st.button("🖨️ Generar PDF", use_container_width=True):
            df_mes = df_pdf_base[df_pdf_base['Mes'] == mes_pdf].copy()

            if df_mes.empty:
                st.warning("No hay datos para ese mes.")
            else:
                with st.spinner("Generando reporte PDF..."):
                    buf = io.BytesIO()
                    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                                            rightMargin=1.5*cm, leftMargin=1.5*cm,
                                            topMargin=1.5*cm, bottomMargin=1.5*cm)
                    styles  = getSampleStyleSheet()
                    story   = []
                    tmpfiles = []

                    # Estilos custom
                    title_style = ParagraphStyle('title', parent=styles['Title'],
                                                 fontSize=18, spaceAfter=6, alignment=TA_CENTER)
                    h2_style    = ParagraphStyle('h2', parent=styles['Heading2'],
                                                 fontSize=13, spaceAfter=4, spaceBefore=12)
                    body_style  = ParagraphStyle('body', parent=styles['Normal'],
                                                 fontSize=9, spaceAfter=4)

                    # ── Portada ──
                    story.append(Paragraph("🚚 Inteligencia de Flota — Jujuy", title_style))
                    story.append(Paragraph(f"Reporte mensual: {mes_pdf}", styles['Heading3']))
                    story.append(Paragraph(f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')}", body_style))
                    story.append(Spacer(1, 0.4*cm))

                    # ── Resumen ejecutivo ──
                    story.append(Paragraph("📊 Resumen Ejecutivo", h2_style))
                    total_viajes  = len(df_mes)
                    total_km      = df_mes['KM_Recorr'].sum() if 'KM_Recorr' in df_mes.columns else 0
                    total_litros  = df_mes['L_Ticket'].sum()
                    total_costo   = df_mes['Costo_Total_ARS'].sum()
                    avg_cons      = df_mes['Consumo_L100'].mean()
                    alertas_mes   = len(df_mes[df_mes['Consumo_L100'] > UMBRAL])

                    resumen_data = [
                        ['Métrica', 'Valor'],
                        ['Total de viajes',           str(total_viajes)],
                        ['KM totales recorridos',     f"{total_km:,.0f} km"],
                        ['Litros consumidos',         f"{total_litros:,.1f} L"],
                        ['Costo total',               f"${total_costo:,.0f} ARS"],
                        ['Consumo promedio',          f"{avg_cons:.2f} L/100km"],
                        [f'Alertas (>{UMBRAL:.0f} L/100km)', str(alertas_mes)],
                    ]
                    t_resumen = Table(resumen_data, colWidths=[8*cm, 8*cm])
                    t_resumen.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a5f')),
                        ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
                        ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE',   (0, 0), (-1, -1), 9),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
                        ('GRID',       (0, 0), (-1, -1), 0.3, colors.grey),
                        ('ALIGN',      (0, 0), (-1, -1), 'LEFT'),
                        ('LEFTPADDING', (0, 0), (-1, -1), 8),
                    ]))
                    story.append(t_resumen)
                    story.append(Spacer(1, 0.5*cm))

                    # ── Gráfico 1: Consumo por chofer (matplotlib) ──
                    story.append(Paragraph("📈 Consumo Promedio por Chofer (L/100km)", h2_style))
                    df_g1 = df_mes.groupby('Chofer')['Consumo_L100'].mean().sort_values(ascending=True)
                    fig1, ax1 = plt.subplots(figsize=(10, max(3, len(df_g1) * 0.4)))
                    bar_colors = ['#FF4B4B' if v > UMBRAL else '#4CAF50' for v in df_g1.values]
                    ax1.barh(df_g1.index, df_g1.values, color=bar_colors)
                    ax1.axvline(UMBRAL, color='orange', linestyle='--', label=f'Umbral {UMBRAL:.0f}')
                    ax1.set_xlabel('L/100km')
                    ax1.legend()
                    ax1.set_facecolor('#1e2130')
                    fig1.patch.set_facecolor('#1e2130')
                    ax1.tick_params(colors='white')
                    ax1.xaxis.label.set_color('white')
                    for spine in ax1.spines.values():
                        spine.set_edgecolor('#444')
                    plt.tight_layout()
                    tmp1 = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
                    tmpfiles.append(tmp1.name)
                    fig1.savefig(tmp1.name, dpi=120, bbox_inches='tight', facecolor='#1e2130')
                    plt.close(fig1)
                    story.append(RLImage(tmp1.name, width=22*cm, height=max(5*cm, len(df_g1)*0.8*cm)))
                    story.append(Spacer(1, 0.5*cm))

                    # ── Gráfico 2: Costo por unidad ──
                    story.append(Paragraph("💰 Costo Total por Unidad (ARS)", h2_style))
                    df_g2 = df_mes.groupby('Movil')['Costo_Total_ARS'].sum().sort_values(ascending=False).head(15)
                    fig2, ax2 = plt.subplots(figsize=(10, 4))
                    ax2.bar([f"C{int(m)}" for m in df_g2.index], df_g2.values, color='#4a90e2')
                    ax2.set_ylabel('ARS')
                    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'${x:,.0f}'))
                    ax2.set_facecolor('#1e2130')
                    fig2.patch.set_facecolor('#1e2130')
                    ax2.tick_params(colors='white', axis='both')
                    ax2.yaxis.label.set_color('white')
                    for spine in ax2.spines.values():
                        spine.set_edgecolor('#444')
                    plt.xticks(rotation=45)
                    plt.tight_layout()
                    tmp2 = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
                    tmpfiles.append(tmp2.name)
                    fig2.savefig(tmp2.name, dpi=120, bbox_inches='tight', facecolor='#1e2130')
                    plt.close(fig2)
                    story.append(RLImage(tmp2.name, width=22*cm, height=7*cm))
                    story.append(Spacer(1, 0.5*cm))

                    # ── Tabla de datos ──
                    story.append(Paragraph("📋 Detalle de Registros del Mes", h2_style))
                    cols_tabla = ['Fecha', 'Chofer', 'Movil', 'Marca', 'Ruta',
                                  'KM_Recorr', 'L_Ticket', 'Consumo_L100', 'Costo_Total_ARS', 'Desvio_Neto']
                    cols_tabla = [c for c in cols_tabla if c in df_mes.columns]
                    df_tabla   = df_mes[cols_tabla].copy()
                    df_tabla['Fecha'] = df_tabla['Fecha'].dt.strftime('%d/%m/%Y')

                    headers     = ['Fecha', 'Chofer', 'Móvil', 'Marca', 'Ruta',
                                   'KM', 'Litros', 'L/100', 'Costo $', 'Desvío'][:len(cols_tabla)]
                    tabla_data  = [headers]
                    for _, row in df_tabla.iterrows():
                        fila = []
                        for c in cols_tabla:
                            v = row[c]
                            if isinstance(v, float): fila.append(f"{v:.1f}")
                            else: fila.append(str(v))
                        tabla_data.append(fila)

                    col_w  = [2.5*cm, 4*cm, 1.5*cm, 3*cm, 2*cm, 2*cm, 2*cm, 2*cm, 3*cm, 2*cm]
                    col_w  = col_w[:len(cols_tabla)]
                    t_data = Table(tabla_data, colWidths=col_w, repeatRows=1)

                    row_styles = [
                        ('BACKGROUND',  (0, 0), (-1, 0),  colors.HexColor('#1e3a5f')),
                        ('TEXTCOLOR',   (0, 0), (-1, 0),  colors.white),
                        ('FONTNAME',    (0, 0), (-1, 0),  'Helvetica-Bold'),
                        ('FONTSIZE',    (0, 0), (-1, -1), 7),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
                        ('GRID',        (0, 0), (-1, -1), 0.2, colors.grey),
                        ('ALIGN',       (0, 0), (-1, -1), 'CENTER'),
                    ]
                    # Resaltar alertas en rojo
                    if 'Consumo_L100' in cols_tabla:
                        ci = cols_tabla.index('Consumo_L100')
                        for ri, row in enumerate(df_tabla.itertuples(), start=1):
                            val = getattr(row, 'Consumo_L100', 0)
                            if val > st.session_state.get("umbral_consumo", 35.0):
                                row_styles.append(('BACKGROUND', (ci, ri), (ci, ri), colors.HexColor('#421212')))
                                row_styles.append(('TEXTCOLOR',  (ci, ri), (ci, ri), colors.HexColor('#FF4B4B')))

                    t_data.setStyle(TableStyle(row_styles))
                    story.append(t_data)

                    doc.build(story)

                    # Limpiar temporales
                    for f in tmpfiles:
                        try: os.unlink(f)
                        except: pass

                    buf.seek(0)
                    st.success("✅ PDF generado correctamente.")
                    st.download_button(
                        label     = "📥 Descargar Reporte PDF",
                        data      = buf,
                        file_name = f"reporte_flota_{mes_pdf}.pdf",
                        mime      = "application/pdf",
                        use_container_width=True
                    )
