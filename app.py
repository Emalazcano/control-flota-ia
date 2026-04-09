import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import time
import plotly.express as px
import os

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Control de Flota IA - Jujuy", layout="wide")

# Conexión a Google Sheets
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1PEH7lbtoq_oAHwom0O5YYYskFm6ALJ6LCj1FfQKzpmQ/edit?gid=0#gid=0"
conn = st.connection("gsheets", type=GSheetsConnection)

def obtener_datos():
    try:
        df = conn.read(spreadsheet=SPREADSHEET_URL, ttl=0)
        # Limpieza de datos para evitar errores de "None" o texto en columnas numéricas
        cols_num = ["Costo_Total_ARS", "L_Ticket", "Costo_Ralenti_ARS", "Consumo_L100", "Desvio_Neto", "L_Tablero", "L_Ralenti"]
        for c in cols_num:
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
    return ["Cargar choferes en el Excel"]

# --- 2. LOGIN COMPACTO ---
if "auth" not in st.session_state:
    st.title("🚛 Sistema de Control de Flota")
    # Login en una sola fila para que no sea extenso
    col1, col2, col3 = st.columns([2, 2, 1])
    u = col1.text_input("Usuario", placeholder="ema_admin")
    p = col2.text_input("Contraseña", type="password", placeholder="••••")
    if col3.button("Ingresar", use_container_width=True):
        if u == "ema_admin" and p == "jujuy2024":
            st.session_state["auth"] = True
            st.rerun()
        else:
            st.error("Error")
    st.stop()

# --- 3. PROCESAMIENTO DE DATOS ---
df_h = obtener_datos()
lista_choferes = obtener_choferes()

# --- 4. INTERFAZ PRINCIPAL ---
st.title("🚛 Inteligencia de Flota y Costos")

tabs = st.tabs(["⛽ Registro de Carga", "🦅 Ojo de Halcón (IA)", "📜 Historial Completo"])

# --- PESTAÑA: CARGA ---
with tabs[0]:
    with st.form("form_carga", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            fecha = st.date_input("Fecha", datetime.now())
            movil = st.selectbox("Móvil", list(range(1, 101)))
            chofer = st.selectbox("Chofer", lista_choferes)
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
        
        if st.form_submit_button("💾 GUARDAR REGISTRO"):
            if kmf > kmi and lt > 0:
                recorrido = kmf - kmi
                cons = (lt / recorrido * 100)
                desv = lt - (ltab + lral)
                nuevo = {
                    "Fecha": fecha.strftime('%d/%m/%Y'), "Chofer": chofer, "Movil": movil,
                    "Marca": marca, "Ruta": ruta, "Traza": traza, "KM_Ini": kmi, "KM_Fin": kmf,
                    "KM_Recorr": recorrido, "L_Ticket": lt, "L_Tablero": ltab, "L_Ralenti": lral,
                    "Desvio_Neto": round(desv, 2), "Consumo_L100": round(cons, 2),
                    "Costo_Total_ARS": round(lt * 1100, 2), "Costo_Ralenti_ARS": round(lral * 1100, 2)
                }
                df_f = pd.concat([df_h, pd.DataFrame([nuevo])], ignore_index=True)
                conn.update(spreadsheet=SPREADSHEET_URL, data=df_f)
                st.success("✅ Guardado")
                time.sleep(1)
                st.rerun()

# --- PESTAÑA: IA & DASHBOARD ---
with tabs[1]:
    if not df_h.empty:
        # Métricas principales
        k1, k2, k3 = st.columns(3)
        k1.metric("Gasto Total", f"$ {df_h['Costo_Total_ARS'].sum():,.0f}")
        k2.metric("Litros Totales", f"{df_h['L_Ticket'].sum():,.0f} L")
        k3.metric("Consumo Promedio", f"{df_h['Consumo_L100'].mean():,.1f} L/100")
        
        st.divider()
        g1, g2 = st.columns(2)
        
        with g1:
            st.subheader("🏆 Top Choferes Eco-Driving")
            rank = df_h.groupby("Chofer")["Consumo_L100"].mean().sort_values().head(5).reset_index()
            for i, r in rank.iterrows():
                m = "🥇" if i==0 else "🥈" if i==1 else "🥉" if i==2 else "👤"
                st.markdown(f"**{m} {r['Chofer']}** - {r['Consumo_L100']:.2f} L/100km")
        
        with g2:
            st.subheader("⚠️ Monitor de Desvío Crítico")
            desv_c = df_h.groupby("Chofer")["Desvio_Neto"].sum().sort_values(ascending=False).reset_index()
            for _, r in desv_c.iterrows():
                col_b = "#FF4B4B" if r['Desvio_Neto'] > 20 else "#28a745"
                st.markdown(f"<div style='border-left: 5px solid {col_b}; padding-left: 10px;'><b>{r['Chofer']}</b>: {r['Desvio_Neto']:.1f} L</div>", unsafe_allow_html=True)
    else:
        st.info("Carga datos para ver el análisis.")

# --- PESTAÑA: HISTORIAL ---
with tabs[2]:
    st.subheader("📜 Historial Completo")
    if not df_h.empty:
        # Esto soluciona que el historial no aparezca
        st.dataframe(df_h.iloc[::-1], use_container_width=True)
        st.download_button("📥 Descargar Excel", df_h.to_csv(index=False), "flota.csv")
    else:
        st.warning("No hay datos en el historial.")
