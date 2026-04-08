import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import time

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Control de Flota IA", layout="wide")

# --- CONEXIÓN A GOOGLE SHEETS ---
# ⚠️ REEMPLAZA CON TU URL DE GOOGLE SHEETS ⚠️
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1PEH7lbtoq_oAHwom0O5YYYskFm6ALJ6LCj1FfQKzpmQ/edit?gid=0#gid=0"

conn = st.connection("gsheets", type=GSheetsConnection)

def obtener_datos():
    try:
        return conn.read(spreadsheet=SPREADSHEET_URL, ttl=0)
    except:
        return pd.DataFrame()

# --- CARGA DE CHOFERES ---
@st.cache_data
def cargar_choferes():
    try:
        return pd.read_excel("choferes.xlsx")
    except:
        return pd.DataFrame({"Nombre": ["Cargar choferes.xlsx en GitHub"]})

df_choferes = cargar_choferes()
df_historico = obtener_datos()

# --- INTERFAZ ---
st.title("🚛 Control de Flota")

menu = st.sidebar.selectbox("Menú", ["Cargar Combustible", "Dashboard Histórico"])

if menu == "Cargar Combustible":
    st.header("⛽ Registro de Carga")
    
    # 1. Elección de Móvil (Lista del 1 al 100)
    lista_moviles = list(range(1, 101))
    movil_seleccionado = st.selectbox("Número de Móvil", lista_moviles)
    
    # 2. Buscar último KM para este móvil
    km_sugerido = 0
    if not df_historico.empty and "Movil" in df_historico.columns:
        ultimo_registro_movil = df_historico[df_historico["Movil"] == movil_seleccionado]
        if not ultimo_registro_movil.empty:
            km_sugerido = ultimo_registro_movil["KM_Fin"].iloc[-1]
            st.info(f"💡 KM Inicial sugerido para el móvil {movil_seleccionado}: {km_sugerido}")

    with st.form("form_carga"):
        col1, col2 = st.columns(2)
        with col1:
            fecha = st.date_input("Fecha", datetime.now())
            chofer = st.selectbox("Chofer", df_choferes["Nombre"].unique())
            marca = st.radio("Marca del Camión", ["Scania", "Mercedes"]) # AGREGADO
            ruta = st.radio("Tipo de Ruta", ["Llano", "Alta Montaña"])
            traza = st.text_input("Traza (Origen - Destino)")
        with col2:
            km_ini = st.number_input("KM Inicial", min_value=0, value=int(km_sugerido))
            km_fin = st.number_input("KM Final", min_value=0)
            l_tablero = st.number_input("Litros de Tablero (Canbus)", min_value=0.0)
            l_ralenti = st.number_input("Litros Ralentí (Vigía)", min_value=0.0)
            l_ticket = st.number_input("Litros según Ticket", min_value=0.0)
        
        btn_guardar = st.form_submit_button("💾 GUARDAR REGISTRO")

    if btn_guardar:
        if km_fin <= km_ini:
            st.error("❌ El KM Final debe ser mayor al Inicial.")
        elif l_ticket <= 0:
            st.error("❌ El litraje del ticket no puede ser 0.")
        else:
            # Cálculos
            km_recorr = km_fin - km_ini
            consumo = (l_ticket / km_recorr * 100) if km_recorr > 0 else 0
            
            # Cálculo del Desvío Neto (Ticket vs Tablero contemplando Ralentí)
            # Desvío = Litros Ticket - (Litros Tablero + Litros Ralentí)
            desvio_neto = l_ticket - (l_tablero + l_ralenti)
            
            nuevo_registro = pd.DataFrame([{
                "Fecha": str(fecha),
                "Chofer": chofer,
                "Movil": movil_seleccionado,
                "Marca": marca, # AGREGADO
                "Ruta": ruta,
                "Traza": traza,
                "KM_Ini": km_ini,
                "KM_Fin": km_fin,
                "KM_Recorr": km_recorr,
                "L_Tablero": l_tablero,
                "L_Ralenti": l_ralenti,
                "L_Ticket": l_ticket,
                "Desvio_Neto": round(desvio_neto, 2), # AGREGADO
                "Consumo_L100": round(consumo, 2)
            }])

            df_final = pd.concat([df_historico, nuevo_registro], ignore_index=True)
            
            try:
                conn.update(spreadsheet=SPREADSHEET_URL, data=df_final)
                st.success(f"✅ ¡Guardado! Desvío Neto detectado: {round(desvio_neto, 2)} L.")
                st.balloons()
                time.sleep(1)
                st.rerun()
                
            except Exception as e:
                if "200" in str(e):
                    st.success("✅ ¡Registro sincronizado!")
                    st.balloons()
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"Error al conectar con Google: {e}")

elif menu == "Dashboard Histórico":
    st.header("📊 Datos Registrados")
    df_ver = obtener_datos()
    if not df_ver.empty:
        st.dataframe(df_ver.iloc[::-1])
    else:
        st.info("No hay datos registrados aún.")
    if not df_ver.empty:
        # Mostramos los últimos viajes primero
        st.dataframe(df_ver.iloc[::-1])
    else:
        st.info("No hay datos registrados aún.")
