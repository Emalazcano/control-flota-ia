import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import time
import plotly.express as px
import os

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Control Flota Jujuy", layout="wide")

conn = st.connection("gsheets", type=GSheetsConnection)
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1PEH7lbtoq_oAHwom0O5YYYskFm6ALJ6LCj1FfQKzpmQ/edit?gid=0#gid=0"

def obtener_datos():
    try:
        df = conn.read(spreadsheet=SPREADSHEET_URL, ttl=0)
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

# --- 2. LOGIN ---
if "auth" not in st.session_state:
    st.title("🚛 Sistema de Control de Flota")
    _, col_log, _ = st.columns([1, 3, 1])
    with col_log:
        st.subheader("🔐 Acceso")
        c1, c2, c3 = st.columns([2, 2, 1])
        u = c1.text_input("Usuario", label_visibility="collapsed", placeholder="Usuario")
        p = c2.text_input("Clave", type="password", label_visibility="collapsed", placeholder="Contraseña")
        if c3.button("Entrar", use_container_width=True):
            if u == "ema_admin" and p == "jujuy2024":
                st.session_state["auth"] = True
                st.rerun()
            else: st.error("❌")
    st.stop()

# --- 3. DATOS ---
df_h = obtener_datos()
lista_choferes = obtener_choferes()

# --- 4. INTERFAZ ---
st.title("🚛 Inteligencia de Flota y Costos")
tabs = st.tabs(["⛽ Registro", "🦅 Inteligencia", "📜 Historial"])

# PESTAÑA REGISTRO
with tabs[0]:
    with st.form("registro", clear_on_submit=True):
        f1, f2, f3 = st.columns(3)
        with f1:
            fecha = st.date_input("Fecha", datetime.now())
            movil = st.number_input("Móvil", min_value=1, max_value=100)
            chofer = st.selectbox("Chofer", lista_choferes)
        with f2:
            marca = st.radio("Marca", ["SCANIA", "MERCEDES BENZ"], horizontal=True)
            ruta = st.radio("Ruta", ["Llano", "Alta Montaña"], horizontal=True)
            traza = st.text_input("Traza").upper()
        with f3:
            kmi = st.number_input("KM Inicial", min_value=0)
            kmf = st.number_input("KM Final", min_value=0)
            lt = st.number_input("Litros Ticket", min_value=0.0)
            ltab = st.number_input("Litros Tablero", min_value=0.0)
            lral = st.number_input("Litros Ralentí", min_value=0.0)
        
        if st.form_submit_button("💾 GUARDAR"):
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

# PESTAÑA IA (Con Alertas Anteriores + Tolerancia 50L)
with tabs[1]:
    if not df_h.empty:
        m1, m2, m3 = st.columns(3)
        m1.metric("Gasto Total", f"$ {df_h['Costo_Total_ARS'].sum():,.0f}")
        m2.metric("Consumo Promedio", f"{df_h['Consumo_L100'].mean():,.1f} L/100")
        m3.metric("Desvío Neto Total", f"{df_h['Desvio_Neto'].sum():,.1f} L")
        
        st.divider()
        g1, g2 = st.columns(2)
        
        with g1:
            st.subheader("🏆 Eco-Driving")
            rank = df_h.groupby("Chofer")["Consumo_L100"].mean().sort_values().head(3).reset_index()
            for i, r in rank.iterrows():
                emoji = ["🥇", "🥈", "🥉"][i]
                st.write(f"{emoji} **{r['Chofer']}**: {r['Consumo_L100']:.2f} L/100km")
        
        with g2:
            st.subheader("🚨 Alertas de Desvío")
            # Agrupamos los desvíos actuales por chofer
            alertas_df = df_h.groupby("Chofer")["Desvio_Neto"].sum().reset_index()
            
            for _, r in alertas_df.iterrows():
                valor = r['Desvio_Neto']
                # Aplicamos la tolerancia de 50 litros
                if valor > 50:
                    st.error(f"**{r['Chofer']}**: {valor:.1f} Litros (Excede tolerancia)")
                elif valor < -50:
                    st.warning(f"**{r['Chofer']}**: {valor:.1f} Litros (Carga menor al tablero)")
                else:
                    # Estilo anterior para los que están en rango
                    st.write(f"**{r['Chofer']}**: {valor:.1f} Litros (Normal)")
    else:
        st.info("Sin datos.")

# PESTAÑA HISTORIAL
with tabs[2]:
    st.subheader("📜 Historial Completo")
    if not df_h.empty:
        st.dataframe(df_h.iloc[::-1], use_container_width=True)
        st.download_button("📥 Exportar CSV", df_h.to_csv(index=False), "historial.csv")
