import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import time
import plotly.express as px
from sklearn.ensemble import IsolationForest
from fpdf import FPDF # <-- Nueva librería

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Control de Flota IA", layout="wide")

# --- CONEXIÓN ---
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1PEH7lbtoq_oAHwom0O5YYYskFm6ALJ6LCj1FfQKzpmQ/edit?gid=0#gid=0"
conn = st.connection("gsheets", type=GSheetsConnection)

# --- FUNCIÓN PARA GENERAR EL PDF ---
def generar_comprobante_pdf(datos):
    pdf = FPDF()
    pdf.add_page()
    
    # Estética del PDF
    pdf.set_fill_color(230, 230, 230)
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 15, "COMPROBANTE DE CARGA - CONTROL DE FLOTA", ln=True, align="C", fill=True)
    pdf.ln(10)
    
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, f"Detalle del Viaje - Móvil {datos['Movil']}", ln=True)
    pdf.line(10, 35, 200, 35)
    pdf.ln(5)
    
    # Tabla de datos
    pdf.set_font("Arial", size=11)
    for clave, valor in datos.items():
        pdf.set_font("Arial", "B", 11)
        pdf.cell(50, 8, f"{clave}:", border="B")
        pdf.set_font("Arial", size=11)
        pdf.cell(0, 8, f" {valor}", border="B", ln=True)
    
    pdf.ln(20)
    pdf.set_font("Arial", "I", 9)
    pdf.cell(0, 10, f"Documento generado automáticamente el {datetime.now().strftime('%d/%m/%Y %H:%M')}", align="C")
    
    return pdf.output()

# ... (Funciones check_password y obtener_datos se mantienen igual) ...

if check_password():
    df_historico = conn.read(spreadsheet=SPREADSHEET_URL, ttl=0)
    role = st.session_state.get("user_role", "operador")
    
    # ... (Sidebar y Menú se mantienen igual) ...
    menu = st.sidebar.selectbox("Menú Principal", ["Cargar Combustible", "Análisis IA & Dashboard"], key="menu_unico")

    if menu == "Cargar Combustible":
        st.header("⛽ Registro de Carga")
        # (Formulario de carga igual al anterior...)
        
        with st.form("form_carga"):
            # ... (inputs de fecha, chofer, marca, km, litros...)
            btn_guardar = st.form_submit_button("💾 GUARDAR Y GENERAR PDF")

        if btn_guardar:
            # Lógica de cálculos (consumo, desvio, costo...)
            km_recorr = km_fin - km_ini
            consumo = (l_ticket / km_recorr * 100) if km_recorr > 0 else 0
            costo_total = l_ticket * precio_litro
            
            # 1. Guardar en Google Sheets
            nuevo_reg = {
                "Fecha": str(fecha), "Chofer": chofer, "Movil": movil_seleccionado,
                "Marca": marca, "Ruta": ruta, "KM_Recorr": km_recorr,
                "Consumo_L100": round(consumo, 2), "Costo_Total": round(costo_total, 2)
            }
            # (Aquí va el código de conn.update...)
            
            # 2. Preparar datos para el PDF
            datos_pdf = {
                "Fecha": str(fecha),
                "Chofer": chofer,
                "Movil": movil_seleccionado,
                "Marca": marca,
                "Ruta": ruta,
                "Traza": traza,
                "KM Recorridos": f"{km_recorr} km",
                "Litros Cargados": f"{l_ticket} L",
                "Consumo Promedio": f"{round(consumo, 2)} L/100km",
                "Costo Combustible": f"${costo_total:,.2f}"
            }
            
            pdf_bytes = generar_comprobante_pdf(datos_pdf)
            
            st.success("✅ Datos guardados en la nube.")
            
            # 3. Botón de descarga (Aparece solo tras el éxito)
            st.download_button(
                label="📥 DESCARGAR COMPROBANTE PDF",
                data=bytes(pdf_bytes),
                file_name=f"Viaje_M{movil_seleccionado}_{fecha}.pdf",
                mime="application/pdf"
            )

    elif menu == "Análisis IA & Dashboard":
        st.header("📊 Historial de Viajes")
        # Aquí también podemos agregar la opción de descargar viajes viejos
        st.write("Seleccione un viaje del historial para descargar su PDF:")
        if not df_historico.empty:
            fila_idx = st.selectbox("Seleccionar viaje (por fecha/móvil)", df_historico.index)
            viaje = df_historico.loc[fila_idx].to_dict()
            
            pdf_reimpresion = generar_comprobante_pdf(viaje)
            st.download_button(
                label="🖨️ Re-imprimir PDF Seleccionado",
                data=bytes(pdf_reimpresion),
                file_name="Reimpresion_Viaje.pdf",
                mime="application/pdf"
            )
        st.dataframe(df_historico.iloc[::-1])
