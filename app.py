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

    # SIDEBAR
    st.sidebar.success(f"👤 {user_logueado}")
    precio_litro = st.sidebar.number_input("Precio Litro Gasoil ($)", min_value=0.0, value=1100.0)
    
    opciones = ["Cargar Combustible", "Análisis IA & Dashboard"] if role == "admin" else ["Cargar Combustible"]
    menu = st.sidebar.selectbox("Menú Principal", opciones, key="menu_unico")

    if st.sidebar.button("🚪 Cerrar Sesión"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()

    if menu == "Cargar Combustible":
        st.header("⛽ Registro de Carga")
        
        # --- LÓGICA DE CHOFERES DINÁMICOS ---
        lista_choferes = []
        if not df_historico.empty and "Chofer" in df_historico.columns:
            # Obtenemos nombres únicos y quitamos vacíos
            lista_choferes = sorted(df_historico["Chofer"].dropna().unique().tolist())
        
        # Agregamos opción para ingresar uno nuevo si no está en la lista
        lista_choferes.append("+ Agregar Nuevo Chofer")

        movil_sel = st.selectbox("Móvil", list(range(1, 101)))
        
        km_sugerido = 0
        if not df_historico.empty and "Movil" in df_historico.columns:
            ultimo = df_historico[df_historico["Movil"].astype(str) == str(movil_sel)]
            if not ultimo.empty:
                km_sugerido = ultimo["KM_Fin"].iloc[-1]
                st.info(f"💡 KM Inicial sugerido: {km_sugerido}")

        with st.form("form_carga"):
            col1, col2 = st.columns(2)
            with col1:
                fecha = st.date_input("Fecha de Carga", datetime.now(), format="DD/MM/YYYY")
                
                # Selector de Chofer
                chofer_sel = st.selectbox("Chofer", lista_choferes)
                if chofer_sel == "+ Agregar Nuevo Chofer":
                    chofer_final = st.text_input("Escriba el nombre del nuevo chofer")
                else:
                    chofer_final = chofer_sel

                marca = st.radio("Marca", ["SCANIA", "MERCEDES BENZ"])
                ruta = st.radio("Tipo de Ruta", ["Llano", "Alta Montaña"])
                traza = st.text_input("Traza (Origen - Destino)")
            with col2:
                km_ini = st.number_input("KM Inicial", min_value=0, value=int(km_sugerido))
                km_fin = st.number_input("KM Final", min_value=0)
                l_ticket = st.number_input("Litros Ticket", min_value=0.0)
                l_tablero = st.number_input("Litros Tablero", min_value=0.0)
                l_ralenti = st.number_input("Litros Ralentí", min_value=0.0)
            
            btn_guardar = st.form_submit_button("💾 GUARDAR Y GENERAR PDF")

        if btn_guardar:
            if not chofer_final:
                st.error("❌ Por favor, ingrese el nombre del chofer.")
            elif km_fin <= km_ini:
                st.error("❌ El KM Final debe ser mayor.")
            else:
                km_recorr = km_fin - km_ini
                consumo = (l_ticket / km_recorr * 100) if km_recorr > 0 else 0
                costo_total = l_ticket * precio_litro
                costo_ralenti = l_ralenti * precio_litro
                desvio = l_ticket - (l_tablero + l_ralenti)
                fecha_arg = fecha.strftime('%d/%m/%Y')
                
                datos_viaje = {
                    "Fecha": fecha_arg, "Chofer": chofer_final, "Movil": movil_sel,
                    "Marca": marca, "Ruta": ruta, "Traza": traza,
                    "KM_Ini": km_ini, "KM_Fin": km_fin, "KM_Recorr": km_recorr, 
                    "L_Ticket": l_ticket, "Consumo_L100": round(consumo, 2), 
                    "Costo_Total_ARS": round(costo_total, 2),
                    "Costo_Ralenti_ARS": round(costo_ralenti, 2),
                    "Desvio_Neto": round(desvio, 2)
                }
                
                try:
                    df_final = pd.concat([df_historico, pd.DataFrame([datos_viaje])], ignore_index=True)
                    conn.update(spreadsheet=SPREADSHEET_URL, data=df_final)
                    st.success("✅ Registro guardado.")
                    pdf_bytes = generar_comprobante_pdf(datos_viaje)
                    st.download_button(label="📥 DESCARGAR PDF", data=bytes(pdf_bytes), file_name=f"Viaje_M{movil_sel}.pdf")
                    time.sleep(1)
                    st.rerun() # Recargamos para que el nuevo chofer aparezca en la lista
                except Exception as e:
                    st.error(f"Error: {e}")

    elif menu == "Análisis IA & Dashboard":
        # (El resto del código del dashboard se mantiene igual)
        st.header("📊 Inteligencia de Flota y Costos")
        if not df_historico.empty:
            for col in ["Costo_Ralenti_ARS", "Costo_Total_ARS", "L_Ticket"]:
                if col not in df_historico.columns: df_historico[col] = 0
            
            col_m1, col_m2, col_m3 = st.columns(3)
            with col_m1: st.metric("Gasto Total", f"${df_historico['Costo_Total_ARS'].sum():,.0f}")
            with col_m2: st.metric("Total Litros", f"{df_historico['L_Ticket'].sum():,.0f} L")
            with col_m3: st.metric("Pérdida Ralentí", f"${df_historico['Costo_Ralenti_ARS'].sum():,.0f}")

            st.subheader("📉 Ralentí por Chofer")
            fig_ral = px.bar(df_historico, x="Chofer", y="Costo_Ralenti_ARS", color="Marca", template="plotly_dark")
            st.plotly_chart(fig_ral, use_container_width=True)

            st.subheader("📝 Historial Completo")
            st.dataframe(df_historico.iloc[::-1], use_container_width=True)
