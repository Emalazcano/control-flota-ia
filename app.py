import streamlit as st 
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime
import time
import google.generativeai as genai

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Inteligencia de Flota Jujuy", layout="wide")

# --- CONFIGURACIÓN DE IA GEMINI ---
# Mejoramos la carga de la key para evitar errores
if "GOOGLE_API_KEY" in st.secrets:
    api_key_final = st.secrets["GOOGLE_API_KEY"].strip()
    genai.configure(api_key=api_key_final)
    # Usamos gemini-2.0-flash que es rápido y eficiente
    model = genai.GenerativeModel('gemini-2.0-flash')
else:
    st.warning("⚠️ Clave API no detectada en Secrets.")
    model = None

# CSS personalizado
st.markdown("""
    <style>
    .metric-card { background-color: #1e2130; padding: 15px; border-radius: 12px; border: 1px solid #3d425a; text-align: center; }
    .driver-name { font-weight: bold; font-size: 16px; margin: 5px 0; color: white; }
    .driver-score { font-size: 24px; color: #4CAF50; font-weight: bold; }
    .medal-icon { font-size: 32px; margin-bottom: 5px; }
    .desvio-item { padding: 12px; border-radius: 8px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #3d425a; }
    .desvio-critico { background: #421212 !important; border: 1px solid #FF4B4B !important; }
    </style>
""", unsafe_allow_html=True)

# --- 2. LOGIN ---
if "auth" not in st.session_state:
    st.title("🚚 Sistema de Control de Flota")
    _, col_log, _ = st.columns([1, 2, 1])
    with col_log:
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.button("Ingresar", use_container_width=True):
            if u == "ema_admin" and p == "jujuy2024":
                st.session_state["auth"] = True
                st.rerun()
            else: st.error("Clave incorrecta")
    st.stop()

# --- 3. CONEXIÓN Y DATOS ---
conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1PEH7lbtoq_oAHwom0O5YYYskFm6ALJ6LCj1FfQKzpmQ/edit?gid=0#gid=0"

@st.cache_data(ttl=600)
def cargar_historial():
    try:
        df = conn.read(spreadsheet=URL, ttl=0)
        num_cols = ["Movil", "KM_Fin", "KM_Ini", "L_Ticket", "L_Tablero", "L_Ralenti", "Desvio_Neto", "Consumo_L100", "Costo_Total_ARS"]
        for col in num_cols:
            if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        if 'Fecha' in df.columns:
            df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=True, errors='coerce').fillna(pd.Timestamp.now())
        return df
    except Exception as e:
        st.error(f"Error al cargar datos: {e}")
        return pd.DataFrame()

df_h = cargar_historial()

# --- 4. INTERFAZ ---
st.title("🚚 Inteligencia de Flota y Costos")
tabs = st.tabs(["⛽ Registro de Carga", "🦅 Ojo de Halcón", "📜 Historial", "🤖 Asistente IA"])

# --- TAB 0: REGISTRO (Simplificado para brevedad) ---
with tabs[0]:
    st.subheader("📝 Nuevo Registro")
    # (Mantener lógica de formulario original)
    # ... (Tu lógica existente aquí) ...

# --- TAB 1: OJO DE HALCÓN ---
with tabs[1]:
    if not df_h.empty:
        df_ana = df_h.copy()
        df_ana['Mes_Año'] = df_ana['Fecha'].dt.to_period('M').astype(str)
        c_f1, c_f2 = st.columns(2)
        mes_sel = c_f1.selectbox("📅 Mes", ["Todos"] + sorted(df_ana['Mes_Año'].unique().tolist(), reverse=True))
        ruta_sel = c_f2.multiselect("🏔️ Ruta", df_ana['Ruta'].unique(), default=df_ana['Ruta'].unique())
        df_filtrado = df_ana[df_ana['Ruta'].isin(ruta_sel)]
        if mes_sel != "Todos": df_filtrado = df_filtrado[df_filtrado['Mes_Año'] == mes_sel]

        # Ranking de Desvíos
        st.subheader("⚠️ Ranking de Desvíos (>50L)")
        df_desv = df_filtrado.groupby("Chofer")["Desvio_Neto"].sum().reset_index()
        df_desv = df_desv[df_desv['Desvio_Neto'] > 50].sort_values("Desvio_Neto", ascending=False)
        
        if df_desv.empty: st.info("✅ Sin desvíos críticos.")
        else:
            for _, row in df_desv.iterrows():
                st.markdown(f'<div class="desvio-item desvio-critico"><div><b>{row["Chofer"]}</b><br><small>🚨 Crítico (>50L)</small></div><b>{row["Desvio_Neto"]:.1f} L</b></div>', unsafe_allow_html=True)

# --- TAB 3: ASISTENTE IA (OPTIMIZADO) ---
with tabs[3]:
    st.subheader("🤖 Consultas con IA")
    
    # Inicializar historial en sesión
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Mostrar historial
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Formulario para evitar consultas automáticas
    with st.form("ai_form", clear_on_submit=True):
        pregunta = st.text_input("¿Qué quieres saber sobre la flota?", key="input_ia")
        btn_enviar = st.form_submit_button("Consultar IA")

    if btn_enviar and pregunta and model:
        st.session_state.messages.append({"role": "user", "content": pregunta})
        with st.chat_message("user"): st.markdown(pregunta)
        
        with st.chat_message("assistant"):
            with st.spinner("Analizando..."):
                # Generar contexto resumido
                ctx = f"Eres experto en Flota Jujuy. Datos: {df_h.groupby('Chofer')['Consumo_L100'].mean().head(5).to_string()}"
                try:
                    response = model.generate_content(f"{ctx}\nPregunta: {pregunta}")
                    res_text = response.text
                    st.markdown(res_text)
                    st.session_state.messages.append({"role": "assistant", "content": res_text})
                except Exception as e:
                    st.error("⚠️ Cuota excedida. Espera un minuto o intenta una consulta más corta.")
