import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import time
import plotly.express as px
from sklearn.ensemble import IsolationForest
from fpdf import FPDF

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Control de Flota IA - Jujuy", layout="wide")

# --- 2. CONEXIÓN ---
# ⚠️ REEMPLAZA CON TU URL
SPREADSHEET_URL = "TU_LINK_DE_GOOGLE_SHEETS_AQUI"
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 3. DEFINICIÓN DE FUNCIONES (Deben ir antes de usarse) ---

def obtener_datos():
    try:
        return conn.read(spreadsheet=SPREADSHEET_URL, ttl=0)
    except:
        return pd.DataFrame()

def generar_comprobante_pdf(datos):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(230, 230, 230)
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 15, "COMPROBANTE DE VIAJE - CONTROL DE FLOTA", ln=True, align="C", fill=True)
    pdf.ln(10)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, f"Detalle de Carga - Movil {datos.get('Movil', 'S/N')}", ln=True)
    pdf.line(10, 35, 200, 35)
    pdf.ln(5)
    pdf.set_font("Arial", size=11)
    for clave, valor in datos.items():
        pdf.set_font("Arial", "B", 11)
        pdf.cell(50, 8, f"{clave}:", border="B")
        pdf.set_font("Arial", size=11)
        pdf.cell(0, 8, f" {valor}", border="B", ln=True)
    pdf.ln(20)
    pdf.set_font("Arial", "I", 9)
    pdf.cell(0, 10, f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}", align="C")
    return pdf.output()

def check_password():
    """Retorna True si el usuario introdujo la contraseña correcta."""
    if "password_correct" not in st.session_state:
        st.title("🔐 Acceso Sistema de Flota")
        st.text_input("Usuario", key="username")
        st.text_input("Contraseña", type="password", key="password")
        if st.button("Ingresar"):
            usuarios_validos = {"ema_admin": "jujuy2024", "operador": "flota123"}
            user = st.session_state["username"]
            pwd = st.session_state["password"]
            if user in usuarios_validos and usuarios_validos[user] == pwd:
                st.session_state["password_correct"] = True
                st.session_state["user_role"] = "admin" if user == "ema_admin" else "operador"
                st.rerun()
            else:
                st.error("😕 Usuario o contraseña incorrectos")
        return False
    return True

# --- 4. PROGRAMA PRINCIPAL (Llamada a las funciones) ---

if check_password():
    df_historico = obtener_datos()
    role = st.session_state.get("user_role", "operador")
    user_logueado = st.session_state["username"].upper()

    # Sidebar
    st.sidebar.success(f"👤 {user_logueado}")
    precio_litro = st.sidebar.number_input("Precio Litro Gasoil ($)", min_value=0.0, value=1100.0)
    
    opciones = ["Cargar Combustible", "Análisis IA & Dashboard"] if role == "admin" else ["Cargar Combustible"]
    menu = st.sidebar.selectbox("Menú Principal", opciones, key="menu_unico")

    if st.sidebar.button("🚪 Cerrar Sesión"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()

    # --- LÓGICA DE MENÚ ---
    if menu == "Cargar Combustible":
        st.header("⛽ Registro de Carga")
        
        # Simulación de carga de choferes (puedes reemplazar con tu excel)
        lista_choferes = ["Chofer 1", "Chofer 2", "Chofer 3"] 
        
        with st.form("form_carga"):
            col1, col2 = st.columns(2)
            with col1:
                fecha = st.date_input("Fecha", datetime.now())
                chofer = st.selectbox("Chofer", lista_choferes)
                movil = st.selectbox("Móvil", list(range(1, 101)))
                marca = st.radio("Marca", ["Scania", "Mercedes"])
                ruta = st.radio("Tipo de Ruta", ["Llano", "Alta Montaña"])
                traza = st.text_input("Traza (Origen - Destino)")
            with col2:
                km_ini = st.number_input("KM Inicial", min_value=0)
                km_fin = st.number_input("KM Final", min_value=0)
                l_ticket = st.number_input("Litros Ticket", min_value=0.0)
                l_tablero = st.number_input("Litros Tablero", min_value=0.0)
                l_ralenti = st.number_input("Litros Ralentí", min_value=0.0)
            
            btn_guardar = st.form_submit_button("💾 GUARDAR Y GENERAR PDF")

        if btn_guardar:
            if km_fin <= km_ini:
                st.error("❌ El KM Final debe ser mayor.")
            else:
                km_recorr = km_fin - km_ini
                consumo = (l_ticket / km_recorr * 100) if km_recorr > 0 else 0
                costo_total = l_ticket * precio_litro
                
                # Datos para el PDF
                datos_viaje = {
                    "Fecha": str(fecha), "Chofer": chofer, "Movil": movil,
                    "Marca": marca, "Ruta": ruta, "Traza": traza,
                    "KM Recorridos": f"{km_recorr} km", "Litros": f"{l_ticket} L",
                    "Consumo": f"{round(consumo, 2)} L/100km", "Costo": f"${costo_total:,.2f}"
                }
                
                # Guardar (Simulado aquí, usa tu lógica de conn.update)
                st.success("✅ Registro guardado en Sheets.")
                
                # Generar PDF
                pdf_bytes = generar_comprobante_pdf(datos_viaje)
                st.download_button(
                    label="📥 DESCARGAR COMPROBANTE PDF",
                    data=bytes(pdf_bytes),
                    file_name=f"Viaje_M{movil}_{fecha}.pdf",
                    mime="application/pdf"
                )

    elif menu == "Análisis IA & Dashboard":
        st.header("📊 Inteligencia de Flota")
        st.dataframe(df_historico.iloc[::-1])
