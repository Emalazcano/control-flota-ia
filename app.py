import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime
import time

# --- 1. CONFIGURACIÓN Y ESTILOS ---
st.set_page_config(page_title="Inteligencia de Flota Jujuy", layout="wide")

st.markdown("""
    <style>
    .metric-card { background-color: #1e2130; padding: 15px; border-radius: 12px; border: 1px solid #3d425a; text-align: center; }
    .driver-name { font-weight: bold; font-size: 16px; margin: 5px 0; color: white; }
    .driver-score { font-size: 24px; color: #4CAF50; font-weight: bold; }
    
    /* Estilos para las tarjetas de desvío anchas y con colores */
    .desvio-item { padding: 12px; border-radius: 8px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #3d425a; }
    .desvio-critico { background: #421212 !important; border: 1px solid #FF4B4B !important; }
    .desvio-ok { background: #0c2b18 !important; border: 1px solid #00CC96 !important; }
    </style>
""", unsafe_allow_html=True)

# --- 2. CARGA DE DATOS ---
conn = st.connection("gsheets", type=GSheetsConnection)
URL_VIAJES = "https://docs.google.com/spreadsheets/d/1PEH7lbtoq_oAHwom0O5YYYskFm6ALJ6LCj1FfQKzpmQ/edit?gid=0#gid=0"

@st.cache_data(ttl=60)
def cargar_personal():
    try:
        # Lee el excel que tenés en tu repositorio (image_0ee306.png)
        df_c = pd.read_excel("choferes.xlsx")
        return sorted(df_c.iloc[:, 0].dropna().unique().tolist())
    except:
        return ["ERROR AL LEER EXCEL LOCAL"]

def cargar_historial():
    try:
        df = conn.read(spreadsheet=URL_VIAJES, ttl=0)
        if 'Fecha' in df.columns:
            df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=True, errors='coerce')
        return df
    except: return pd.DataFrame()

lista_choferes = cargar_personal()
df_h = cargar_historial()

# --- 3. INTERFAZ ---
tabs = st.tabs(["⛽ Registro de Carga", "🦅 Ojo de Halcón", "📜 Historial"])

# --- TAB REGISTRO ---
with tabs[0]:
    st.subheader("📝 Nuevo Registro")
    with st.form("registro_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            chofer = st.selectbox("👤 Chofer", lista_choferes) # Usa los del excel local
            marca = st.radio("🏷️ Marca", ["SCANIA", "MERCEDES BENZ"], horizontal=True)
            fecha_input = st.date_input("📅 Fecha de Carga", datetime.now())
        with col2:
            traza = st.selectbox("🗺️ Traza", sorted(df_h["Traza"].unique().tolist()) if not df_h.empty else ["SSJJ-OLAR(SDJ)-SSJJ"])
            kmi = st.number_input("🛣️ KM Inicial")
        with col3:
            kmf = st.number_input("🏁 KM Final")
            lt = st.number_input("⛽ Litros Ticket")
            ltab = st.number_input("📟 Litros Tablero")
            lral = st.number_input("⏳ Litros Ralentí")

        if st.form_submit_button("💾 GUARDAR REGISTRO", use_container_width=True):
            dist = kmf - kmi
            costo_viaje = round(lt * 2065.0, 2)
            cons = round((lt / dist * 100), 2) if dist > 0 else 0
            desv = round(lt - (ltab + lral), 2)

            nuevo_reg = {
                "Fecha": fecha_input.strftime('%d/%m/%Y'),
                "Chofer": chofer, "KM_Ini": kmi, "KM_Fin": kmf, "KM_Recorr": dist,
                "L_Ticket": lt, "L_Tablero": ltab, "L_Ralenti": lral,
                "Consumo_L100": cons, "Costo_Total_ARS": costo_viaje, "Desvio_Neto": desv
            }
            
            df_final = pd.concat([df_h, pd.DataFrame([nuevo_reg])], ignore_index=True)
            conn.update(spreadsheet=URL_VIAJES, data=df_final)
            st.success("✅ Guardado correctamente")
            time.sleep(1)
            st.rerun()

# --- TAB OJO DE HALCÓN ---
with tabs[1]:
    if not df_h.empty:
        st.subheader("⚠️ Ranking de Desvíos de Combustible")
        df_desv = df_h.groupby("Chofer")["Desvio_Neto"].sum().sort_values(ascending=False).reset_index()
        
        for i, row in df_desv.iterrows():
            # Lógica de colores restaurada
            es_critico = row['Desvio_Neto'] > 50
            clase_color = "desvio-critico" if es_critico else "desvio-ok"
            icono = "🚨" if es_critico else "✅"
            
            st.markdown(f"""
                <div class="desvio-item {clase_color}">
                    <b style="color:white;">{row["Chofer"]}</b>
                    <b style="color:white; font-size:18px;">{icono} {row["Desvio_Neto"]:.1f} L</b>
                </div>
            """, unsafe_allow_html=True)
