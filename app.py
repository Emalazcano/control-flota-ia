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
# ⚠️ REEMPLAZA CON TU URL DE GOOGLE SHEETS
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1PEH7lbtoq_oAHwom0O5YYYskFm6ALJ6LCj1FfQKzpmQ/edit?gid=0#gid=0"
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 3. DEFINICIÓN DE FUNCIONES ---

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
    if "password_correct" not in st.session_state:
        st.title("🔐 Acceso Sistema de Flota")
        st.text_input("Usuario", key="username", placeholder="Ej: ema_admin")
        st.text_input("Contraseña", type="password", key="password")
        if st.button("Ingresar"):
            usuarios_validos = {"ema_admin": "jujuy2024", "operador": "flota123"}
            user = st.session_state.get("username", "")
            pwd = st.session_state.get("password", "")
            if user in usuarios_validos and usuarios_validos[user] == pwd:
                st.session_state["password_correct"] = True
                st.session_state["user_role"] = "admin" if user == "ema_admin" else "operador"
                st.rerun()
            else:
                st.error("😕 Usuario o contraseña incorrectos")
        return False
    return True

# --- 4. PROGRAMA PRINCIPAL ---

if check_password():
    user_logueado = st.session_state.get("username", "ADMIN").upper()
    role = st.session_state.get("user_role", "operador")
    df_historico = obtener_datos()

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
        
        # Sugerencia de KM inicial basada en el último registro
        km_sugerido = 0
        movil_sel = st.selectbox("Móvil", list(range(1, 101)))
        if not df_historico.empty and "Movil" in df_historico.columns:
            # Aseguramos que Movil sea comparado correctamente
            ultimo = df_historico[df_historico["Movil"].astype(str) == str(movil_sel)]
            if not ultimo.empty:
                km_sugerido = ultimo["KM_Fin"].iloc[-1]
                st.info(f"💡 KM Inicial sugerido: {km_sugerido}")

        with st.form("form_carga"):
            col1, col2 = st.columns(2)
            with col1:
                fecha = st.date_input("Fecha de Carga", datetime.now())
                chofer = st.text_input("Nombre del Chofer")
                marca = st.radio("Marca", ["Scania", "Mercedes"])
                ruta = st.radio("Tipo de Ruta", ["Llano", "Alta Montaña"])
                traza = st.text_input("Traza (Origen - Destino)")
            with col2:
                km_ini = st.number_input("KM Inicial", min_value=0, value=int(km_sugerido))
                km_fin = st.number_input("KM Final", min_value=0)
                l_ticket = st.number_input("Litros Ticket (Carga Real)", min_value=0.0)
                l_tablero = st.number_input("Litros Tablero (Consumidos)", min_value=0.0)
                l_ralenti = st.number_input("Litros Ralentí (Vigía)", min_value=0.0)
            
            btn_guardar = st.form_submit_button("💾 GUARDAR Y GENERAR PDF")

        if btn_guardar:
            if km_fin <= km_ini:
                st.error("❌ El KM Final debe ser mayor al Inicial.")
            elif l_ticket <= 0:
                st.error("❌ Los litros deben ser mayores a 0.")
            else:
                km_recorr = km_fin - km_ini
                consumo = (l_ticket / km_recorr * 100) if km_recorr > 0 else 0
                costo_total = l_ticket * precio_litro
                costo_ralenti = l_ralenti * precio_litro
                desvio = l_ticket - (l_tablero + l_ralenti)
                
                # FORMATEO DE FECHA ARGENTINA PARA EL PDF Y EXCEL
                fecha_arg = fecha.strftime('%d/%m/%Y')
                
                datos_viaje = {
                    "Fecha": fecha_arg, 
                    "Chofer": chofer, 
                    "Movil": movil_sel,
                    "Marca": marca, 
                    "Ruta": ruta, 
                    "Traza": traza,
                    "KM_Ini": km_ini,
                    "KM_Fin": km_fin,
                    "KM_Recorr": km_recorr, 
                    "L_Ticket": l_ticket,
                    "Consumo_L100": round(consumo, 2), 
                    "Costo_Total_ARS": round(costo_total, 2),
                    "Costo_Ralenti_ARS": round(costo_ralenti, 2),
                    "Desvio_Neto": round(desvio, 2)
                }
                
                try:
                    # Sincronización con Google Sheets
                    nuevo_df = pd.DataFrame([datos_viaje])
                    df_final = pd.concat([df_historico, nuevo_df], ignore_index=True)
                    conn.update(spreadsheet=SPREADSHEET_URL, data=df_final)
                    st.success(f"✅ Registro guardado. Costo: ${costo_total:,.2f}")
                    
                    # Generar PDF con los mismos datos
                    pdf_bytes = generar_comprobante_pdf(datos_viaje)
                    st.download_button(
                        label="📥 DESCARGAR COMPROBANTE PDF",
                        data=bytes(pdf_bytes),
                        file_name=f"Viaje_M{movil_sel}_{fecha_arg.replace('/','-')}.pdf",
                        mime="application/pdf"
                    )
                except Exception as e:
                    if "200" in str(e): st.success("✅ Sincronizado correctamente")
                    else: st.error(f"Error al guardar: {e}")

    elif menu == "Análisis IA & Dashboard":
        st.header("📊 Inteligencia de Flota y Costos")
        if not df_historico.empty:
            # Gráfico de Dinero Perdido (Ralentí)
            st.subheader("📉 Dinero Perdido por Ralentí")
            fig = px.bar(df_historico, x="Chofer", y="Costo_Ralenti_ARS", color="Marca", 
                         title="Pesos malgastados por motor encendido en espera")
            st.plotly_chart(fig, use_container_width=True)
            
            # Tabla Histórica con fecha formateada
            st.subheader("📝 Historial de Registros")
            st.dataframe(df_historico.iloc[::-1])
        else:
            st.info("No hay datos históricos para mostrar aún.")
