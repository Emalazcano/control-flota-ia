import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import time
import plotly.express as px
from fpdf import FPDF
import os

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Control de Flota IA - Jujuy", layout="wide")

# Conexión a Google Sheets
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1PEH7lbtoq_oAHwom0O5YYYskFm6ALJ6LCj1FfQKzpmQ/edit?gid=0#gid=0"
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 2. FUNCIONES ---

def obtener_datos_sheets():
    try:
        return conn.read(spreadsheet=SPREADSHEET_URL, ttl=0)
    except:
        return pd.DataFrame()

@st.cache_data
def obtener_choferes_locales():
    archivo = "choferes.xlsx" # Archivo en tu repositorio
    if os.path.exists(archivo):
        try:
            df = pd.read_excel(archivo)
            col = "Chofer" if "Chofer" in df.columns else df.columns[0]
            return sorted(df[col].dropna().unique().tolist())
        except: pass
    return ["Cargar choferes en el Excel"]

def generar_comprobante_pdf(datos):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 15, "COMPROBANTE DE VIAJE", ln=True, align="C")
    pdf.ln(10)
    pdf.set_font("Arial", size=11)
    for clave, valor in datos.items():
        pdf.cell(50, 8, f"{clave}:", border="B")
        pdf.cell(0, 8, f" {valor}", border="B", ln=True)
    return pdf.output()

def check_password():
    if "password_correct" not in st.session_state:
        st.title("🔐 Acceso Sistema de Flota")
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.button("Ingresar"):
            if u == "ema_admin" and p == "jujuy2024":
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
        return False
    return True

# --- 3. PROGRAMA PRINCIPAL ---

if check_password():
    df_historico = obtener_datos_sheets()
    lista_choferes = obtener_choferes_locales()
    
    # Unificación de trazas [extraídas del historial en Sheets]
    lista_trazas = []
    if not df_historico.empty and "Traza" in df_historico.columns:
        trazas_sucias = df_historico["Traza"].dropna().astype(str).str.strip().str.upper()
        lista_trazas = sorted(trazas_sucias.unique().tolist())
    lista_trazas.append("+ Agregar Nueva Traza")

    st.sidebar.success("👤 SESIÓN INICIADA")
    precio_litro = st.sidebar.number_input("Precio Litro Gasoil ($)", value=1100.0)
    menu = st.sidebar.selectbox("Menú", ["Cargar Combustible", "Análisis IA & Dashboard"])

    if menu == "Cargar Combustible":
        st.header("⛽ Registro de Carga")
        movil_sel = st.selectbox("Móvil", list(range(1, 101)))
        
        with st.form("form_carga", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                fecha = st.date_input("Fecha", datetime.now())
                chofer_sel = st.selectbox("Chofer", lista_choferes)
                marca = st.radio("Marca", ["SCANIA", "MERCEDES BENZ"])
                ruta_tipo = st.radio("Ruta", ["Llano", "Alta Montaña"])
                
                traza_sel = st.selectbox("Seleccionar Traza", lista_trazas)
                traza_nueva = st.text_input("O nueva Traza (Mayúsculas)")
                traza_final = traza_nueva.strip().upper() if traza_nueva else (traza_sel if traza_sel != "+ Agregar Nueva Traza" else "")

            with col2:
                km_ini = st.number_input("KM Inicial", min_value=0)
                km_fin = st.number_input("KM Final", min_value=0)
                l_ticket = st.number_input("Litros Ticket", min_value=0.0)
                l_tablero = st.number_input("Litros Tablero", min_value=0.0)
                l_ralenti = st.number_input("Litros Ralentí (Vigía)", min_value=0.0)
            
            btn_guardar = st.form_submit_button("💾 GUARDAR")

        if btn_guardar:
            if km_fin <= km_ini:
                st.error("❌ El KM final debe ser mayor.")
            else:
                # CÁLCULOS CRÍTICOS
                km_recorr = km_fin - km_ini
                consumo = (l_ticket / km_recorr * 100) if km_recorr > 0 else 0
                desvio = l_ticket - (l_tablero + l_ralenti)
                
                datos_viaje = {
                    "Fecha": fecha.strftime('%d/%m/%Y'),
                    "Chofer": chofer_sel,
                    "Movil": movil_sel,
                    "Marca": marca,
                    "Ruta": ruta_tipo,
                    "Traza": traza_final,
                    "KM_Ini": km_ini,
                    "KM_Fin": km_fin,
                    "KM_Recorr": km_recorr,
                    "L_Ticket": l_ticket,
                    "L_Tablero": l_tablero,        # Se asegura el envío
                    "L_Ralenti": l_ralenti,        # Se asegura el envío
                    "Desvio_Neto": round(desvio, 2), # Se asegura el envío
                    "Consumo_L100": round(consumo, 2),
                    "Costo_Total_ARS": round(l_ticket * precio_litro, 2),
                    "Costo_Ralenti_ARS": round(l_ralenti * precio_litro, 2)
                }
                
                try:
                    df_final = pd.concat([df_historico, pd.DataFrame([datos_viaje])], ignore_index=True)
                    conn.update(spreadsheet=SPREADSHEET_URL, data=df_final)
                    st.success("✅ Guardado exitoso.")
                    st.download_button("📥 PDF", data=bytes(generar_comprobante_pdf(datos_viaje)), file_name="Viaje.pdf")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    elif menu == "Análisis IA & Dashboard":
        st.header("📊 Inteligencia de Flota")
        if not df_historico.empty:
            m1, m2, m3 = st.columns(3)
            m1.metric("Gasto Total", f"$ {df_historico['Costo_Total_ARS'].sum():,.0f}")
            m2.metric("Total Litros", f"{df_historico['L_Ticket'].sum():,.0f} L")
            m3.metric("Pérdida Ralentí", f"$ {df_historico['Costo_Ralenti_ARS'].sum():,.0f}")

            st.subheader("📉 Ralentí por Chofer")
            fig = px.bar(df_historico, x="Chofer", y="Costo_Ralenti_ARS", color="Marca", template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

            st.subheader("📝 Historial Completo")
            st.dataframe(df_historico.iloc[::-1], use_container_width=True)
