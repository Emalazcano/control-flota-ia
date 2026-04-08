import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Control de Flota IA", layout="wide")
SPREADSHEET_URL = "TU_LINK_DE_GOOGLE_SHEETS_AQUI"
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
        return pd.DataFrame({"Nombre": ["Cargar choferes.xlsx"]})

df_choferes = cargar_choferes()
df_historico = obtener_datos()

# --- INTERFAZ ---
st.title("🚛 Control de Flota - Sincronizado")

menu = st.sidebar.selectbox("Menú", ["Cargar Combustible", "Dashboard Histórico"])

if menu == "Cargar Combustible":
    st.header("⛽ Registro de Carga")
    
    # 1. Selección de Móvil primero para poder buscar su KM
    movil_seleccionado = st.number_input("Número de Móvil", min_value=1, step=1, value=1)
    
    # 2. Lógica para buscar el último KM de ese móvil
    km_sugerido = 0
    if not df_historico.empty and "Movil" in df_historico.columns:
        # Filtramos por el móvil y traemos el último registro
        ultimo_registro_movil = df_historico[df_historico["Movil"] == movil_seleccionado]
        if not ultimo_registro_movil.empty:
            km_sugerido = ultimo_registro_movil["KM_Fin"].iloc[-1]
            st.info(f"💡 KM Inicial sugerido según último viaje del móvil {movil_seleccionado}: {km_sugerido}")

    with st.form("form_carga"):
        col1, col2 = st.columns(2)
        with col1:
            fecha = st.date_input("Fecha", datetime.now())
            chofer = st.selectbox("Chofer", df_choferes["Nombre"].unique())
            # El móvil ya lo seleccionamos arriba, lo pasamos como dato oculto o informativo
            ruta = st.radio("Tipo de Ruta", ["Llano", "Alta Montaña"])
            traza = st.text_input("Traza (Origen - Destino)")
        with col2:
            # USAMOS EL KM SUGERIDO AQUÍ
            km_ini = st.number_input("KM Inicial", min_value=0, value=int(km_sugerido))
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

            df_final = pd.concat([df_historico, nuevo_registro], ignore_index=True)
            
            try:
                conn.update(spreadsheet=SPREADSHEET_URL, data=df_final)
                st.success(f"✅ ¡Guardado! El móvil {movil_seleccionado} cerró con {km_fin} KM.")
                st.balloons()
                st.rerun() # Recarga la app para actualizar el KM sugerido en el próximo uso
            except Exception as e:
                st.error(f"Error: {e}")

elif menu == "Dashboard Histórico":
    st.header("📊 Datos Registrados")
    if not df_historico.empty:
        st.dataframe(df_historico.sort_index(ascending=False))
    else:
        st.info("No hay datos aún.")
