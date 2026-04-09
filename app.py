   import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import time
import plotly.express as px
from fpdf import FPDF
import os

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Control de Flota IA - Jujuy", layout="wide")

# --- 2. CONEXIÓN A GOOGLE SHEETS ---
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1PEH7lbtoq_oAHwom0O5YYYskFm6ALJ6LCj1FfQKzpmQ/edit?gid=0#gid=0"
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 3. DEFINICIÓN DE FUNCIONES ---

def obtener_datos_sheets():
    try:
        return conn.read(spreadsheet=SPREADSHEET_URL, ttl=0)
    except:
        return pd.DataFrame()

@st.cache_data
def obtener_choferes_locales():
    archivo = "choferes.xlsx"
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
                st.session_state["user_role"] = "admin"
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos")
        return False
    return True

# --- 4. PROGRAMA PRINCIPAL ---

if check_password():
    df_historico = obtener_datos_sheets()
    lista_choferes = obtener_choferes_locales()
    
    # --- LÓGICA DE UNIFICACIÓN DE TRAZAS ---
    lista_trazas = []
    if not df_historico.empty and "Traza" in df_historico.columns:
        # Limpiamos espacios y pasamos a mayúsculas para unificar
        trazas_sucias = df_historico["Traza"].dropna().astype(str).str.strip().str.upper()
        lista_trazas = sorted(trazas_sucias.unique().tolist())
    
    lista_trazas.append("+ Agregar Nueva Traza")

    # SIDEBAR
    st.sidebar.success(f"👤 ADMIN")
    precio_litro = st.sidebar.number_input("Precio Litro ($)", value=1100.0)
    menu = st.sidebar.selectbox("Menú", ["Cargar Combustible", "Análisis IA & Dashboard"])

    if menu == "Cargar Combustible":
        st.header("⛽ Registro de Carga")
        
        movil_sel = st.selectbox("Móvil", list(range(1, 101)))
        
        with st.form("form_carga", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                fecha = st.date_input("Fecha", datetime.now(), format="DD/MM/YYYY")
                chofer_sel = st.selectbox("Chofer", lista_choferes)
                marca = st.radio("Marca", ["SCANIA", "MERCEDES BENZ"])
                ruta_tipo = st.radio("Tipo de Ruta", ["Llano", "Alta Montaña"])
                
                # --- SELECTOR DE TRAZA UNIFICADA ---
                traza_sel = st.selectbox("Seleccionar Traza Existente", lista_trazas)
                traza_nueva = st.text_input("O escribir Traza Nueva (Ej: SSJJ-OLAR-SSJJ)")
                # Si escribió algo en Traza Nueva, usamos eso. Si no, lo del selector.
                traza_final = traza_nueva.strip().upper() if traza_nueva else (traza_sel if traza_sel != "+ Agregar Nueva Traza" else "")

            with col2:
                km_ini = st.number_input("KM Inicial", min_value=0)
                km_fin = st.number_input("KM Final", min_value=0)
                l_ticket = st.number_input("Litros Ticket", min_value=0.0)
                l_tablero = st.number_input("Litros Tablero", min_value=0.0)
                l_ralenti = st.number_input("Litros Ralentí", min_value=0.0)
            
            btn_guardar = st.form_submit_button("💾 GUARDAR")

        if btn_guardar:
            if not traza_final:
                st.error("❌ Por favor, definí una Traza.")
            elif km_fin <= km_ini:
                st.error("❌ KM Final debe ser mayor.")
            else:
                km_recorr = km_fin - km_ini
                datos_viaje = {
                    "Fecha": fecha.strftime('%d/%m/%Y'), "Chofer": chofer_sel, "Movil": movil_sel,
                    "Marca": marca, "Ruta": ruta_tipo, "Traza": traza_final,
                    "KM_Ini": km_ini, "KM_Fin": km_fin, "KM_Recorr": km_recorr, 
                    "L_Ticket": l_ticket, "Consumo_L100": round((l_ticket/km_recorr*100 if km_recorr>0 else 0), 2), 
                    "Costo_Total_ARS": round(l_ticket * precio_litro, 2),
                    "Costo_Ralenti_ARS": round(l_ralenti * precio_litro, 2)
                }
                
                try:
                    df_final = pd.concat([df_historico, pd.DataFrame([datos_viaje])], ignore_index=True)
                    conn.update(spreadsheet=SPREADSHEET_URL, data=df_final)
                    st.success(f"✅ Guardado. Traza '{traza_final}' registrada.")
                    st.download_button("📥 Descargar PDF", data=bytes(generar_comprobante_pdf(datos_viaje)), file_name="Viaje.pdf")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    elif menu == "Análisis IA & Dashboard":
        st.header("📊 Inteligencia de Flota")
        if not df_historico.empty:
            # Métricas
            c1, c2, c3 = st.columns(3)
            c1.metric("Gasto Total", f"$ {df_historico['Costo_Total_ARS'].sum():,.0f}")
            c2.metric("Total Litros", f"{df_historico['L_Ticket'].sum():,.0f} L")
            c3.metric("Pérdida Ralentí", f"$ {df_historico['Costo_Ralenti_ARS'].sum():,.0f}")

            # Gráfico unificado por traza
            st.subheader("⛽ Consumo Promedio por Traza")
            # Agrupamos por traza para ver cuál consume más
            df_traza = df_historico.groupby("Traza")["Consumo_L100"].mean().reset_index()
            fig = px.bar(df_traza, x="Traza", y="Consumo_L100", template="plotly_dark", color="Traza")
            st.plotly_chart(fig, use_container_width=True)

            st.subheader("📝 Historial")
            st.dataframe(df_historico.iloc[::-1], use_container_width=True)
