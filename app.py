import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import time
import plotly.express as px
from fpdf import FPDF
import os

# --- 1. CONFIGURACIÓN Y ESTILO ---
st.set_page_config(page_title="Control de Flota IA - Jujuy", layout="wide")

# CSS personalizado para mejorar la prolijidad de las tarjetas
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 24px; color: #00ffcc; }
    .stAlert { border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CONEXIÓN Y DATOS ---
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1PEH7lbtoq_oAHwom0O5YYYskFm6ALJ6LCj1FfQKzpmQ/edit?gid=0#gid=0"
conn = st.connection("gsheets", type=GSheetsConnection)

def obtener_datos():
    try:
        df = conn.read(spreadsheet=SPREADSHEET_URL, ttl=0)
        # Limpieza masiva de datos numéricos
        cols = ["Costo_Total_ARS", "L_Ticket", "Costo_Ralenti_ARS", "Consumo_L100", "Desvio_Neto", "L_Tablero", "L_Ralenti"]
        for c in cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        return df
    except:
        return pd.DataFrame()

@st.cache_data
def obtener_choferes():
    archivo = "choferes.xlsx"
    if os.path.exists(archivo):
        try:
            df = pd.read_excel(archivo)
            col = "Chofer" if "Chofer" in df.columns else df.columns[0]
            return sorted(df[col].dropna().unique().tolist())
        except: pass
    return ["Error al leer choferes.xlsx"]

# --- 3. SEGURIDAD ---
if "auth" not in st.session_state:
    st.title("🔐 Sistema de Control de Flota")
    col_u, col_p = st.columns(2)
    u = col_u.text_input("Usuario")
    p = col_p.text_input("Contraseña", type="password")
    if st.button("Ingresar"):
        if u == "ema_admin" and p == "jujuy2024":
            st.session_state["auth"] = True
            st.rerun()
        else:
            st.error("Acceso denegado")
    st.stop()

# --- 4. INTERFAZ PRINCIPAL ---
df_h = obtener_datos()
choferes = obtener_choferes()

st.title("🚛 Inteligencia de Flota y Costos")

# Pestañas para organizar la prolijidad
tab_carga, tab_ia, tab_historial = st.tabs(["⛽ Registro de Carga", "🦅 Ojo de Halcón (IA)", "📜 Historial Completo"])

# --- PESTAÑA 1: CARGA ---
with tab_carga:
    st.subheader("Nuevo Registro de Combustible")
    with st.form("form_prolijo"):
        c1, c2, c3 = st.columns(3)
        with c1:
            fecha = st.date_input("Fecha", datetime.now())
            movil = st.selectbox("Móvil", list(range(1, 101)))
            chofer = st.selectbox("Chofer", choferes)
        with c2:
            marca = st.radio("Marca", ["SCANIA", "MERCEDES BENZ"], horizontal=True)
            ruta = st.radio("Ruta", ["Llano", "Alta Montaña"], horizontal=True)
            traza = st.text_input("Traza (Ej: SSJJ-OLAR)").upper()
        with c3:
            kmi = st.number_input("KM Inicial", min_value=0)
            kmf = st.number_input("KM Final", min_value=0)
            lt = st.number_input("Litros Ticket", min_value=0.0)
            ltab = st.number_input("Litros Tablero", min_value=0.0)
            lral = st.number_input("Litros Ralentí", min_value=0.0)
        
        if st.form_submit_button("💾 REGISTRAR OPERACIÓN"):
            if kmf > kmi and lt > 0:
                recorrido = kmf - kmi
                cons = (lt / recorrido * 100)
                desv = lt - (ltab + lral)
                nuevo_dato = {
                    "Fecha": fecha.strftime('%d/%m/%Y'), "Chofer": chofer, "Movil": movil,
                    "Marca": marca, "Ruta": ruta, "Traza": traza, "KM_Ini": kmi, "KM_Fin": kmf,
                    "KM_Recorr": recorrido, "L_Ticket": lt, "L_Tablero": ltab, "L_Ralenti": lral,
                    "Desvio_Neto": round(desv, 2), "Consumo_L100": round(cons, 2),
                    "Costo_Total_ARS": round(lt * 1100, 2), "Costo_Ralenti_ARS": round(lral * 1100, 2)
                }
                df_f = pd.concat([df_h, pd.DataFrame([nuevo_dato])], ignore_index=True)
                conn.update(spreadsheet=SPREADSHEET_URL, data=df_f)
                st.success("✅ Datos guardados con éxito")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Verifique los kilómetros y litros.")

# --- PESTAÑA 2: INTELIGENCIA ARTIFICIAL ---
with tab_ia:
    if not df_h.empty:
        # KPI Cards superiores
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Gasto Total", f"$ {df_h['Costo_Total_ARS'].sum():,.0f}")
        k2.metric("Litros Totales", f"{df_h['L_Ticket'].sum():,.0f} L")
        k3.metric("Consumo Promedio", f"{df_h['Consumo_L100'].mean():,.1f} L/100")
        k4.metric("Desvío Neto", f"{df_h['Desvio_Neto'].sum():,.1f} L")

        st.divider()

        # Alertas de Anomalías
        prom_t = df_h.groupby("Traza")["Consumo_L100"].transform("mean")
        anom = df_h[df_h["Consumo_L100"] > (prom_t * 1.20)].tail(3)
        if not anom.empty:
            st.warning("🚨 **Detección de Anomalías (Ojo de Halcón)**")
            for _, r in anom.iterrows():
                st.error(f"Exceso en Móvil {r['Movil']} ({r['Chofer']}): {r['Consumo_L100']} L/100km")

        # Gráficos organizados
        g1, g2 = st.columns(2)
        
        with g1:
            st.subheader("🏆 Top Choferes Eco-Driving")
            # Agrupamos por chofer y calculamos el promedio de consumo
            # El más eficiente es el que tiene el número más bajo (menor consumo)
            rank = df_h.groupby("Chofer")["Consumo_L100"].mean().sort_values().reset_index()
            
            # Contenedor para las medallas
            for i, r in rank.head(5).iterrows():
                # Asignamos el emoji según la posición
                if i == 0:
                    medalla = "🥇"
                    color = "gold"
                elif i == 1:
                    medalla = "🥈"
                    color = "silver"
                elif i == 2:
                    medalla = "🥉"
                    color = "#cd7f32" # Bronce
                else:
                    medalla = "👤"
                    color = "white"
                
                # Mostramos cada chofer con una barra de progreso o texto destacado
                st.markdown(f"""
                <div style="background-color: rgba(255,255,255,0.1); padding: 10px; border-radius: 10px; margin-bottom: 5px; border-left: 5px solid {color};">
                    <span style="font-size: 20px;">{medalla}</span> 
                    <b>{r['Chofer']}</b> <br>
                    <small>Promedio: {r['Consumo_L100']:.2f} L/100km</small>
                </div>
                """, unsafe_allow_html=True)
                
        with g2:
            st.subheader("⚠️ Desvío de Combustible por Chofer")
            # Agrupamos por chofer para ver la suma de sus desvíos
            desvio_chofer = df_h.groupby("Chofer")["Desvio_Neto"].sum().sort_values(ascending=False).reset_index()
            
            # Creamos el gráfico de barras
            fig_desvio = px.bar(
                desvio_chofer,
                x="Desvio_Neto",
                y="Chofer",
                orientation='h',
                title="Total Litros Desviados (Ticket vs Tablero)",
                labels={"Desvio_Neto": "Litros de Desvío", "Chofer": "Chofer"},
                color="Desvio_Neto",
                color_continuous_scale="Reds", # Los desvíos más altos se verán más rojos
                template="plotly_dark"
            )
            
            # Ajustamos el diseño para que se vea impecable
            fig_desvio.update_layout(showlegend=False, height=400)
            st.plotly_chart(fig_desvio, use_container_width=True)
            
            st.info("💡 **Dato clave:** El desvío neto es la diferencia entre los litros del ticket y la suma de (Tablero + Ralentí).")
