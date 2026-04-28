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
    /* Ocultar botones de +/- */
    [data-testid="stNumberInput"] button { display: none; }
    @media only screen and (max-width: 600px) {
        .stMetric { background-color: #f0f2f6; padding: 10px; border-radius: 10px; margin-bottom: 10px; }
        [data-testid="stMetricValue"] { font-size: 20px !important; }
        div.stButton > button { width: 100%; height: 50px; font-size: 16px; }
        .stForm { padding: 10px !important; }
        [data-testid="column"] { min-width: 100% !important; }
    }
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
        border: 1px solid #3d425a; transition: transform 0.2s;
    }
    .desvio-item:hover { transform: scale(1.02); }
    .desvio-critico { background: #421212 !important; border: 1px solid #FF4B4B !important; }
    .desvio-ok      { background: #0c2b18 !important; border: 1px solid #00CC96 !important; }
    .alert-banner {
        background: #421212; border: 1px solid #FF4B4B; border-radius: 10px;
        padding: 14px 18px; margin-bottom: 10px; color: white; font-size: 15px;
    }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 2. CONFIGURACIÓN IA GEMINI
# ─────────────────────────────────────────────
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    model = genai.GenerativeModel('gemini-2.0-flash-lite')
else:
    st.error("⚠️ Configura tu GOOGLE_API_KEY en los secretos.")

# ─────────────────────────────────────────────
# 3. USUARIOS Y LOGIN
# ─────────────────────────────────────────────
USUARIOS = {
    "ema_admin":    {"pass": "jujuy2024",  "rol": "admin"},
    "visualizador": {"pass": "ver2024",    "rol": "visualizador"},
}

if "auth" not in st.session_state:
    st.title("🚚 Sistema de Control de Flota")
    _, col_log, _ = st.columns([1, 2, 1])
    with col_log:
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.button("Ingresar", use_container_width=True):
            if u in USUARIOS and USUARIOS[u]["pass"] == p:
                st.session_state["auth"] = True
                st.session_state["usuario"] = u
                st.session_state["rol"] = USUARIOS[u]["rol"]
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

if "precio_gasoil" not in st.session_state: st.session_state["precio_gasoil"] = 2065.0
if "umbral_consumo" not in st.session_state: st.session_state["umbral_consumo"] = 35.0

# ─────────────────────────────────────────────
# 5. FUNCIONES DE DATOS
# ─────────────────────────────────────────────
@st.cache_data(ttl=600)
def cargar_lista_choferes():
    try:
        df_c = pd.read_excel("choferes.xlsx")
        return sorted(df_c.iloc[:, 0].dropna().unique().tolist())
    except: return []

def cargar_historial():
    try:
        df = conn.read(spreadsheet=URL, ttl=0)
        cols_int = ["Movil", "KM_Ini", "KM_Fin", "KM_Recorr", "L_Ralenti", "L_Ticket", "L_Tablero", "Desvio_Neto"]
        cols_float = ["Consumo_L100", "Costo_Total_ARS", "Costo_Ralenti_ARS"]
        for col in cols_int:
            if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
        for col in cols_float:
            if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        if 'Fecha' in df.columns: df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=True, errors='coerce')
    except Exception as e:
        st.error(f"Error al cargar datos: {e}")
        df = pd.DataFrame() 
    return df

# ─────────────────────────────────────────────
# 6. CARGA INICIAL
# ─────────────────────────────────────────────
df_h = cargar_historial()
lista_personal = cargar_lista_choferes()

if not lista_personal and not df_h.empty:
    lista_personal = sorted(df_h["Chofer"].dropna().unique().tolist())
elif not lista_personal:
    lista_personal = ["NUEVO"]

# ─────────────────────────────────────────────
# 7. SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"👤 **{st.session_state.get('usuario','?')}** ({ROL})")
    if st.button("🚪 Cerrar sesión", use_container_width=True):
        for k in list(st.session_state.keys()): del st.session_state[k]
        st.rerun()
    st.divider()
    st.markdown("### ⚙️ Configuración")
    st.session_state["umbral_consumo"] = st.number_input("🚨 Umbral consumo (L/100km)", value=st.session_state["umbral_consumo"], step=1.0)
    st.session_state["precio_gasoil"] = st.number_input("💰 Precio gasoil ($/L)", value=st.session_state["precio_gasoil"], step=10.0)

UMBRAL = st.session_state["umbral_consumo"]

# ─────────────────────────────────────────────
# 8. TÍTULO Y TABS
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
# TAB: REGISTRO (SOLO ADMIN)
# ─────────────────────────────────────────────
if TAB_REG:
    with TAB_REG:
        st.subheader("📝 Nuevo Registro")

        # Lógica de carga
        movil_sel = st.selectbox("🔢 Selecciona Móvil", list(range(1, 101)), index=34, key="m_sel")
        
        idx_marca, idx_chofer, km_sugerido = 0, 0, 0
        traza_ex = ["➕ NUEVA"]

        if not df_h.empty:
            hist_movil = df_h[df_h["Movil"] == int(movil_sel)]
            if not hist_movil.empty:
                ult_r = hist_movil.sort_values("Fecha").iloc[-1]
                km_sugerido = float(ult_r["KM_Fin"])
                if ult_r["Chofer"] in lista_personal: idx_chofer = lista_personal.index(ult_r["Chofer"])
                if ult_r["Marca"] == "MERCEDES BENZ": idx_marca = 1
                traza_ex = ["➕ NUEVA"] + sorted(df_h["Traza"].unique().tolist())

        # FORMULARIO
        with st.form("registro_form_v2", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                marca = st.radio("🏷️ Marca", ["SCANIA", "MERCEDES BENZ"], index=idx_marca, horizontal=True)
                chofer = st.selectbox("👤 Chofer", options=lista_personal, index=idx_chofer)
                fecha = st.date_input("📅 Fecha", datetime.now())
            with c2:
                tipo_ruta = st.radio("🏔️ Tipo", ["Llano", "Alta Montaña"], horizontal=True)
                traza = st.selectbox("🗺️ Traza", traza_ex)
                nt = st.text_input("✍️ Nueva Traza").upper()
            with c3:
                kmi = st.number_input("🛣️ KM Inicial", value=int(km_sugerido))
                kmf = st.number_input("🏁 KM Final", value=0)
                lt = st.number_input("⛽ Litros Totales", value=0.0, step=0.1)

            # METRICAS TEMPORALES (Recuperadas)
            dist_c = max(0, int(kmf - kmi))
            cons_c = (lt / dist_c * 100) if dist_c > 0 else 0.0
            costo_c = lt * st.session_state["precio_gasoil"]
            desvio_c = max(0, cons_c - UMBRAL)

            c_met1, c_met2, c_met3, c_met4 = st.columns(4)
            c_met1.metric("🛣️ KM", f"{dist_c:,.0f}")
            c_met2.metric("🔢 Cons", f"{cons_c:.1f}")
            c_met3.metric("💰 Costo", f"${costo_c:,.0f}")
            c_met4.metric("🚨 Desvío", f"{desvio_c:.1f}")

            submit = st.form_submit_button("💾 GUARDAR", use_container_width=True)

        if submit:
            st.success("✅ Datos procesados (simulación).")
            st.rerun()

# ─────────────────────────────────────────────
# RESTO DE TABS (Ojo de Halcón, Analítica, etc)
# ─────────────────────────────────────────────
with TAB_HALCON:
    st.write("Panel Ojo de Halcón...")
    # ... (El resto de tu lógica de las otras pestañas) ...
