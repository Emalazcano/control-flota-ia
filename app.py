import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Control de Flota IA", layout="wide")

# --- CONEXIÓN A GOOGLE SHEETS ---
# Aquí solo dejamos la URL. La "llave" la saca sola de los Secrets de Streamlit
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1PEH7lbtoq_oAHwom0O5YYYskFm6ALJ6LCj1FfQKzpmQ/edit?gid=0#gid=0"

# Esta línea busca automáticamente los Secrets que pegaste (el JSON)
conn = st.connection("gsheets", type=GSheetsConnection)

def obtener_datos():
    try:
        # Aquí es donde 'conn.read' entra en acción
        return conn.read(spreadsheet=SPREADSHEET_URL, ttl=0)
    except Exception as e:
        return pd.DataFrame()

# --- CARGA DE CHOFERES ---
@st.cache_data
def cargar_choferes():
    try:
        return pd.read_excel("choferes.xlsx")
    except:
        return pd.DataFrame({"Nombre": ["Cargar choferes.xlsx en GitHub"]})

df_choferes = cargar_choferes()

# --- INTERFAZ ---
st.title("🚛 Control de Flota - Sincronizado")

menu = st.sidebar.selectbox("Menú", ["Cargar Combustible", "Dashboard Histórico"])

if menu == "Cargar Combustible":
    st.header("⛽ Registro de Carga")
    
    with st.form("form_carga"):
        col1, col2 = st.columns(2)
        with col1:
            fecha = st.date_input("Fecha", datetime.now())
            chofer = st.selectbox("Chofer", df_choferes["Nombre"].unique())
            movil = st.number_input("Número de Móvil", min_value=1, step=1)
            ruta = st.radio("Tipo de Ruta", ["Llano", "Alta Montaña"])
            traza = st.text_input("Traza (Origen - Destino)")
        with col2:
            km_ini = st.number_input("KM Inicial", min_value=0)
            km_fin = st.number_input("KM Final", min_value=0)
            l_tablero = st.number_input("Litros de Tablero", min_value=0.0)
            l_ralenti = st.number_input("Litros Ralentí (Vigía)", min_value=0.0)
            l_ticket = st.number_input("Litros según Ticket", min_value=0.0)
        
        btn_guardar = st.form_submit_button("💾 GUARDAR REGISTRO")

    if btn_guardar:
        if km_fin <= km_ini:
            st.error("❌ El KM Final debe ser mayor al Inicial.")
        else:
            km_recorr = km_fin - km_ini
            consumo = (l_ticket / km_recorr * 100) if km_recorr > 0 else 0
            
            nuevo_registro = pd.DataFrame([{
                "Fecha": str(fecha),
                "Chofer": chofer,
                "Movil": movil,
                "Ruta": ruta,
                "Traza": traza,
                "KM_Ini": km_ini,
                "KM_Fin": km_fin,
                "KM_Recorr": km_recorr,
                "L_Tablero": l_tablero,
                "L_Ralenti": l_ralenti,
                "L_Ticket": l_ticket,
                "Consumo_L100": round(consumo, 2)
            }])

            # ACCIÓN: Leer datos actuales
            df_historico = obtener_datos()
            df_final = pd.concat([df_historico, nuevo_registro], ignore_index=True)
            
            # ACCIÓN: Guardar en Google (Aquí es donde 'conn.update' actúa)
            try:
                conn.update(spreadsheet=SPREADSHEET_URL, data=df_final)
                st.success("✅ ¡Guardado con éxito en Google Sheets!")
                st.balloons()
            except Exception as e:
                st.error(f"Error crítico al guardar: {e}")

elif menu == "Dashboard Histórico":
    st.header("📊 Datos Registrados")
    df_ver = obtener_datos()
    if not df_ver.empty:
        st.dataframe(df_ver.sort_index(ascending=False))
    else:
        st.info("No hay datos aún.")
