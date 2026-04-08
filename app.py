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
        # ttl=0 para que siempre traiga el último KM cargado desde la nube
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

# Cargamos los datos actuales para las sugerencias
df_choferes = cargar_choferes()
df_historico = obtener_datos()

# --- INTERFAZ ---
st.title("🚛 Control de Flota - Sincronizado")

menu = st.sidebar.selectbox("Menú", ["Cargar Combustible", "Dashboard Histórico"])

if menu == "Cargar Combustible":
    st.header("⛽ Registro de Carga")
    
    # 1. Selección de Móvil (Fuera del form para disparar la búsqueda automática)
    movil_seleccionado = st.number_input("Número de Móvil", min_value=1, step=1, value=1)
    
    # 2. Buscar último KM para este móvil
    km_sugerido = 0
    if not df_historico.empty and "Movil" in df_historico.columns:
        # Filtramos los registros de ese móvil y tomamos el último KM_Fin
        ultimo_registro_movil = df_historico[df_historico["Movil"] == movil_seleccionado]
        if not ultimo_registro_movil.empty:
            km_sugerido = ultimo_registro_movil["KM_Fin"].iloc[-1]
            st.info(f"💡 KM Inicial sugerido para el móvil {movil_seleccionado}: {km_sugerido}")

    # 3. Formulario de carga
    with st.form("form_carga"):
        col1, col2 = st.columns(2)
        with col1:
            fecha = st.date_input("Fecha", datetime.now())
            chofer = st.selectbox("Chofer", df_choferes["Nombre"].unique())
            ruta = st.radio("Tipo de Ruta", ["Llano", "Alta Montaña"])
            traza = st.text_input("Traza (Origen - Destino)")
        with col2:
            # El KM Inicial toma por defecto el km_sugerido
            km_ini = st.number_input("KM Inicial", min_value=0, value=int(km_sugerido))
            km_fin = st.number_input("KM Final", min_value=0)
            l_tablero = st.number_input("Litros de Tablero", min_value=0.0)
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
            
            # Preparar fila
            nuevo_registro = pd.DataFrame([{
                "Fecha": str(fecha),
                "Chofer": chofer,
                "Movil": movil_seleccionado,
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

            # Combinar con lo que ya existe
            df_final = pd.concat([df_historico, nuevo_registro], ignore_index=True)
            
            try:
                # Intento de guardado
                conn.update(spreadsheet=SPREADSHEET_URL, data=df_final)
                st.success(f"✅ ¡Registro guardado exitosamente!")
                st.balloons()
                time.sleep(1)
                st.rerun()
                
            except Exception as e:
                # Si el error es el código 200, lo tratamos como éxito
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
        # Mostramos los últimos viajes primero
        st.dataframe(df_ver.iloc[::-1])
    else:
        st.info("No hay datos registrados aún.")
