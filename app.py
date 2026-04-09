import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import time
import plotly.express as px
from sklearn.ensemble import IsolationForest

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Control de Flota IA", layout="wide")
SPREADSHEET_URL = "TU_LINK_DE_GOOGLE_SHEETS_AQUI"
conn = st.connection("gsheets", type=GSheetsConnection)

def obtener_datos():
    try:
        return conn.read(spreadsheet=SPREADSHEET_URL, ttl=0)
    except:
        return pd.DataFrame()

df_choferes = pd.read_excel("choferes.xlsx") if "choferes.xlsx" else pd.DataFrame()
df_historico = obtener_datos()

# --- INTERFAZ ---
st.title("🚛 Sistema de Flota con Inteligencia Artificial")

menu = st.sidebar.selectbox("Menú", ["Cargar Combustible", "Análisis IA & Dashboard"])

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
            marca = st.radio("Marca del Camión", ["Scania", "Mercedes"])
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
            
            nuevo = pd.DataFrame([{
                "Fecha": str(fecha), "Chofer": chofer, "Movil": movil_seleccionado,
                "Marca": marca, "Ruta": ruta, "Traza": traza, "KM_Ini": km_ini,
                "KM_Fin": km_fin, "KM_Recorr": km_recorr, "L_Tablero": l_tablero,
                "L_Ralenti": l_ralenti, "L_Ticket": l_ticket, 
                "Desvio_Neto": round(desvio, 2), "Consumo_L100": round(consumo, 2)
            }])
            
            try:
                df_final = pd.concat([df_historico, nuevo], ignore_index=True)
                conn.update(spreadsheet=SPREADSHEET_URL, data=df_final)
                st.success("✅ ¡Sincronizado!")
                time.sleep(1); st.rerun()
            except Exception as e:
                if "200" in str(e): st.success("✅ Guardado"); time.sleep(1); st.rerun()
                else: st.error(f"Error: {e}")

elif menu == "Análisis IA & Dashboard":
    st.header("📊 Inteligencia de Flota")
    
    if not df_historico.empty:
        # --- 1. DETECCIÓN DE ANOMALÍAS CON IA ---
        st.subheader("🚨 Alertas de la IA (Detección de Anomalías)")
        if len(df_historico) > 5: # Necesita algunos datos para aprender
            # Preparamos datos para la IA
            data_ia = df_historico[['Consumo_L100', 'Desvio_Neto']].fillna(0)
            modelo = IsolationForest(contamination=0.1, random_state=42) # Detecta el 10% más raro
            df_historico['IA_Status'] = modelo.fit_predict(data_ia)
            
            anomalias = df_historico[df_historico['IA_Status'] == -1]
            if not anomalias.empty:
                st.warning(f"La IA detectó {len(anomalias)} registros con consumos o desvíos fuera de lo normal.")
                st.dataframe(anomalias[['Fecha', 'Chofer', 'Movil', 'Consumo_L100', 'Desvio_Neto']])
            else:
                st.success("✅ No se detectan anomalías críticas en los últimos registros.")
        else:
            st.info("La IA está aprendiendo. Necesita al menos 5 registros para analizar patrones.")

        # --- 2. KPI'S PRINCIPALES ---
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Consumo Promedio General", f"{round(df_historico['Consumo_L100'].mean(), 2)} L/100")
        col_b.metric("Desvío Neto Total", f"{round(df_historico['Desvio_Neto'].sum(), 2)} L")
        col_c.metric("KM Totales Flota", f"{int(df_historico['KM_Recorr'].sum())} km")

        # --- 3. COMPARATIVA DE MARCAS ---
        st.subheader("🏎️ Rendimiento por Marca (Scania vs Mercedes)")
        fig_marca = px.box(df_historico, x="Marca", y="Consumo_L100", color="Marca", points="all", title="Dispersión de Consumo por Marca")
        st.plotly_chart(fig_marca, use_container_width=True)

        # --- 4. RANKING DE EFICIENCIA CHOFERES ---
        st.subheader("🏆 Ranking Eco-Driving (Mejores Choferes)")
        ranking = df_historico.groupby("Chofer")["Consumo_L100"].mean().sort_values().reset_index()
        fig_rank = px.bar(ranking, x="Consumo_L100", y="Chofer", orientation='h', color="Consumo_L100", title="Choferes más eficientes (Menos es mejor)")
        st.plotly_chart(fig_rank, use_container_width=True)

        # --- 5. TABLA HISTÓRICA ---
        st.subheader("📝 Historial Completo")
        st.dataframe(df_historico.iloc[::-1], use_container_width=True)
    else:
        st.info("Esperando datos para iniciar el análisis IA.")
