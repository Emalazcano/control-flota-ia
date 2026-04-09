import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import time
import plotly.express as px
from sklearn.ensemble import IsolationForest

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Control de Flota Inteligente", layout="wide")

# --- CONEXIÓN A GOOGLE SHEETS ---
# ⚠️ REEMPLAZA CON TU URL DE GOOGLE SHEETS ⚠️
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

# --- FUNCIÓN DE LOGIN ---
def check_password():
    if "password_correct" not in st.session_state:
        st.title("🔐 Acceso Sistema de Flota")
        st.text_input("Usuario", key="username")
        st.text_input("Contraseña", type="password", key="password")
        if st.button("Ingresar"):
            usuarios_validos = {
                "ema_admin": "jujuy2024",
                "operador": "flota123"
            }
            user = st.session_state["username"]
            pwd = st.session_state["password"]
            
            if user in usuarios_validos and usuarios_validos[user] == pwd:
                st.session_state["password_correct"] = True
                st.session_state["user_role"] = "admin" if user == "ema_admin" else "operador"
                st.rerun()
            else:
                st.error("😕 Usuario o contraseña incorrectos")
        return False
    return True

# --- INICIO DEL PROGRAMA PRINCIPAL ---
if check_password():
    # 1. Carga de datos inicial
    df_choferes = cargar_choferes()
    df_historico = obtener_datos()
    role = st.session_state.get("user_role", "operador")
    user_logueado = st.session_state["username"].upper()

    # 2. Sidebar de Configuración y Navegación
    st.sidebar.success(f"👤 USUARIO: {user_logueado}")
    
    st.sidebar.title("💰 Costos")
    precio_litro = st.sidebar.number_input("Precio Litro Gasoil ($)", min_value=0.0, value=1100.0)
    
    st.sidebar.markdown("---")
    
    # Definir opciones de menú según el ROL
    if role == "admin":
        menu_options = ["Cargar Combustible", "Calculadora de Flete (IA)", "Análisis IA & Dashboard"]
    else:
        menu_options = ["Cargar Combustible"]
    
    # ÚNICO SELECTBOX DE MENÚ (Evita el error de duplicado)
    menu = st.sidebar.selectbox("Menú Principal", menu_options, key="menu_unico")

    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Cerrar Sesión"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    # --- LÓGICA DE CONTENIDO ---
    
    if menu == "Cargar Combustible":
        st.header("⛽ Registro de Carga")
        movil_seleccionado = st.selectbox("Número de Móvil", list(range(1, 101)))
        
        km_sugerido = 0
        if not df_historico.empty and "Movil" in df_historico.columns:
            ultimo = df_historico[df_historico["Movil"] == movil_seleccionado]
            if not ultimo.empty:
                km_sugerido = ultimo["KM_Fin"].iloc[-1]
                st.info(f"💡 KM Inicial sugerido: {km_sugerido}")

        with st.form("form_carga"):
            col1, col2 = st.columns(2)
            with col1:
                fecha = st.date_input("Fecha", datetime.now())
                chofer = st.selectbox("Chofer", df_choferes["Nombre"].unique())
                marca = st.radio("Marca", ["Scania", "Mercedes"])
                ruta = st.radio("Tipo de Ruta", ["Llano", "Alta Montaña"])
                traza = st.text_input("Traza (Origen - Destino)")
            with col2:
                km_ini = st.number_input("KM Inicial", min_value=0, value=int(km_sugerido))
                km_fin = st.number_input("KM Final", min_value=0)
                l_tablero = st.number_input("Litros Tablero", min_value=0.0)
                l_ralenti = st.number_input("Litros Ralentí", min_value=0.0)
                l_ticket = st.number_input("Litros Ticket", min_value=0.0)
            
            btn_guardar = st.form_submit_button("💾 GUARDAR REGISTRO")

        if btn_guardar:
            if km_fin <= km_ini:
                st.error("❌ El KM Final debe ser mayor al Inicial.")
            else:
                km_recorr = km_fin - km_ini
                consumo = (l_ticket / km_recorr * 100) if km_recorr > 0 else 0
                desvio = l_ticket - (l_tablero + l_ralenti)
                costo_total = l_ticket * precio_litro
                costo_ralenti = l_ralenti * precio_litro
                
                nuevo = pd.DataFrame([{
                    "Fecha": str(fecha), "Chofer": chofer, "Movil": movil_seleccionado,
                    "Marca": marca, "Ruta": ruta, "Traza": traza, "KM_Ini": km_ini,
                    "KM_Fin": km_fin, "KM_Recorr": km_recorr, "L_Tablero": l_tablero,
                    "L_Ralenti": l_ralenti, "L_Ticket": l_ticket, 
                    "Desvio_Neto": round(desvio, 2), "Consumo_L100": round(consumo, 2),
                    "Costo_Viaje_ARS": round(costo_total, 2), "Costo_Ralenti_ARS": round(costo_ralenti, 2)
                }])
                
                try:
                    df_final = pd.concat([df_historico, nuevo], ignore_index=True)
                    conn.update(spreadsheet=SPREADSHEET_URL, data=df_final)
                    st.success("✅ ¡Guardado Correctamente!")
                    time.sleep(1); st.rerun()
                except Exception as e:
                    if "200" in str(e): st.success("✅ Sincronizado"); time.sleep(1); st.rerun()
                    else: st.error(f"Error: {e}")

    elif menu == "Calculadora de Flete (IA)":
        st.header("🚚 Presupuestador de Flete")
        if not df_historico.empty:
            col1, col2 = st.columns(2)
            with col1:
                c_marca = st.selectbox("Marca del Camión", ["Scania", "Mercedes"])
                c_ruta = st.selectbox("Tipo de Ruta", ["Llano", "Alta Montaña"])
                c_distancia = st.number_input("Distancia a recorrer (KM)", min_value=1, value=100)
                margen = st.slider("Margen Seguridad (%)", 0, 20, 5)
            
            filtro = df_historico[(df_historico['Marca'] == c_marca) & (df_historico['Ruta'] == c_ruta)]
            if not filtro.empty:
                cons_medio = filtro['Consumo_L100'].mean()
                l_estimados = (cons_medio * c_distancia / 100) * (1 + margen/100)
                costo_est = l_estimados * precio_litro
                with col2:
                    st.metric("Costo Estimado Gasoil", f"${costo_est:,.2f}")
                    st.metric("Litros Necesarios", f"{round(l_estimados, 1)} L")
            else:
                st.warning("No hay datos históricos para esta ruta.")

    elif menu == "Análisis IA & Dashboard":
        st.header("📊 Inteligencia de Flota")
        if not df_historico.empty:
            # IA Anomalías
            if len(df_historico) > 5:
                data_ia = df_historico[['Consumo_L100', 'Desvio_Neto']].fillna(0)
                modelo = IsolationForest(contamination=0.1, random_state=42)
                df_historico['IA_Status'] = modelo.fit_predict(data_ia)
                anomalias = df_historico[df_historico['IA_Status'] == -1]
                if not anomalias.empty:
                    st.warning(f"🚨 Se detectaron {len(anomalias)} anomalías en los registros.")
                    st.dataframe(anomalias[['Fecha', 'Chofer', 'Movil', 'Consumo_L100', 'Desvio_Neto']])

            # Dinero Perdido
            st.subheader("📉 Dinero Perdido por Ralentí")
            fig_money = px.bar(df_historico.groupby("Chofer")["Costo_Ralenti_ARS"].sum().reset_index(), 
                               x="Chofer", y="Costo_Ralenti_ARS", color="Costo_Ralenti_ARS",
                               title="Pesos perdidos por motor encendido en espera")
            st.plotly_chart(fig_money, use_container_width=True)
            
            # Tabla histórica
            st.subheader("📝 Historial")
            st.dataframe(df_historico.iloc[::-1])
