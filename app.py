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

st.markdown("""
<style>
    [data-testid="stNumberInput"] button { display: none; }
    .metric-card {
        background-color: #1e2130; padding: 15px; border-radius: 12px;
        border: 1px solid #3d425a; text-align: center;
    }
    .driver-name { font-weight: bold; font-size: 16px; margin: 5px 0; color: white; }
    .driver-score { font-size: 24px; color: #4CAF50; font-weight: bold; }
    .medal-icon { font-size: 32px; margin-bottom: 5px; }
    .desvio-item {
        padding: 12px; border-radius: 8px; margin-bottom: 10px;
        display: flex; justify-content: space-between; align-items: center;
        border: 1px solid #3d425a;
    }
    .desvio-critico { background: #421212 !important; border: 1px solid #FF4B4B !important; }
    .alert-banner {
        background: #421212; border: 1px solid #FF4B4B; border-radius: 10px;
        padding: 14px 18px; margin-bottom: 10px; color: white; font-size: 15px;
    }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 2. CONFIGURACIÓN IA GEMINI
# FIX: Se crea correctamente el objeto `model`
# ─────────────────────────────────────────────
model = None
if "GOOGLE_API_KEY" in st.secrets:
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"].strip().strip('"'))
        model = genai.GenerativeModel('gemini-2.0-flash-lite')
    except Exception as e:
        st.warning(f"⚠️ Error al configurar IA: {e}")

# ─────────────────────────────────────────────
# 3. USUARIOS Y LOGIN
# ─────────────────────────────────────────────
USUARIOS = {
    "ema_admin":    {"pass": "jujuy2024", "rol": "admin"},
    "visualizador": {"pass": "ver2024",   "rol": "visualizador"},
}

if "auth" not in st.session_state:
    st.title("🚚 Sistema de Control de Flota")
    _, col_log, _ = st.columns([1, 2, 1])
    with col_log:
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.button("Ingresar", use_container_width=True):
            if u in USUARIOS and USUARIOS[u]["pass"] == p:
                st.session_state["auth"]    = True
                st.session_state["usuario"] = u
                st.session_state["rol"]     = USUARIOS[u]["rol"]
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos")
    st.stop()

ROL = st.session_state.get("rol", "visualizador")

# ─────────────────────────────────────────────
# 4. CONEXIÓN GOOGLE SHEETS
# ─────────────────────────────────────────────
conn = st.connection("gsheets", type=GSheetsConnection)
URL  = "https://docs.google.com/spreadsheets/d/1PEH7lbtoq_oAHwom0O5YYYskFm6ALJ6LCj1FfQKzpmQ/edit?gid=0#gid=0"

# ─────────────────────────────────────────────
# 5. SESSION STATE — valores por defecto
# ─────────────────────────────────────────────
if "precio_gasoil"   not in st.session_state: st.session_state["precio_gasoil"]   = 2065.0
if "umbral_consumo"  not in st.session_state: st.session_state["umbral_consumo"]  = 35.0
if "ai_cache"        not in st.session_state: st.session_state["ai_cache"]        = {}
if "messages"        not in st.session_state: st.session_state["messages"]        = []
if "ultimo_call"     not in st.session_state: st.session_state["ultimo_call"]     = 0

# ─────────────────────────────────────────────
# 6. FUNCIONES DE DATOS
# ─────────────────────────────────────────────
@st.cache_data(ttl=600)
def cargar_lista_choferes():
    try:
        return sorted(pd.read_excel("choferes.xlsx").iloc[:, 0].dropna().unique().tolist())
    except:
        return []

def cargar_historial():
    try:
        df = conn.read(spreadsheet=URL, ttl=0)
        cols_num = ["Movil", "KM_Ini", "KM_Fin", "KM_Recorr",
                    "L_Ticket", "L_Cisterna", "L_YPF", "L_Tablero", "L_Ralenti",
                    "Consumo_L100", "Costo_Total_ARS", "Desvio_Neto"]
        for col in cols_num:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        if 'Fecha' in df.columns:
            def parsear_fecha(val):
                if pd.isna(val):
                    return pd.NaT
                s = str(val).strip()
                # Intenta DD/MM/YYYY
                for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%Y/%m/%d'):
                    try:
                        return pd.to_datetime(s[:10], format=fmt)
                    except:
                        continue
                # Último recurso: pandas infiere
                try:
                    return pd.to_datetime(s, dayfirst=True, errors='coerce')
                except:
                    return pd.NaT

            df['Fecha'] = df['Fecha'].apply(parsear_fecha)
            # FIX: NaT se deja como NaT, NO se rellena con hoy
            cols_int = ["Movil", "KM_Ini", "KM_Fin", "KM_Recorr"]
            cols_float = ["L_Ticket", "L_Cisterna", "L_YPF", "L_Tablero", "L_Ralenti",
                          "Consumo_L100", "Costo_Total_ARS", "Desvio_Neto"]
            for col in cols_int:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)

for col in cols_float:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).round(3)

            # así podés identificar registros con fecha problemática
            df = df.dropna(subset=['Fecha'])

        return df
    except Exception as e:
        st.error(f"Error al cargar datos: {e}")
        return pd.DataFrame()

def guardar_historial(df_nuevo):
    """Convierte fechas a texto DD/MM/YYYY antes de escribir para evitar 0:00:00."""
    df_save = df_nuevo.copy()
    df_save['Fecha'] = pd.to_datetime(df_save['Fecha'], errors='coerce').dt.strftime('%d/%m/%Y')
    conn.update(spreadsheet=URL, data=df_save)

# ─────────────────────────────────────────────
# 7. CARGA INICIAL
# ─────────────────────────────────────────────
df_h = cargar_historial()
lista_personal = cargar_lista_choferes()

# FIX: fallback seguro si choferes.xlsx no existe
if not lista_personal and not df_h.empty:
    lista_personal = sorted(df_h["Chofer"].dropna().unique().tolist())
if not lista_personal:
    lista_personal = ["SIN CHOFERES"]

# ─────────────────────────────────────────────
# 8. SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"👤 **{st.session_state.get('usuario', '?')}** ({ROL})")
    if st.button("🚪 Cerrar sesión", use_container_width=True):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

    st.divider()
    st.subheader("⚙️ Configuración")
    st.session_state["umbral_consumo"] = st.number_input(
        "🚨 Umbral consumo (L/100km)",
        min_value=10.0, max_value=80.0,
        value=st.session_state["umbral_consumo"], step=1.0
    )
    st.session_state["precio_gasoil"] = st.number_input(
        "💰 Precio gasoil ($/L)",
        min_value=0.0,
        value=st.session_state["precio_gasoil"], step=10.0
    )

# Atajo local para no repetir st.session_state["umbral_consumo"] en todo el código
UMBRAL = st.session_state["umbral_consumo"]

# ─────────────────────────────────────────────
# 9. TÍTULO Y TABS
# ─────────────────────────────────────────────
st.title("🚚 Inteligencia de Flota y Costos")

if ROL == "admin":
    tabs = st.tabs(["📝 Registro", "👁️ Ojo de Halcón", "📜 Historial",
                    "🤖 Asistente IA", "📈 Analítica", "💰 Costos", "📄 Reporte PDF"])
    TAB_REG, TAB_HALCON, TAB_HIST, TAB_IA, TAB_ANA, TAB_COSTOS, TAB_PDF = tabs
else:
    tabs = st.tabs(["👁️ Ojo de Halcón", "📜 Historial",
                    "🤖 Asistente IA", "📈 Analítica", "💰 Costos", "📄 Reporte PDF"])
    TAB_HALCON, TAB_HIST, TAB_IA, TAB_ANA, TAB_COSTOS, TAB_PDF = tabs
    TAB_REG = None

# ─────────────────────────────────────────────
# TAB: REGISTRO (solo admin)
# ─────────────────────────────────────────────
if TAB_REG:
    with TAB_REG:
        st.subheader("📝 Nuevo Registro")

        col_m1, _ = st.columns([1, 3])
        movil_sel = col_m1.selectbox("🔢 Selecciona Móvil", list(range(1, 101)), index=34, key="movil_reg")

        # Precarga datos del último registro de ese móvil
        idx_marca, idx_chofer, km_sugerido = 0, 0, 0
        traza_ex = ["➕ NUEVA"]
        if not df_h.empty:
            hist_movil = df_h[df_h["Movil"] == int(movil_sel)]
            if not hist_movil.empty:
                ult_r = hist_movil.sort_values("Fecha").iloc[-1]
                km_sugerido = float(ult_r["KM_Fin"])
                if ult_r["Chofer"] in lista_personal:
                    idx_chofer = lista_personal.index(ult_r["Chofer"])
                if ult_r["Marca"] == "SCANIA":        idx_marca = 0
                elif ult_r["Marca"] == "MERCEDES BENZ": idx_marca = 1
                traza_ex = ["➕ NUEVA"] + sorted(df_h["Traza"].dropna().unique().tolist())

        with st.form("registro_form_final", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)

            with c1:
                marca       = st.radio("🏷️ Marca", ["SCANIA", "MERCEDES BENZ"], index=idx_marca, horizontal=True)
                chofer      = st.selectbox("👤 Chofer", options=lista_personal, index=idx_chofer)
                fecha_input = st.date_input("📅 Fecha de Carga", datetime.now())

            with c2:
                ruta_tipo = st.radio("🏔️ Tipo de Ruta", ["Llano", "Alta Montaña"], horizontal=True)
                traza_sel = st.selectbox("🗺️ Traza", traza_ex)
                nt        = st.text_input("✍️ Nombre Nueva Traza").upper()
                t_final   = nt if traza_sel == "➕ NUEVA" else traza_sel

            with c3:
                kmi        = st.number_input("🛣️ KM Inicial",   value=int(km_sugerido), step=1)
                kmf        = st.number_input("🏁 KM Final",      value=0, step=1)
                l_cisterna = st.number_input("⛽ L. Cisterna",   value=0.0, step=0.1)
                l_ypf      = st.number_input("⛽ L. YPF",        value=0.0, step=0.1)
                ltab       = st.number_input("📟 L. Tablero",    value=0.0, step=0.1)
                lral       = st.number_input("⏳ L. Ralentí",    value=0.0, step=0.1)

            # Cálculos en tiempo real (dentro del form para que se actualicen)
            st.divider()
            lt_total  = l_cisterna + l_ypf
            dist_v    = max(0, int(kmf - kmi))
            cons_prev = (lt_total / dist_v * 100) if dist_v > 0 else 0.0
            costo_prev = lt_total * st.session_state["precio_gasoil"]
            # FIX: Desvío = litros ticket - (tablero + ralentí), no vs umbral
            desvio_prev = round(lt_total - (ltab + lral), 2)

            c_met1, c_met2, c_met3, c_met4 = st.columns(4)
            c_met1.metric("🛣️ KM",        f"{dist_v:,.0f}")
            c_met2.metric("🔢 Promedio",  f"{cons_prev:.1f} L/100")
            c_met3.metric("💰 Costo",     f"${costo_prev:,.0f}")
            c_met4.metric("🚨 Desvío",    f"{desvio_prev:.1f} L")

            if cons_prev > UMBRAL and dist_v > 0:
                st.markdown(
                    f'<div class="alert-banner">🚨 <b>ALERTA:</b> Consumo calculado '
                    f'({cons_prev:.1f} L/100km) supera el umbral ({UMBRAL:.0f} L/100km).</div>',
                    unsafe_allow_html=True
                )

            _, c_centro, _ = st.columns([1, 2, 1])
            with c_centro:
                submit_button = st.form_submit_button("💾 GUARDAR REGISTRO", use_container_width=True)

        if submit_button:
            lt_total = l_cisterna + l_ypf
            dist_v   = max(0, int(kmf - kmi))
            if kmf <= kmi:
                st.error("⚠️ El KM Final debe ser mayor al Inicial.")
            elif lt_total <= 0:
                st.error("⚠️ La suma de litros debe ser mayor a 0.")
            elif not t_final:
                st.error("⚠️ Ingresá un nombre de traza.")
            else:
                cons_final  = round((lt_total / dist_v * 100) if dist_v > 0 else 0, 2)
                # FIX: Desvio_Neto se calcula y se guarda correctamente
                desvio_neto = round(lt_total - (ltab + lral), 2)

                nuevo_reg = {
                    "Fecha":           fecha_input.strftime('%d/%m/%Y'),
                    "Chofer":          chofer,
                    "Movil":           int(movil_sel),
                    "Marca":           marca,
                    "Ruta":            ruta_tipo,
                    "Traza":           t_final,
                    "KM_Ini":          int(kmi),
                    "KM_Fin":          int(kmf),
                    "KM_Recorr":       dist_v,
                    "L_Ticket":        round(lt_total, 3),
                    "L_Cisterna":      round(float(l_cisterna), 3),
                    "L_YPF":           round(float(l_ypf), 3),
                    "L_Tablero":       round(float(ltab), 3),
                    "L_Ralenti":       round(float(lral), 3),
                    "Consumo_L100":    cons_final,
                    "Costo_Total_ARS": round(lt_total * st.session_state["precio_gasoil"], 2),
                    "Desvio_Neto":     desvio_neto,   # FIX: ahora se guarda
                }
                guardar_historial(pd.concat([df_h, pd.DataFrame([nuevo_reg])], ignore_index=True))

                if cons_final > UMBRAL:
                    st.warning(f"⚠️ Guardado, pero el consumo ({cons_final} L/100km) supera el umbral.")
                else:
                    st.success("✅ Registro guardado correctamente.")
                time.sleep(1)
                st.rerun()

# ─────────────────────────────────────────────
# TAB: OJO DE HALCÓN
# ─────────────────────────────────────────────
with TAB_HALCON:
    if df_h.empty:
        st.info("Sin datos disponibles.")
    else:
        df_ana = df_h.copy()
        df_ana['Fecha']   = pd.to_datetime(df_ana['Fecha'], errors='coerce')
        df_ana['Mes_Año'] = df_ana['Fecha'].dt.to_period('M').astype(str)

        st.markdown("### 🔍 Filtros")
        c_f1, c_f2 = st.columns(2)
        mes_sel  = c_f1.selectbox("📅 Mes", ["Todos"] + sorted(df_ana['Mes_Año'].unique().tolist(), reverse=True))
        ruta_sel = c_f2.multiselect("🏔️ Ruta", df_ana['Ruta'].unique(), default=list(df_ana['Ruta'].unique()))

        df_filtrado = df_ana[df_ana['Ruta'].isin(ruta_sel)]
        if mes_sel != "Todos":
            df_filtrado = df_filtrado[df_filtrado['Mes_Año'] == mes_sel]

        # Alertas automáticas
        alertas = df_filtrado[df_filtrado['Consumo_L100'] > UMBRAL]
        if not alertas.empty:
            st.markdown(f"### 🚨 Alertas de consumo alto (> {UMBRAL:.0f} L/100km)")
            for _, row in alertas.iterrows():
                st.markdown(
                    f'<div class="alert-banner">🚨 <b>{row["Chofer"]}</b> — '
                    f'Móvil {int(row["Movil"])} — {row["Consumo_L100"]:.1f} L/100km '
                    f'el {pd.Timestamp(row["Fecha"]).strftime("%d/%m/%Y")}</div>',
                    unsafe_allow_html=True
                )
            st.divider()

        csv = df_filtrado.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Descargar reporte filtrado (CSV)", csv, 'reporte_flota.csv', 'text/csv')

        st.divider()
        st.subheader("🏆 Ranking de Eficiencia (Top 5)")
        top_5 = df_filtrado.groupby("Chofer")["Consumo_L100"].mean().sort_values().head(5).reset_index()
        if not top_5.empty:
            cols_m   = st.columns(min(5, len(top_5)))
            medallas = ["🥇", "🥈", "🥉", "👤", "👤"]
            for i, row in top_5.iterrows():
                with cols_m[i]:
                    st.markdown(
                        f'<div class="metric-card">'
                        f'<div class="medal-icon">{medallas[i]}</div>'
                        f'<div class="driver-name">{row["Chofer"]}</div>'
                        f'<div class="driver-score">{row["Consumo_L100"]:.1f}</div>'
                        f'<div style="color:#aab;font-size:12px;">L/100</div></div>',
                        unsafe_allow_html=True
                    )

        st.divider()
        st.subheader("⚠️ Ranking de Desvíos Críticos por Chofer (>50L)")
        if "Desvio_Neto" in df_filtrado.columns:
            df_desv = (df_filtrado.groupby("Chofer")["Desvio_Neto"].sum()
                       .reset_index()
                       .pipe(lambda d: d[d['Desvio_Neto'] > 50])
                       .sort_values("Desvio_Neto", ascending=False))
            if df_desv.empty:
                st.info("✅ No hay desvíos críticos.")
            else:
                for _, row in df_desv.iterrows():
                    st.markdown(
                        f'<div class="desvio-item desvio-critico">'
                        f'<div><b>{row["Chofer"]}</b><br><small>🚨 Crítico (>50L)</small></div>'
                        f'<b>{row["Desvio_Neto"]:.1f} L</b></div>',
                        unsafe_allow_html=True
                    )
        else:
            st.info("ℹ️ No hay datos de desvío disponibles aún.")

        st.divider()
        st.subheader("📊 Desvíos Críticos por Unidad (>50L)")
        if "Desvio_Neto" in df_filtrado.columns:
            df_movil = (df_filtrado.groupby("Movil")["Desvio_Neto"].sum()
                        .reset_index()
                        .pipe(lambda d: d[d['Desvio_Neto'] > 50])
                        .sort_values("Desvio_Neto", ascending=False))
            if df_movil.empty:
                st.info("✅ No hay desvíos críticos por unidad.")
            else:
                for _, row in df_movil.iterrows():
                    st.markdown(
                        f'<div class="desvio-item desvio-critico">'
                        f'<div><b>Unidad Nº {int(row["Movil"])}</b><br><small>🚨 Crítico (>50L)</small></div>'
                        f'<b>{row["Desvio_Neto"]:.1f} L</b></div>',
                        unsafe_allow_html=True
                    )

        st.divider()
        st.subheader("📊 Comparativa: Scania vs Mercedes por Ruta")
        df_comp = df_filtrado.groupby(["Ruta", "Marca"])["Consumo_L100"].mean().reset_index()
        fig_comp = px.bar(df_comp, x="Ruta", y="Consumo_L100", color="Marca",
                          barmode="group", text_auto='.1f', template="plotly_dark")
        st.plotly_chart(fig_comp, use_container_width=True)

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
        for i in range(0, len(df_traza), 4):
            cols_t = st.columns(4)
            for j, (_, row) in enumerate(df_traza.iloc[i:i+4].iterrows()):
                is_alert    = row["Consumo_Promedio"] > UMBRAL
                color_score = "#FF4B4B" if is_alert else "#4CAF50"
                icono       = "🚨" if is_alert else "✅"
                with cols_t[j]:
                    st.markdown(f"""
                        <div class="metric-card">
                            <div class="medal-icon">{icono}</div>
                            <div class="driver-name" style="font-size:13px;">{row["Traza"]}</div>
                            <div class="driver-score" style="color:{color_score};">
                                {row["Consumo_Promedio"]:.1f}
                            </div>
                            <div style="color:#aab;font-size:11px;">L/100km</div>
                            <div style="color:#aab;font-size:11px;margin-top:6px;">
                                {int(row["Viajes"])} viajes · {int(row["KM_Totales"]):,} km
                            </div>
                        </div>
                    """, unsafe_allow_html=True)

        st.markdown("#### 📊 Detalle por traza")
        st.dataframe(
            df_traza.sort_values("Consumo_Promedio", ascending=False).style.map(
                lambda v: 'background-color: #421212; color: white'
                if isinstance(v, float) and v > UMBRAL else '',
                subset=["Consumo_Promedio"]
            ),
            use_container_width=True,
            column_config={
                "Traza":            st.column_config.TextColumn("Traza"),
                "Consumo_Promedio": st.column_config.NumberColumn("L/100km",  format="%.2f"),
                "Viajes":           st.column_config.NumberColumn("Viajes",   format="%d"),
                "KM_Totales":       st.column_config.NumberColumn("KM Total", format="%d"),
                "Litros_Totales":   st.column_config.NumberColumn("Litros",   format="%.1f"),
            }
        )

# ─────────────────────────────────────────────
# TAB: HISTORIAL
# FIX: Muestra todos los registros con filtros útiles
# ─────────────────────────────────────────────
with TAB_HIST:
    st.subheader("📋 Historial de Registros")
    if df_h.empty:
        st.info("No hay datos cargados.")
    else:
        df_hist = df_h.copy()
        df_hist['Fecha'] = pd.to_datetime(df_hist['Fecha'], errors='coerce')
        df_hist['Mes_Año'] = df_hist['Fecha'].dt.to_period('M').astype(str)

        # Filtros
        h1, h2, h3 = st.columns(3)
        filtro_mes    = h1.selectbox("📅 Mes", ["Todos"] + sorted(df_hist['Mes_Año'].unique().tolist(), reverse=True), key="hist_mes")
        filtro_movil  = h2.selectbox("🚛 Móvil", ["Todos"] + sorted(df_hist['Movil'].unique().tolist()), key="hist_movil")
        filtro_chofer = h3.selectbox("👤 Chofer", ["Todos"] + sorted(df_hist['Chofer'].dropna().unique().tolist()), key="hist_chofer")

        df_hist_f = df_hist.copy()
        if filtro_mes    != "Todos": df_hist_f = df_hist_f[df_hist_f['Mes_Año']  == filtro_mes]
        if filtro_movil  != "Todos": df_hist_f = df_hist_f[df_hist_f['Movil']    == int(filtro_movil)]
        if filtro_chofer != "Todos": df_hist_f = df_hist_f[df_hist_f['Chofer']   == filtro_chofer]

        df_hist_f = df_hist_f.sort_values("Fecha", ascending=False)
        df_hist_f['Fecha'] = df_hist_f['Fecha'].dt.strftime('%d/%m/%Y')
        df_hist_f = df_hist_f.drop(columns=['Mes_Año'], errors='ignore')

        st.caption(f"Mostrando {len(df_hist_f)} registros")
        st.dataframe(
            df_hist_f.style.map(
                lambda v: 'background-color: #421212; color: white'
                if isinstance(v, float) and v > UMBRAL else '',
                subset=["Consumo_L100"] if "Consumo_L100" in df_hist_f.columns else []
            ),
            use_container_width=True,
            column_config={
                "KM_Ini":    st.column_config.NumberColumn("KM Inicial",   format="%d"),
                "KM_Fin":    st.column_config.NumberColumn("KM Final",     format="%d"),
                "KM_Recorr": st.column_config.NumberColumn("KM Recorrido", format="%d"),
            }
        )

        csv_hist = df_hist_f.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Exportar filtrado (CSV)", csv_hist, "historial_flota.csv", "text/csv")

# ─────────────────────────────────────────────
# TAB: ASISTENTE IA
# FIX: objeto `model` correctamente definido arriba
# ─────────────────────────────────────────────
with TAB_IA:
    st.subheader("🤖 Asistente Inteligente")

    # Botones rápidos
    c1, c2, c3, c4 = st.columns(4)
    pregunta_rapida = None
    if c1.button("🥇 ¿Mejor Chofer?"):
        pregunta_rapida = "¿Quién ha sido el chofer más eficiente según los datos?"
    if c2.button("📊 ¿Móvil más gastador?"):
        pregunta_rapida = "¿Qué unidad (móvil) ha tenido el consumo de combustible más alto?"
    if c3.button("⚖️ ¿Comparar Rutas?"):
        pregunta_rapida = "Compara el consumo promedio entre 'Llano' y 'Alta Montaña'."
    if c4.button("🔍 Diagnóstico Mensual"):
        resumen = df_h.groupby('Movil')['Consumo_L100'].mean().to_string() if not df_h.empty else "Sin datos"
        pregunta_rapida = f"Analiza estos consumos por unidad: {resumen}. ¿Hay anomalías o se recomienda mantenimiento?"

    # Historial del chat
    for msg in st.session_state["messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    with st.form("ai_form", clear_on_submit=True):
        pregunta_input = st.text_input("¿Qué quieres saber?", key="input_ia")
        btn_enviar     = st.form_submit_button("Consultar IA")

    pregunta = pregunta_rapida if pregunta_rapida else pregunta_input

    if (btn_enviar or pregunta_rapida) and pregunta:
        if not model:
            st.error("⚠️ El Asistente IA no está configurado. Verificá la API key en Secrets.")
        else:
            ahora = time.time()
            if ahora - st.session_state["ultimo_call"] < 15:
                restante = int(15 - (ahora - st.session_state["ultimo_call"]))
                st.warning(f"⏳ Esperá {restante} segundos antes de la próxima consulta.")
            elif pregunta in st.session_state["ai_cache"]:
                st.info("💡 Respuesta recuperada del historial reciente.")
                resp_cache = st.session_state["ai_cache"][pregunta]
                with st.chat_message("assistant"):
                    st.markdown(resp_cache)
            else:
                st.session_state["messages"].append({"role": "user", "content": pregunta})
                with st.chat_message("user"):
                    st.markdown(pregunta)
                with st.chat_message("assistant"):
                    with st.spinner("Analizando..."):
                        try:
                            resumen_choferes = df_h.groupby('Chofer')['Consumo_L100'].mean().sort_values().to_string() if not df_h.empty else "Sin datos"
                            resumen_moviles  = df_h.groupby('Movil')['Consumo_L100'].mean().sort_values().to_string()  if not df_h.empty else "Sin datos"
                            avg_flota        = df_h['Consumo_L100'].mean() if not df_h.empty else 0

                            contexto = f"""
Sos el jefe de flota de una empresa de transporte en Jujuy, Argentina.
Respondé de forma crítica y concisa. Si hay consumos altos, recomendá mantenimiento.
El umbral de alerta es {UMBRAL:.0f} L/100km.

DATOS ACTUALES:
- Total registros: {len(df_h)}
- Consumo promedio flota: {avg_flota:.1f} L/100km
- Por chofer (L/100km):
{resumen_choferes}
- Por unidad (L/100km):
{resumen_moviles}
"""
                            response  = model.generate_content(f"{contexto}\nPregunta: {pregunta}")
                            respuesta = response.text
                            st.session_state["ai_cache"][pregunta]  = respuesta
                            st.session_state["ultimo_call"]         = time.time()
                            st.markdown(respuesta)
                            st.session_state["messages"].append({"role": "assistant", "content": respuesta})
                        except Exception as e:
                            st.error(f"⚠️ Error al consultar la IA: {e}")

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
            fig_line.add_hline(
                y=UMBRAL, line_dash="dot", line_color="red",
                annotation_text=f"Umbral ({UMBRAL:.0f} L/100)", annotation_position="top left"
            )
            fig_line.update_layout(hovermode="x unified")
            st.plotly_chart(fig_line, use_container_width=True)
            st.info("💡 Línea blanca = promedio flota. Línea roja = umbral de alerta.")
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

        mes_actual    = pd.Timestamp.today().to_period('M').strftime('%Y-%m')
        mes_ant       = (pd.Timestamp.today() - pd.DateOffset(months=1)).to_period('M').strftime('%Y-%m')
        df_mes_act    = df_cos[df_cos['Mes'] == mes_actual]
        df_mes_ant    = df_cos[df_cos['Mes'] == mes_ant]

        costo_actual  = df_mes_act['Costo_Total_ARS'].sum()
        costo_ant     = df_mes_ant['Costo_Total_ARS'].sum()
        delta_costo   = costo_actual - costo_ant
        litros_actual = df_mes_act['L_Ticket'].sum()
        km_actual     = df_mes_act['KM_Recorr'].sum() if 'KM_Recorr' in df_mes_act.columns else 0
        costo_x_km    = (costo_actual / km_actual) if km_actual > 0 else 0

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("💰 Costo mes actual",  f"${costo_actual:,.0f}", delta=f"${delta_costo:,.0f} vs mes ant.")
        m2.metric("⛽ Litros mes actual", f"{litros_actual:,.0f} L")
        m3.metric("📏 KM mes actual",     f"{km_actual:,.0f} km")
        m4.metric("💵 Costo por KM",      f"${costo_x_km:,.1f}/km")
        st.divider()

        st.markdown("### 📅 Gasto mensual")
        df_mensual = df_cos.groupby('Mes').agg(
            Costo_Total=('Costo_Total_ARS', 'sum'),
            Litros=('L_Ticket', 'sum'),
            Viajes=('Fecha', 'count')
        ).reset_index().sort_values('Mes')
        fig_cos = px.bar(df_mensual, x='Mes', y='Costo_Total', text_auto='.2s',
                         template='plotly_dark', labels={'Costo_Total': 'Costo ARS'},
                         title='Gasto total por mes')
        st.plotly_chart(fig_cos, use_container_width=True)

        st.markdown("### 🔮 Proyección del mes en curso")
        hoy        = pd.Timestamp.today()
        dias_trans = hoy.day
        dias_mes   = hoy.days_in_month
        proyeccion = (costo_actual / dias_trans * dias_mes) if dias_trans > 0 else 0
        col_p1, col_p2 = st.columns(2)
        col_p1.metric("📈 Proyección de cierre", f"${proyeccion:,.0f}")
        col_p2.metric("📆 Días transcurridos",   f"{dias_trans} / {dias_mes}")

        st.markdown("### 🚛 Costo acumulado por unidad")
        df_x_movil = df_cos.groupby('Movil')['Costo_Total_ARS'].sum().reset_index().sort_values('Costo_Total_ARS', ascending=False)
        fig_movil  = px.bar(df_x_movil, x='Movil', y='Costo_Total_ARS', text_auto='.2s',
                            template='plotly_dark', title='Costo total por unidad')
        st.plotly_chart(fig_movil, use_container_width=True)

        st.markdown("### 👤 Top 10 choferes por costo")
        df_x_chof = df_cos.groupby('Chofer')['Costo_Total_ARS'].sum().reset_index().sort_values('Costo_Total_ARS', ascending=False).head(10)
        fig_chof  = px.bar(df_x_chof, x='Chofer', y='Costo_Total_ARS', text_auto='.2s',
                           template='plotly_dark', title='Top 10 choferes por costo acumulado')
        st.plotly_chart(fig_chof, use_container_width=True)

# ─────────────────────────────────────────────
# TAB: REPORTE PDF
# FIX: usa st.session_state["umbral_consumo"] en lugar de variable UMBRAL no definida
# ─────────────────────────────────────────────
with TAB_PDF:
    st.subheader("📄 Generar Reporte PDF Mensual")
    if df_h.empty:
        st.info("Sin datos para generar el reporte.")
    else:
        df_pdf_base = df_h.copy()
        df_pdf_base['Fecha'] = pd.to_datetime(df_pdf_base['Fecha'], errors='coerce')
        df_pdf_base['Mes']   = df_pdf_base['Fecha'].dt.to_period('M').astype(str)

        meses_disp = sorted(df_pdf_base['Mes'].unique().tolist(), reverse=True)
        mes_pdf    = st.selectbox("📅 Seleccioná el mes para el reporte", meses_disp)

        if st.button("🖨️ Generar PDF", use_container_width=True):
            df_mes = df_pdf_base[df_pdf_base['Mes'] == mes_pdf].copy()
            if df_mes.empty:
                st.warning("No hay datos para ese mes.")
            else:
                with st.spinner("Generando reporte PDF..."):
                    buf      = io.BytesIO()
                    doc      = SimpleDocTemplate(buf, pagesize=landscape(A4),
                                                 rightMargin=1.5*cm, leftMargin=1.5*cm,
                                                 topMargin=1.5*cm, bottomMargin=1.5*cm)
                    styles   = getSampleStyleSheet()
                    story    = []
                    tmpfiles = []

                    title_style = ParagraphStyle('title', parent=styles['Title'],   fontSize=18, spaceAfter=6,  alignment=TA_CENTER)
                    h2_style    = ParagraphStyle('h2',    parent=styles['Heading2'], fontSize=13, spaceAfter=4,  spaceBefore=12)
                    body_style  = ParagraphStyle('body',  parent=styles['Normal'],   fontSize=9,  spaceAfter=4)

                    # Portada
                    story.append(Paragraph("🚚 Inteligencia de Flota — Jujuy", title_style))
                    story.append(Paragraph(f"Reporte mensual: {mes_pdf}", styles['Heading3']))
                    story.append(Paragraph(f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')}", body_style))
                    story.append(Spacer(1, 0.4*cm))

                    # Resumen ejecutivo
                    story.append(Paragraph("📊 Resumen Ejecutivo", h2_style))
                    total_viajes = len(df_mes)
                    total_km     = df_mes['KM_Recorr'].sum() if 'KM_Recorr' in df_mes.columns else 0
                    total_litros = df_mes['L_Ticket'].sum()
                    total_costo  = df_mes['Costo_Total_ARS'].sum()
                    avg_cons     = df_mes['Consumo_L100'].mean()
                    alertas_mes  = len(df_mes[df_mes['Consumo_L100'] > UMBRAL])

                    resumen_data = [
                        ['Métrica', 'Valor'],
                        ['Total de viajes',              str(total_viajes)],
                        ['KM totales recorridos',        f"{total_km:,.0f} km"],
                        ['Litros consumidos',            f"{total_litros:,.1f} L"],
                        ['Costo total',                  f"${total_costo:,.0f} ARS"],
                        ['Consumo promedio',             f"{avg_cons:.2f} L/100km"],
                        [f'Alertas (>{UMBRAL:.0f} L/100km)', str(alertas_mes)],
                    ]
                    t_res = Table(resumen_data, colWidths=[8*cm, 8*cm])
                    t_res.setStyle(TableStyle([
                        ('BACKGROUND',    (0,0), (-1,0), colors.HexColor('#1e3a5f')),
                        ('TEXTCOLOR',     (0,0), (-1,0), colors.white),
                        ('FONTNAME',      (0,0), (-1,0), 'Helvetica-Bold'),
                        ('FONTSIZE',      (0,0), (-1,-1), 9),
                        ('ROWBACKGROUNDS',(0,1), (-1,-1), [colors.whitesmoke, colors.white]),
                        ('GRID',          (0,0), (-1,-1), 0.3, colors.grey),
                        ('ALIGN',         (0,0), (-1,-1), 'LEFT'),
                        ('LEFTPADDING',   (0,0), (-1,-1), 8),
                    ]))
                    story.append(t_res)
                    story.append(Spacer(1, 0.5*cm))

                    # Gráfico 1: Consumo por chofer
                    story.append(Paragraph("📈 Consumo Promedio por Chofer (L/100km)", h2_style))
                    df_g1      = df_mes.groupby('Chofer')['Consumo_L100'].mean().sort_values(ascending=True)
                    fig1, ax1  = plt.subplots(figsize=(10, max(3, len(df_g1) * 0.4)))
                    bar_colors = ['#FF4B4B' if v > UMBRAL else '#4CAF50' for v in df_g1.values]
                    ax1.barh(df_g1.index, df_g1.values, color=bar_colors)
                    ax1.axvline(UMBRAL, color='orange', linestyle='--', label=f'Umbral {UMBRAL:.0f}')
                    ax1.set_xlabel('L/100km')
                    ax1.legend()
                    ax1.set_facecolor('#1e2130')
                    fig1.patch.set_facecolor('#1e2130')
                    ax1.tick_params(colors='white')
                    ax1.xaxis.label.set_color('white')
                    for spine in ax1.spines.values(): spine.set_edgecolor('#444')
                    plt.tight_layout()
                    tmp1 = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
                    tmpfiles.append(tmp1.name)
                    fig1.savefig(tmp1.name, dpi=120, bbox_inches='tight', facecolor='#1e2130')
                    plt.close(fig1)
                    story.append(RLImage(tmp1.name, width=22*cm, height=max(5*cm, len(df_g1)*0.8*cm)))
                    story.append(Spacer(1, 0.5*cm))

                    # Gráfico 2: Costo por unidad
                    story.append(Paragraph("💰 Costo Total por Unidad (ARS)", h2_style))
                    df_g2     = df_mes.groupby('Movil')['Costo_Total_ARS'].sum().sort_values(ascending=False).head(15)
                    fig2, ax2 = plt.subplots(figsize=(10, 4))
                    ax2.bar([f"C{int(m)}" for m in df_g2.index], df_g2.values, color='#4a90e2')
                    ax2.set_ylabel('ARS')
                    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'${x:,.0f}'))
                    ax2.set_facecolor('#1e2130')
                    fig2.patch.set_facecolor('#1e2130')
                    ax2.tick_params(colors='white', axis='both')
                    ax2.yaxis.label.set_color('white')
                    for spine in ax2.spines.values(): spine.set_edgecolor('#444')
                    plt.xticks(rotation=45)
                    plt.tight_layout()
                    tmp2 = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
                    tmpfiles.append(tmp2.name)
                    fig2.savefig(tmp2.name, dpi=120, bbox_inches='tight', facecolor='#1e2130')
                    plt.close(fig2)
                    story.append(RLImage(tmp2.name, width=22*cm, height=7*cm))
                    story.append(Spacer(1, 0.5*cm))

                    # Tabla de datos
                    story.append(Paragraph("📋 Detalle de Registros del Mes", h2_style))
                    cols_tabla = ['Fecha', 'Chofer', 'Movil', 'Marca', 'Ruta',
                                  'KM_Recorr', 'L_Ticket', 'Consumo_L100', 'Costo_Total_ARS', 'Desvio_Neto']
                    cols_tabla = [c for c in cols_tabla if c in df_mes.columns]
                    df_tabla   = df_mes[cols_tabla].copy()
                    df_tabla['Fecha'] = df_tabla['Fecha'].dt.strftime('%d/%m/%Y')

                    headers    = ['Fecha','Chofer','Móvil','Marca','Ruta',
                                  'KM','Litros','L/100','Costo $','Desvío'][:len(cols_tabla)]
                    tabla_data = [headers]
                    for _, row in df_tabla.iterrows():
                        fila = []
                        for c in cols_tabla:
                            v = row[c]
                            fila.append(f"{v:.1f}" if isinstance(v, float) else str(v))
                        tabla_data.append(fila)

                    col_w  = [2.5*cm,4*cm,1.5*cm,3*cm,2*cm,2*cm,2*cm,2*cm,3*cm,2*cm][:len(cols_tabla)]
                    t_data = Table(tabla_data, colWidths=col_w, repeatRows=1)

                    row_styles = [
                        ('BACKGROUND',     (0,0), (-1,0),  colors.HexColor('#1e3a5f')),
                        ('TEXTCOLOR',      (0,0), (-1,0),  colors.white),
                        ('FONTNAME',       (0,0), (-1,0),  'Helvetica-Bold'),
                        ('FONTSIZE',       (0,0), (-1,-1), 7),
                        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.whitesmoke, colors.white]),
                        ('GRID',           (0,0), (-1,-1), 0.2, colors.grey),
                        ('ALIGN',          (0,0), (-1,-1), 'CENTER'),
                    ]
                    if 'Consumo_L100' in cols_tabla:
                        ci = cols_tabla.index('Consumo_L100')
                        for ri, row in enumerate(df_tabla.itertuples(), start=1):
                            if getattr(row, 'Consumo_L100', 0) > UMBRAL:
                                row_styles.append(('BACKGROUND', (ci,ri), (ci,ri), colors.HexColor('#421212')))
                                row_styles.append(('TEXTCOLOR',  (ci,ri), (ci,ri), colors.HexColor('#FF4B4B')))
                    t_data.setStyle(TableStyle(row_styles))
                    story.append(t_data)

                    doc.build(story)
                    for f in tmpfiles:
                        try: os.unlink(f)
                        except: pass

                    buf.seek(0)
                    st.success("✅ PDF generado correctamente.")
                    st.download_button(
                        label="📥 Descargar Reporte PDF",
                        data=buf,
                        file_name=f"reporte_flota_{mes_pdf}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
