import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Control de Flota IA", layout="wide")

# --- CONEXIÓN A GOOGLE SHEETS ---
# ⚠️ PEGA AQUÍ TU URL DE GOOGLE SHEETS ⚠️
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1PEH7lbtoq_oAHwom0O5YYYskFm6ALJ6LCj1FfQKzpmQ/edit?gid=0#gid=0"

conn = st.connection("gsheets", type=GSheetsConnection)

def obtener_datos():
    try:
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

# --- INTERFAZ PRINCIPAL ---
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
            l_tablero = st.number_input("Litros de Tablero", min_value=0.0) # REINCORPORADO
            l_ralenti = st.number_input("Litros Ralentí (Vigía)", min_value=0.0)
            l_ticket = st.number_input("Litros según Ticket", min_value=0.0)
        
        btn_guardar = st.form_submit_button("💾 GUARDAR REGISTRO")

    if btn_guardar:
        if km_fin <= km_ini:
            st.error("❌ El KM Final debe ser mayor al Inicial.")
        elif l_ticket <= 0:
            st.error("❌ Los litros de ticket deben ser mayores a 0.")
        else:
            km_recorr = km_fin - km_ini
            consumo = (l_ticket / km_recorr * 100) if km_recorr > 0 else 0
            # Diferencia entre lo que dice el camión y el surtidor
            dif_tablero_ticket = l_ticket - l_tablero
            
            nuevo_registro = pd.DataFrame([{
                "Fecha": str(fecha),
                "Chofer": chofer,
                "Movil": movil,
                "Ruta": ruta,
                "Traza": traza,
                "KM_Ini": km_ini,
                "KM_Fin": km_fin,
                "KM_Recorr": km_recorr,
                "L_Tablero": l_tablero, # GUARDADO
                "L_Ralenti": l_ralenti,
                "L_Ticket": l_ticket,
                "Dif_Surtidor_vs_Tablero": round(dif_tablero_ticket, 2),
                "Consumo_L100": round(consumo, 2)
            }])

            df_historico = obtener_datos()
            df_final = pd.concat([df_historico, nuevo_registro], ignore_index=True)
            
            try:
                conn.update(spreadsheet=SPREADSHEET_URL, data=df_final)
                st.success("✅ Registro guardado. Diferencia detectada: " + str(round(dif_tablero_ticket, 2)) + " L.")
                st.balloons()
            except Exception as e:
                st.error(f"Error al guardar: {e}")

elif menu == "Dashboard Histórico":
    st.header("📊 Datos Registrados")
    df_ver = obtener_datos()
    
    if not df_ver.empty:
        st.dataframe(df_ver.sort_index(ascending=False))
        
        if "Consumo_L100" in df_ver.columns:
            st.subheader("Análisis de Consumo")
            st.line_chart(df_ver.set_index("Fecha")["Consumo_L100"])
    else:
        st.info("No hay datos aún.")
