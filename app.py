import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime
import time
import os

# --- 1. CONFIGURACIÓN Y ESTILOS (AQUÍ ESTÁ LA MAGIA VISUAL) ---
st.set_page_config(page_title="Inteligencia de Flota Jujuy", layout="wide")

# CSS para que las tarjetas y rankings se vean profesionales
st.markdown("""
    <style>
    /* Estilo para las medallas de eficiencia */
    .metric-card { 
        background-color: #1e2130; 
        padding: 20px; 
        border-radius: 15px; 
        border: 1px solid #3d425a; 
        text-align: center;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.3);
    }
    .driver-name { font-weight: bold; font-size: 16px; color: #aab; margin-bottom: 5px; }
    .driver-score { font-size: 28px; color: #4CAF50; font-weight: bold; }
    
    /* Estilo para la lista de desvíos */
    .desvio-item { 
        padding: 15px; 
        border-radius: 10px; 
        margin-bottom: 10px; 
        display: flex; 
        justify-content: space-between; 
        align-items: center; 
        border: 1px solid #3d425a;
        background-color: #1e2130;
    }
    .desvio-critico { 
        background-color: #421212 !important; 
        border-color: #FF4B4B !important; 
    }
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
            else: 
                st.error("Clave incorrecta")
    st.stop()

# --- 3. CONEXIÓN Y CARGA ---
conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1PEH7lbtoq_oAHwom0O5YYYskFm6ALJ6LCj1FfQKzpmQ/edit?gid=0#gid=0"

if "precio_gasoil" not in st.session_state:
    st.session_state["precio_gasoil"] = 2065.0

if "form_reset_key" not in st.session_state:
    st.session_state["form_reset_key"] = 0

def cargar_historial():
    try:
        df = conn.read(spreadsheet=URL, ttl=0)
        num_cols = ["Movil", "KM_Fin", "KM_Ini", "L_Ticket", "L_Tablero", "L_Ralenti", "Desvio_Neto", "Consumo_L100", "Costo_Total_ARS"]
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        if 'Fecha' in df.columns:
            df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce', dayfirst=True)
            df['Fecha'] = df['Fecha'].dt.normalize()
        return df
    except Exception as e:
        st.error(f"Error: {e}")
        return pd.DataFrame()

df_h = cargar_historial()

# --- 4. INTERFAZ ---
st.title("🚚 Inteligencia de Flota y Costos")
tabs = st.tabs(["⛽ Registro de Carga", "🦅 Ojo de Halcón (IA)", "📜 Historial"])

# --- TAB 1: REGISTRO ---
with tabs[0]:
    st.subheader("📝 Nuevo Registro")
    movil_sel = st.selectbox("🔢 Móvil", list(range(1, 101)), index=36)
    
    with st.form(key=f"registro_form_{st.session_state['form_reset_key']}"):
        c1, c2, c3 = st.columns(3)
        with c1:
            marca = st.radio("🏷️ Marca", ["SCANIA", "MERCEDES BENZ"], horizontal=True)
            chofer = st.selectbox("👤 Chofer", ["ADELMO JORGE", "BENITEZ DIEGO", "GONZALEZ FABIAN", "VALENTIN ARIEL", "DAVILA FACUNDO"])
            st.session_state["precio_gasoil"] = st.number_input("💰 Precio Gasoil", value=float(st.session_state["precio_gasoil"]))
            fecha_sel = st.date_input("📅 Fecha", datetime.now())
        with c2:
            ruta_tipo = st.radio("🏔️ Ruta", ["Llano", "Alta Montaña"], horizontal=True)
            traza = st.selectbox("🗺️ Traza", sorted(df_h["Traza"].unique().tolist()) if not df_h.empty else ["SSJJ-OLAR(SDJ)-SSJJ"])
            km_i = st.number_input("🛣️ KM Inicial", value=0.0)
        with c3:
            km_f = st.number_input("🏁 KM Final", value=0.0)
            l_t = st.number_input("⛽ Litros Ticket", value=0.0)
            l_tab = st.number_input("📟 Litros Tablero", value=0.0)
            l_ral = st.number_input("⏳ Litros Ralentí", value=0.0)

        dist = km_f - km_i
        cons = (l_t / dist * 100) if dist > 0 else 0
        costo_v = l_t * st.session_state["precio_gasoil"]
        desv = l_t - (l_tab + l_ral)

        if st.form_submit_button("💾 GUARDAR", use_container_width=True):
            nuevo = {
                "Fecha": fecha_sel.strftime('%d/%m/%Y'), "Chofer": chofer, "Movil": movil_sel, "Marca": marca,
                "Ruta": ruta_tipo, "Traza": traza, "KM_Ini": km_i, "KM_Fin": km_f, "KM_Recorr": dist,
                "L_Ticket": l_t, "L_Tablero": l_tab, "L_Ralenti": l_ral, "Consumo_L100": round(cons, 2),
                "Costo_Total_ARS": round(costo_v, 2), "Desvio_Neto": round(desv, 2)
            }
            df_final = pd.concat([df_h, pd.DataFrame([nuevo])], ignore_index=True)
            conn.update(spreadsheet=URL, data=df_final)
            st.session_state["form_reset_key"] += 1
            st.rerun()

# --- TAB 2: OJO DE HALCÓN ---
with tabs[1]:
    if not df_h.empty:
        df_ana = df_h.dropna(subset=['Fecha']).copy()
        
        # 1. Ranking de Eficiencia (MEDALLAS)
        st.markdown("### 🏆 Ranking de Eficiencia (Top 5)")
        top_eff = df_ana.groupby("Chofer")["Consumo_L100"].mean().sort_values().head(5).reset_index()
        cols = st.columns(5)
        for i, row in top_eff.iterrows():
            with cols[i]:
                st.markdown(f"""
                    <div class="metric-card">
                        <div class="driver-name">{row['Chofer']}</div>
                        <div class="driver-score">{row['Consumo_L100']:.1f}</div>
                        <div style="color:#aab; font-size:12px;">L/100</div>
                    </div>
                """, unsafe_allow_html=True)

        # 2. Ranking de Desvíos (COLORES)
        st.divider()
        st.markdown("### ⚠️ Ranking de Desvíos de Combustible")
        df_desv = df_ana.groupby("Chofer")["Desvio_Neto"].sum().sort_values(ascending=False).reset_index()
        c_des1, c_des2 = st.columns(2)
        for i, row in df_desv.iterrows():
            clase_critica = "desvio-critico" if row['Desvio_Neto'] > 50 else ""
            col_target = c_des1 if i % 2 == 0 else c_des2
            col_target.markdown(f"""
                <div class="desvio-item {clase_critica}">
                    <span style="color:white; font-weight:bold;">{row['Chofer']}</span>
                    <span style="color:white; font-weight:bold; font-size:18px;">{row['Desvio_Neto']:.1f} L</span>
                </div>
            """, unsafe_allow_html=True)

        # 3. Gráficos
        st.divider()
        g1, g2 = st.columns(2)
        with g1:
            fig1 = px.area(df_ana.groupby(df_ana['Fecha'].dt.to_period('M'))['Consumo_L100'].mean().reset_index().astype({'Fecha':str}), 
                           x='Fecha', y='Consumo_L100', title="📈 Tendencia Mensual", color_discrete_sequence=["#00FFC8"])
            st.plotly_chart(fig1, use_container_width=True)
        with g2:
            fig2 = px.bar(df_ana.groupby("Marca")["Consumo_L100"].mean().reset_index(), 
                          x='Marca', y='Consumo_L100', title="🚛 Scania vs Mercedes", color='Marca')
            st.plotly_chart(fig2, use_container_width=True)

# --- TAB 3: HISTORIAL ---
with tabs[2]:
    if not df_h.empty:
        st.dataframe(df_h.sort_values("Fecha", ascending=False), use_container_width=True)
