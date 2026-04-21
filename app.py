import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime
import time
import os
import google.generativeai as genai

# --- CSS PARA OPTIMIZACIÓN MÓVIL ---
st.markdown("""
    <style>
    @media only screen and (max-width: 600px) {
        .stMetric { background-color: #f0f2f6; padding: 10px; border-radius: 10px; margin-bottom: 10px; }
        [data-testid="stMetricValue"] { font-size: 20px !important; }
        div.stButton > button { width: 100%; height: 50px; font-size: 16px; }
        .stForm { padding: 10px !important; }
    }
    .metric-card { background: #1e1e1e; padding: 15px; border-radius: 10px; border-left: 4px solid #4a90e2; margin-bottom: 10px; text-align: center; }
    .driver-name { font-weight: bold; font-size: 14px; }
    .driver-score { font-size: 20px; color: #4a90e2; }
    .desvio-item { padding: 12px; border-radius: 8px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #3d425a; transition: transform 0.2s; }
    .desvio-critico { background: #421212 !important; border: 1px solid #FF4B4B !important; }
    </style>
""", unsafe_allow_html=True)

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Inteligencia de Flota Jujuy", layout="wide")

# Configuración IA
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"].strip().strip('"'))
    model = genai.GenerativeModel('gemini-2.0-flash')
else:
    model = None

# --- 2. LOGIN ---
if "auth" not in st.session_state:
    st.title("🚚 Sistema de Control de Flota")
    _, col_log, _ = st.columns([1, 2, 1])
    with col_log:
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.button("Ingresar"):
            if u == "ema_admin" and p == "jujuy2024":
                st.session_state["auth"] = True
                st.rerun()
            else: st.error("Clave incorrecta")
    st.stop()

# --- 3. CARGA DE DATOS ---
conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1PEH7lbtoq_oAHwom0O5YYYskFm6ALJ6LCj1FfQKzpmQ/edit?gid=0#gid=0"

if "precio_gasoil" not in st.session_state:
    st.session_state["precio_gasoil"] = 2065.0

@st.cache_data(ttl=600)
def cargar_lista_choferes():
    try:
        df_c = pd.read_excel("choferes.xlsx")
        return sorted(df_c.iloc[:, 0].dropna().unique().tolist())
    except: return []

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
lista_personal = cargar_lista_choferes()
if not lista_personal and not df_h.empty:
    lista_personal = sorted(df_h["Chofer"].unique().tolist())

# --- 4. INTERFAZ PRINCIPAL ---
st.title("🚚 Inteligencia de Flota y Costos")
tabs = st.tabs(["📝 Registro", "👁️ Ojo de Halcón", "📜 Historial", "🤖 IA", "📈 Analítica"])

