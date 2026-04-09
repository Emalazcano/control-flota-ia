import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import time
import plotly.express as px
from sklearn.ensemble import IsolationForest

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Control Financiero de Flota", layout="wide")
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1PEH7lbtoq_oAHwom0O5YYYskFm6ALJ6LCj1FfQKzpmQ/edit?gid=0#gid=0"
conn = st.connection("gsheets", type=GSheetsConnection)

def obtener_datos():
    try:
        return conn.read(spreadsheet=SPREADSHEET_URL, ttl=0)
    except:
        return pd.DataFrame()

df_choferes = pd.read_excel("choferes.xlsx") if "choferes.xlsx" else pd.DataFrame()
df_historico = obtener_datos()

# --- SIDEBAR: PRECIO DEL COMBUSTIBLE ---
st.sidebar.title("💰 Configuración de Costos")
precio_litro = st.sidebar.number_input("Precio Litro Gasoil ($)", min_value=0.0, value=1100.0, step=10.0)

st.sidebar.markdown("---")
menu = st.sidebar.selectbox("Menú", ["Cargar Combustible", "Calculadora de Flete (IA)", "Análisis IA & Dashboard"])

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
            chofer = st.selectbox("Chofer", df_choferes["Nombre"].unique() if not df_choferes.empty else ["Cargar excel"])
            marca = st.radio("Marca", ["Scania", "Mercedes"])
            ruta = st.radio("Tipo de Ruta", ["Llano", "Alta Montaña"])
            traza = st.text_input("Traza (Origen - Destino)")
        with col2:
            km_ini = st.number_input("KM Inicial", min_value=0, value=int(km_sugerido))
            km_fin = st.number_input("KM Final", min_value=0)
            l_tablero = st.number_input("Litros Tablero", min_value=0.0)
            l_ralenti = st.number_input("Litros Ralentí", min_value=0.0)
            l_ticket = st.number_input("Litros Ticket", min_value=0.0)
        
        if st.form_submit_button("💾 GUARDAR REGISTRO"):
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
                "Costo_Viaje_ARS": round(costo_total, 2),
                "Costo_Ralenti_ARS": round(costo_ralenti, 2)
            }])
            
            try:
                df_final = pd.concat([df_historico, nuevo], ignore_index=True)
                conn.update(spreadsheet=SPREADSHEET_URL, data=df_final)
                st.success(f"✅ ¡Guardado! Costo combustible viaje: ${costo_total:,.2f}")
                time.sleep(1); st.rerun()
            except Exception as e:
                if "200" in str(e): st.success("✅ Guardado"); time.sleep(1); st.rerun()
                else: st.error(f"Error: {e}")

elif menu == "Calculadora de Flete (IA)":
    st.header("🚚 Presupuestador Inteligente de Flete")
    st.write("Calcula el costo base de combustible para tu próximo viaje.")

    if not df_historico.empty:
        col1, col2 = st.columns(2)
        with col1:
            c_marca = st.selectbox("Marca del Camión", ["Scania", "Mercedes"])
            c_ruta = st.selectbox("Tipo de Ruta", ["Llano", "Alta Montaña"])
            c_distancia = st.number_input("Distancia a recorrer (KM)", min_value=1, value=100)
            margen_seguridad = st.slider("Margen de seguridad (%)", 0, 20, 5)
        
        filtro = df_historico[(df_historico['Marca'] == c_marca) & (df_historico['Ruta'] == c_ruta)]
        
        if not filtro.empty:
            consumo_medio = filtro['Consumo_L100'].mean()
            litros_estimados = (consumo_medio * c_distancia) / 100
            litros_con_margen = litros_estimados * (1 + margen_seguridad/100)
            costo_estimado = litros_con_margen * precio_litro
            
            with col2:
                st.metric("Costo Estimado Gasoil", f"${costo_estimado:,.2f}")
                st.metric("Litros Necesarios", f"{round(litros_con_margen, 1)} L")
                st.write(f"⚠️ *Basado en precio actual de ${precio_litro}/litro*")
                
            st.warning(f"👉 Para no perder margen, el flete debe cubrir los **${costo_estimado:,.2f}** solo de combustible.")
        else:
            st.warning("Sin datos previos para esta ruta.")

elif menu == "Análisis IA & Dashboard":
    st.header("📊 Dashboard Financiero e Inteligente")
    
    if not df_historico.empty:
        # Aseguramos que existan las columnas financieras si es la primera vez
        if 'Costo_Ralenti_ARS' not in df_historico.columns:
            df_historico['Costo_Ralenti_ARS'] = df_historico['L_Ralenti'] * precio_litro
        
        # --- BLOQUE FINANCIERO ---
        st.subheader("💸 Impacto Económico")
        col_f1, col_f2, col_f3 = st.columns(3)
        total_perdido = df_historico['Costo_Ralenti_ARS'].sum()
        col_f1.metric("Dinero Perdido (Ralentí)", f"${total_perdido:,.2f}", delta_color="inverse")
        col_f2.metric("Gasto Total Gasoil", f"${(df_historico['L_Ticket'].sum() * precio_litro):,.2f}")
        col_f3.metric("Costo Promedio p/ Viaje", f"${(df_historico['Costo_Viaje_ARS'].mean() if 'Costo_Viaje_ARS' in df_historico.columns else 0):,.2f}")

        # --- GRÁFICO DE DINERO PERDIDO ---
        st.subheader("📉 Pérdida de Dinero por Ralentí (por Chofer)")
        fig_money = px.bar(df_historico.groupby("Chofer")["Costo_Ralenti_ARS"].sum().reset_index(), 
                           x="Chofer", y="Costo_Ralenti_ARS", 
                           title="Pesos malgastados por motor encendido en espera",
                           color_discrete_sequence=['#EF553B'])
        st.plotly_chart(fig_money, use_container_width=True)

        # --- RANKING CHOFERES ---
        st.subheader("🏆 Ranking de Eficiencia")
        ranking = df_historico.groupby("Chofer")["Consumo_L100"].mean().sort_values().reset_index()
        st.plotly_chart(px.bar(ranking, x="Consumo_L100", y="Chofer", orientation='h', color="Consumo_L100"), use_container_width=True)
        import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import time
import hashlib

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Control de Flota Seguro", layout="wide")

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

# --- INICIO DEL PROGRAMA ---
if check_password():
    role = st.session_state.get("user_role", "operador")
    
    st.sidebar.success(f"Usuario: {st.session_state['username'].upper()}")
    if st.sidebar.button("Cerrar Sesión"):
        for key in st.session_state.keys():
            del st.session_state[key]
        st.rerun()

    # Definir opciones según rol
    if role == "admin":
        menu_options = ["Cargar Combustible", "Calculadora de Flete (IA)", "Análisis IA & Dashboard"]
    else:
        menu_options = ["Cargar Combustible"]
    
    # AQUÍ ESTÁ EL CAMBIO: El 'key' evita el error de duplicado
    menu = st.sidebar.selectbox("Menú", menu_options, key="menu_principal")

    # Luego siguen tus bloques 'if menu == ...'
