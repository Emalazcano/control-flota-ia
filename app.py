import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import time
import plotly.express as px
from sklearn.ensemble import IsolationForest

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Control de Flota IA", layout="wide")
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1PEH7lbtoq_oAHwom0O5YYYskFm6ALJ6LCj1FfQKzpmQ/edit?gid=0#gid=0"
conn = st.connection("gsheets", type=GSheetsConnection)

def obtener_datos():
    try:
        return conn.read(spreadsheet=SPREADSHEET_URL, ttl=0)
    except:
        return pd.DataFrame()

df_choferes = pd.read_excel("choferes.xlsx") if "choferes.xlsx" else pd.DataFrame()
df_historico = obtener_datos()

# --- INTERFAZ ---
st.sidebar.title("Navegación")
menu = st.sidebar.selectbox("Menú", ["Cargar Combustible", "Calculadora de Viaje (IA)", "Análisis IA & Dashboard"])

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
                st.success("✅ ¡Sincronizado!"); time.sleep(1); st.rerun()
            except Exception as e:
                if "200" in str(e): st.success("✅ Guardado"); time.sleep(1); st.rerun()
                else: st.error(f"Error: {e}")

elif menu == "Calculadora de Viaje (IA)":
    st.header("🧮 Calculadora de Consumo Predictivo")
    st.write("Usa esta herramienta para estimar cuánto combustible debería consumir un viaje.")

    if not df_historico.empty:
        col1, col2 = st.columns(2)
        with col1:
            c_marca = st.selectbox("Marca del Camión", ["Scania", "Mercedes"])
            c_ruta = st.selectbox("Tipo de Ruta", ["Llano", "Alta Montaña"])
            c_distancia = st.number_input("Distancia a recorrer (KM)", min_value=1, value=100)
        
        # Lógica de Predicción Simple basada en promedios históricos
        filtro = df_historico[(df_historico['Marca'] == c_marca) & (df_historico['Ruta'] == c_ruta)]
        
        if not filtro.empty:
            consumo_medio = filtro['Consumo_L100'].mean()
            litros_estimados = (consumo_medio * c_distancia) / 100
            
            with col2:
                st.metric("Consumo Estimado", f"{round(litros_estimados, 1)} Litros")
                st.metric("Rendimiento Objetivo", f"{round(consumo_medio, 2)} L/100km")
                
            st.info(f"💡 Esta predicción se basa en {len(filtro)} viajes anteriores similares.")
            
            # Comparativa visual
            st.subheader("Rendimiento histórico para esta configuración")
            fig_hist = px.histogram(filtro, x="Consumo_L100", nbins=10, title="Frecuencia de consumos históricos")
            st.plotly_chart(fig_hist, use_container_width=True)
        else:
            st.warning("Aún no hay suficientes datos para esta combinación de Marca y Ruta.")
    else:
        st.info("Carga datos para activar la calculadora.")

elif menu == "Análisis IA & Dashboard":
    st.header("📊 Inteligencia de Flota")
    
    if not df_historico.empty:
        # --- DETECCIÓN DE ANOMALÍAS ---
        st.subheader("🚨 Alertas de la IA")
        if len(df_historico) > 5:
            data_ia = df_historico[['Consumo_L100', 'Desvio_Neto']].fillna(0)
            modelo = IsolationForest(contamination=0.1, random_state=42)
            df_historico['IA_Status'] = modelo.fit_predict(data_ia)
            anomalias = df_historico[df_historico['IA_Status'] == -1]
            if not anomalias.empty:
                st.warning(f"Se detectaron {len(anomalias)} anomalías.")
                st.dataframe(anomalias[['Fecha', 'Chofer', 'Movil', 'Consumo_L100', 'Desvio_Neto']])
        
        # --- KPI'S ---
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Consumo Promedio", f"{round(df_historico['Consumo_L100'].mean(), 2)} L/100")
        col_b.metric("Desvío Neto Total", f"{round(df_historico['Desvio_Neto'].sum(), 2)} L")
        col_c.metric("KM Totales", f"{int(df_historico['KM_Recorr'].sum())} km")

        # --- GRÁFICOS ---
        st.subheader("🏎️ Scania vs Mercedes")
        st.plotly_chart(px.box(df_historico, x="Marca", y="Consumo_L100", color="Marca"), use_container_width=True)

        st.subheader("🏆 Ranking Choferes")
        ranking = df_historico.groupby("Chofer")["Consumo_L100"].mean().sort_values().reset_index()
        st.plotly_chart(px.bar(ranking, x="Consumo_L100", y="Chofer", orientation='h', color="Consumo_L100"), use_container_width=True)
