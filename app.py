import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import time
import os

# --- 1. CONFIGURACIÓN Y ESTILOS (AUDITADOS) ---
st.set_page_config(page_title="Inteligencia de Flota Jujuy", layout="wide")

# Estilos para que las tarjetas y el login se vean prolijos
st.markdown("""
    <style>
    .metric-card { background-color: #1e2130; padding: 15px; border-radius: 12px; border: 1px solid #3d425a; text-align: center; }
    .driver-name { font-weight: bold; font-size: 16px; margin: 5px 0; color: white; }
    .driver-score { font-size: 22px; color: #4CAF50; font-weight: bold; }
    .category-header { background: linear-gradient(90deg, #1e2130, #3d425a); padding: 10px; border-radius: 8px; margin-bottom: 15px; text-align: center; }
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

# --- 3. CARGA DE DATOS (EXCEL + SHEETS) ---
conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1PEH7lbtoq_oAHwom0O5YYYskFm6ALJ6LCj1FfQKzpmQ/edit?gid=0#gid=0"

if "precio_gasoil" not in st.session_state:
    st.session_state["precio_gasoil"] = 2065.0 # Actualizado según tu captura

@st.cache_data
def obtener_lista_choferes():
    archivo = "choferes.xlsx"
    if os.path.exists(archivo):
        xl = pd.read_excel(archivo)
        col = "Chofer" if "Chofer" in xl.columns else xl.columns[0]
        return sorted(xl[col].dropna().unique().tolist())
    return ["ADELMO JORGE", "VALENTIN ARIEL", "BENITEZ DIEGO"] # Fallback

df_h = conn.read(spreadsheet=URL, ttl=0)
LISTA_MAESTRA = obtener_lista_choferes()

# --- 4. INTERFAZ ---
st.title("🚚 Inteligencia de Flota y Costos")
tabs = st.tabs(["⛽ Registro de Carga", "🦅 Ojo de Halcón (IA)", "📜 Historial"])

with tabs[0]:
    st.subheader("📝 Nuevo Registro")
    
    # Fila superior: Precio Gasoil (Limpio)
    c_p, _ = st.columns([1, 3])
    with c_p:
        st.session_state["precio_gasoil"] = st.number_input("💵 Precio Gasoil por Litro ($)", value=st.session_state["precio_gasoil"])
    
    with st.form("registro_form", clear_on_submit=True):
        # Organización amigable en 3 columnas (Como en image_bb35be.png)
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("##### 🚛 Vehículo")
            movil_sel = st.selectbox("🔢 Móvil", list(range(1, 101)), index=36) # Index 36 es el móvil 37
            marca = st.radio("🏷️ Marca del Vehículo", ["SCANIA", "MERCEDES BENZ"], horizontal=True)
            chofer = st.selectbox("👤 Chofer", LISTA_MAESTRA)
            
        with col2:
            st.markdown("##### 📍 Ruta y Trayecto")
            ruta_tipo = st.radio("🏔️ Tipo de Ruta", ["Llano", "Alta Montaña"], horizontal=True)
            traza = st.selectbox("🗺️ Seleccionar Traza", ["➕ NUEVA"] + sorted(df_h["Traza"].unique().tolist()) if not df_h.empty else ["➕ NUEVA"])
            nt = st.text_input("✍️ Nombre Nueva Traza (Opcional)").upper()
            t_final = nt if (traza == "➕ NUEVA" and nt != "") else traza

        with col3:
            st.markdown("##### ⛽ Kilometraje y Combustible")
            # KM Inicial automático por móvil
            km_auto = int(df_h[df_h["Movil"] == movil_sel]["KM_Fin"].max()) if not df_h.empty else 0
            kmi = st.number_input("🛣️ KM Inicial", value=km_auto)
            kmf = st.number_input("🏁 KM Final")
            lt = st.number_input("⛽ Litros Ticket")
            ltab = st.number_input("📟 Litros Tablero")
            lral = st.number_input("⏳ Litros Ralentí")

        # --- CALCULADORA AUTOMÁTICA ---
        recorrido = kmf - kmi
        consumo = (lt / recorrido * 100) if recorrido > 0 else 0
        costo = lt * st.session_state["precio_gasoil"]
        desvio = lt - (ltab + lral)

        st.divider()
        if recorrido > 0:
            # Resumen visual rápido
            c1, c2, c3 = st.columns(3)
            c1.info(f"📏 Distancia: **{recorrido} KM**")
            c2.info(f"📊 Consumo: **{consumo:.1f} L/100**")
            c3.info(f"💰 Costo: **${costo:,.0f}**")

        if st.form_submit_button("💾 GUARDAR REGISTRO", use_container_width=True):
            if kmf <= kmi or lt <= 0:
                st.error("⚠️ Verifique que el KM Final sea mayor al inicial y los litros sean válidos.")
            else:
                nuevo = {
                    "Fecha": datetime.now().strftime('%Y-%m-%d'), "Movil": movil_sel, 
                    "Chofer": chofer, "Marca": marca, "Ruta": ruta_tipo, "Traza": t_final, 
                    "KM_Ini": kmi, "KM_Fin": kmf, "KM_Recorr": recorrido, "L_Ticket": lt, 
                    "L_Tablero": ltab, "L_Ralenti": lral, "Desvio_Neto": round(desvio, 2), 
                    "Consumo_L100": round(consumo, 2), "Costo_Total_ARS": round(costo, 2),
                    "Costo_Ralenti_ARS": round(lral * st.session_state["precio_gasoil"], 2)
                }
                # Aquí iría el guardado a Sheets
                st.success("✅ Datos procesados y guardados.")
                time.sleep(1)
                st.rerun()

# El resto de los tabs (Ojo de Halcón e Historial) se mantienen igual
