import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime
import time
import os

# --- 1. CONFIGURACIÓN Y ESTILOS ---
st.set_page_config(page_title="Inteligencia de Flota Jujuy", layout="wide")

st.markdown("""
    <style>
    .metric-card { background-color: #1e2130; padding: 15px; border-radius: 12px; border: 1px solid #3d425a; text-align: center; }
    .driver-name { font-weight: bold; font-size: 16px; margin: 5px 0; color: white; }
    .driver-score { font-size: 24px; color: #4CAF50; font-weight: bold; }
    .medal-icon { font-size: 32px; margin-bottom: 5px; }
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

# --- 3. CONEXIÓN Y DATOS ---
conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1PEH7lbtoq_oAHwom0O5YYYskFm6ALJ6LCj1FfQKzpmQ/edit?gid=0#gid=0"

if "precio_gasoil" not in st.session_state:
    st.session_state["precio_gasoil"] = 2065.0

def cargar_historial():
    try:
        df = conn.read(spreadsheet=URL, ttl=0)
        num_cols = ["Movil", "KM_Fin", "KM_Ini", "L_Ticket", "L_Tablero", "L_Ralenti", "Desvio_Neto", "Consumo_L100", "Costo_Total_ARS"]
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        if 'Fecha' in df.columns:
            # dayfirst=True es vital para que no confunda 05/01 con 01/05
            df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=True, errors='coerce')
            df['Fecha'] = df['Fecha'].fillna(pd.Timestamp.now().normalize())
        return df
    except: return pd.DataFrame()

df_h = cargar_historial()

# --- 4. INTERFAZ ---
st.title("🚚 Inteligencia de Flota y Costos")
tabs = st.tabs(["⛽ Registro de Carga", "🦅 Ojo de Halcón", "📜 Historial"])

# --- TAB 1: REGISTRO ---
with tabs[0]:
    st.subheader("📝 Nuevo Registro")
    
    # Función para limpiar memoria de los campos
    def limpiar_sesion_form():
        for k in ["kmf_k", "lt_k", "ltab_k", "lral_k", "nt_k"]:
            if k in st.session_state:
                st.session_state[k] = 0.0 if k != "nt_k" else ""

    movil_sel = st.selectbox("🔢 Móvil", list(range(1, 101)), index=36)
    
    km_sugerido = 0.0
    if not df_h.empty:
        ult_m = df_h[df_h["Movil"] == movil_sel]
        if not ult_m.empty:
            km_sugerido = float(ult_m.sort_values("Fecha").iloc[-1]["KM_Fin"])

    # clear_on_submit=True limpia la interfaz visual
    with st.form("registro_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            marca = st.radio("🏷️ Marca", ["SCANIA", "MERCEDES BENZ"], horizontal=True)
            chofer = st.selectbox("👤 Chofer", sorted(df_h["Chofer"].unique().tolist()) if not df_h.empty else ["NUEVO"])
            precio_comb = st.number_input("💰 Precio Litro Gasoil", value=float(st.session_state["precio_gasoil"]))
            fecha_input = st.date_input("📅 Fecha de Carga", datetime.now()) # MANDATORIO
        with col2:
            ruta_tipo = st.radio("🏔️ Tipo de Ruta", ["Llano", "Alta Montaña"], horizontal=True)
            trazas_disponibles = ["➕ NUEVA"] + (sorted(df_h["Traza"].unique().tolist()) if not df_h.empty else [])
            traza_sel = st.selectbox("🗺️ Traza", trazas_disponibles)
            nt = st.text_input("✍️ Nombre Nueva Traza", key="nt_k").upper()
            t_final = nt if (traza_sel == "➕ NUEVA" and nt != "") else traza_sel
        with col3:
            kmi = st.number_input("🛣️ KM Inicial", value=float(km_sugerido))
            kmf = st.number_input("🏁 KM Final", key="kmf_k")
            lt = st.number_input("⛽ Litros Ticket", key="lt_k")
            ltab = st.number_input("📟 Litros Tablero", key="ltab_k")
            lral = st.number_input("⏳ Litros Ralentí", key="lral_k")

        if st.form_submit_button("💾 GUARDAR REGISTRO", use_container_width=True):
            dist = kmf - kmi
            cons = (lt / dist * 100) if dist > 0 else 0
            costo_viaje = round(lt * precio_comb, 2)
            desv = lt - (ltab + lral)

            if kmf <= kmi or lt <= 0 or t_final == "":
                st.error("⚠️ Datos inválidos. Verifique KM, Litros y Traza.")
            else:
                nuevo_reg = {
                    "Fecha": fecha_input.strftime('%d/%m/%Y'), # RESPETO A TU ELECCIÓN
                    "Chofer": chofer, "Movil": movil_sel, "Marca": marca,
                    "Ruta": ruta_tipo, "Traza": t_final, "KM_Ini": kmi, "KM_Fin": kmf,
                    "KM_Recorr": dist, "L_Ticket": lt, "L_Tablero": ltab, "L_Ralenti": lral,
                    "Consumo_L100": round(cons, 2), 
                    "Costo_Total_ARS": costo_viaje, 
                    "Desvio_Neto": round(desv, 2)
                }
                
                with st.spinner("Guardando..."):
                    df_final = pd.concat([df_h, pd.DataFrame([nuevo_reg])], ignore_index=True)
                    conn.update(spreadsheet=URL, data=df_final)
                    
                    # Actualizar estado para la próxima carga
                    st.session_state["precio_gasoil"] = precio_comb
                    limpiar_sesion_form()
                    
                    st.success(f"✅ Guardado: {fecha_input.strftime('%d/%m/%Y')} - Costo: ${costo_viaje:,.2f}")
                    time.sleep(1)
                    st.rerun()

# --- TAB 2: ANÁLISIS ---
with tabs[1]:
    if not df_h.empty:
        st.subheader("🏆 Ranking de Eficiencia (Top 5)")
        top_5 = df_h.groupby("Chofer")["Consumo_L100"].mean().sort_values().head(5).reset_index()
        cols = st.columns(5)
        medallas = ["🥇", "🥈", "🥉", "👤", "👤"]
        for i, row in top_5.iterrows():
            with cols[i]:
                st.markdown(f'<div class="metric-card"><div class="medal-icon">{medallas[i]}</div><div class="driver-name">{row["Chofer"]}</div><div class="driver-score">{row["Consumo_L100"]:.1f}</div><div style="color:#aab;font-size:12px;">L/100</div></div>', unsafe_allow_html=True)

        st.divider()
        st.subheader("⚠️ Ranking de Desvíos de Combustible")
        df_desv = df_h.groupby("Chofer")["Desvio_Neto"].sum().sort_values(ascending=False).reset_index()
        ca1, ca2 = st.columns(2)
        for i, row in df_desv.iterrows():
            exc = row['Desvio_Neto'] > 50
            target = ca1 if i % 2 == 0 else ca2
            target.markdown(f'<div style="background:{"#421212" if exc else "#1e2130"};padding:12px;border-radius:8px;border:1px solid {"#FF4B4B" if exc else "#3d425a"};margin-bottom:8px;display:flex;justify-content:space-between;align-items:center;"><b style="color:white;">{row["Chofer"]}</b><b style="font-size:18px;color:white;">{row["Desvio_Neto"]:.1f} L</b></div>', unsafe_allow_html=True)

# --- TAB 3: HISTORIAL ---
with tabs[2]:
    if not df_h.empty:
        df_v = df_h.copy()
        df_v['Fecha'] = df_v['Fecha'].dt.strftime('%d/%m/%Y')
        st.dataframe(df_v.sort_values("Fecha", ascending=False), use_container_width=True)
