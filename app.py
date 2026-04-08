import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Control de Flota IA", layout="wide")

# --- CONEXIÓN A GOOGLE SHEETS ---
# ⚠️ PEGA AQUÍ TU URL DE GOOGLE SHEETS ⚠️
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1nYPxt2jq_imanFjE9JH5uhqWn5c2dRmixhhkSP9jZNc/edit?gid=0#gid=0"

conn = st.connection("gsheets", type=GSheetsConnection)

def obtener_datos():
    try:
        # ttl=0 obliga a leer datos frescos de Google en cada carga
        return conn.read(spreadsheet=SPREADSHEET_URL, ttl=0)
    except Exception as e:
        st.error(f"Error al leer Google Sheets: {e}")
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
    
    # El formulario agrupa los campos y el botón
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
            l_ralenti = st.number_input("Litros Ralentí (Vigía)", min_value=0.0)
            l_ticket = st.number_input("Litros según Ticket", min_value=0.0)
        
        # El botón de envío DEBE estar dentro del bloque "with st.form"
        btn_guardar = st.form_submit_button("💾 GUARDAR REGISTRO")

    # La lógica de guardado se ejecuta solo si se presionó el botón
    if btn_guardar:
        if km_fin <= km_ini:
            st.error("❌ El KM Final debe ser mayor al Inicial.")
        elif l_ticket <= 0:
            st.error("❌ Los litros deben ser mayores a 0.")
        else:
            # Cálculos automáticos
            km_recorr = km_fin - km_ini
            consumo = (l_ticket / km_recorr * 100) if km_recorr > 0 else 0
            
            # Preparar la nueva fila
            nuevo_registro = pd.DataFrame([{
                "Fecha": str(fecha),
                "Chofer": chofer,
                "Movil": movil,
                "Ruta": ruta,
                "Traza": traza,
                "KM_Ini": km_ini,
                "KM_Fin": km_fin,
                "KM_Recorr": km_recorr,
                "L_Ralenti": l_ralenti,
                "L_Ticket": l_ticket,
                "Consumo_L100": round(consumo, 2)
            }])

            # Leer datos actuales y anexar el nuevo
            df_historico = obtener_datos()
            df_final = pd.concat([df_historico, nuevo_registro], ignore_index=True)
            
            # Subir a Google Sheets
            try:
                conn.update(spreadsheet=SPREADSHEET_URL, data=df_final)
                st.success("✅ ¡Registro sincronizado con Google Sheets con éxito!")
                st.balloons()
            except Exception as e:
                st.error(f"Error al guardar: {e}. Revisa que la hoja sea pública para edición.")

elif menu == "Dashboard Histórico":
    st.header("📊 Datos Registrados")
    df_ver = obtener_datos()
    
    if not df_ver.empty:
        st.write(f"Total de registros: {len(df_ver)}")
        st.dataframe(df_ver.sort_index(ascending=False)) # Muestra los más nuevos arriba
        
        # Gráfico rápido de consumo
        if "Consumo_L100" in df_ver.columns:
            st.subheader("Promedio de Consumo por Ruta")
            promedios = df_ver.groupby("Ruta")["Consumo_L100"].mean()
            st.bar_chart(promedios)
    else:
        st.info("Aún no hay datos en Google Sheets. Carga el primer registro.")     