# TAB 0: REGISTRO
with tabs[0]:
    st.subheader("📝 Nuevo Registro")
    with st.container(border=True):
        col_m1, col_m2 = st.columns([1, 2])
        with col_m1:
            movil_sel = st.selectbox("🔢 Móvil", list(range(1, 101)), index=35, key="movil_dinamico")
        
        # Sugerencias
        km_sugerido = 0.0
        idx_marca = 0
        idx_chofer = 0
        marcas_disponibles = ["SCANIA", "MERCEDES BENZ"]
        if not df_h.empty:
            ult_m = df_h[df_h["Movil"] == movil_sel]
            if not ult_m.empty:
                km_sugerido = float(ult_m.sort_values("Fecha").iloc[-1]["KM_Fin"])
                marca_hist = ult_m.sort_values("Fecha").iloc[-1]["Marca"]
                if marca_hist in marcas_disponibles: idx_marca = marcas_disponibles.index(marca_hist)
                chofer_hist = ult_m.sort_values("Fecha").iloc[-1]["Chofer"]
                if chofer_hist in lista_personal: idx_chofer = lista_personal.index(chofer_hist)

        with st.form("registro_form_v2", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                marca = st.radio("🏷️ Marca", marcas_disponibles, index=idx_marca, horizontal=True)
                chofer = st.selectbox("👤 Chofer", options=lista_personal, index=idx_chofer)
                precio_comb = st.number_input("💰 Precio Litro Gasoil", value=float(st.session_state["precio_gasoil"]))
                fecha_input = st.date_input("📅 Fecha de Carga", datetime.now())
            with c2:
                ruta_tipo = st.radio("🏔️ Tipo de Ruta", ["Llano", "Alta Montaña"], horizontal=True)
                traza_ex = ["➕ NUEVA"] + (sorted(df_h["Traza"].dropna().astype(str).unique().tolist()) if not df_h.empty and "Traza" in df_h.columns else [])
                traza_sel = st.selectbox("🗺️ Traza", traza_ex)
                nt = st.text_input("✍️ Nombre Nueva Traza").upper()
                t_final = nt if (traza_sel == "➕ NUEVA") else traza_sel
            with c3:
                kmi = st.number_input("🛣️ KM Inicial", value=int(km_sugerido), step=1, format="%d")
                kmf = st.number_input("🏁 KM Final", value=0, step=1, format="%d")
                lt = st.number_input("⛽ Litros Ticket", value=0.0)
                ltab = st.number_input("📟 Litros Tablero", value=0.0)
                lral = st.number_input("⏳ Litros Ralentí", value=0.0)
            
            submit_button = st.form_submit_button("💾 GUARDAR REGISTRO", use_container_width=True)

    if submit_button:
        # Validación y Guardado
        if kmf <= kmi: st.error("⚠️ Error: KM Final <= KM Inicial"); st.stop()
        if lt <= 0: st.error("⚠️ Error: Ingresa Litros de Ticket"); st.stop()
        
        dist_final = int(kmf - kmi)
        cons_final = round((lt / dist_final * 100), 2) if dist_final > 0 else 0
        nuevo_reg = {
            "Fecha": fecha_input.strftime('%d/%m/%Y'), "Chofer": chofer, "Movil": movil_sel, "Marca": marca,
            "Ruta": ruta_tipo, "Traza": t_final, "KM_Ini": kmi, "KM_Fin": kmf, "KM_Recorr": dist_final,
            "L_Ticket": lt, "L_Tablero": ltab, "L_Ralenti": lral, "Consumo_L100": cons_final,
            "Costo_Total_ARS": round(lt * precio_comb, 2), "Desvio_Neto": round(lt - (ltab + lral), 2)
        }
        with st.spinner("Guardando..."):
            df_final = pd.concat([df_h, pd.DataFrame([nuevo_reg])], ignore_index=True)
            conn.update(spreadsheet=URL, data=df_final)
            st.success("✅ Guardado."); time.sleep(1); st.rerun()

# TAB 1: OJO DE HALCÓN
with tabs[1]:
    if not df_h.empty:
        df_ana = df_h.copy()
        df_ana['Mes_Año'] = df_ana['Fecha'].dt.to_period('M').astype(str)
        mes_sel = st.selectbox("📅 Mes", ["Todos"] + sorted(df_ana['Mes_Año'].unique().tolist(), reverse=True))
        df_filtrado = df_ana if mes_sel == "Todos" else df_ana[df_ana['Mes_Año'] == mes_sel]
        
        st.subheader("🏆 Ranking Eficiencia")
        top_5 = df_filtrado.groupby("Chofer")["Consumo_L100"].mean().nsmallest(5).reset_index()
        cols = st.columns(5)
        for i, row in top_5.iterrows():
            with cols[i]: st.markdown(f'<div class="metric-card">{row["Chofer"]}<br><b>{row["Consumo_L100"]:.1f}</b></div>', unsafe_allow_html=True)

# TAB 2: HISTORIAL
with tabs[2]:
    if not df_h.empty:
        df_v = df_h.copy().sort_values("Fecha", ascending=False)
        df_v['Fecha'] = df_v['Fecha'].dt.strftime('%d/%m/%Y')
        st.dataframe(df_v, use_container_width=True)

# TAB 3: ASISTENTE IA
with tabs[3]:
    st.subheader("🤖 Asistente Inteligente")
    if "messages" not in st.session_state: st.session_state.messages = []
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])
    
    if prompt := st.chat_input("Consulta a la IA..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        with st.chat_message("assistant"):
            if model:
                resp = model.generate_content(f"Jefe de flota, analiza: {prompt} con estos datos: {df_h.head(20).to_string()}")
                st.markdown(resp.text)
                st.session_state.messages.append({"role": "assistant", "content": resp.text})
            else: st.error("IA no disponible")

# TAB 4: ANALÍTICA
with tabs[4]:
    st.subheader("📈 Analítica")
    if not df_h.empty:
        df_ana = df_h.copy()
        moviles = st.multiselect("Seleccionar Móviles", sorted(df_ana['Movil'].unique()), default=[df_ana['Movil'].iloc[0]])
        df_line = df_ana[df_ana['Movil'].isin(moviles)].groupby(['Fecha', 'Movil'])['Consumo_L100'].mean().reset_index()
        st.plotly_chart(px.line(df_line, x="Fecha", y="Consumo_L100", color="Movil", template="plotly_dark"), use_container_width=True)
