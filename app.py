import streamlit as st
import pandas as pd
import plotly.express as px
import os
import numpy as np
from sklearn.linear_model import LinearRegression

# --- CONFIGURACIÓN DE ARCHIVOS ---
DB_FILE = "registro_combustible.csv"
CHOFERES_FILE = "choferes.xlsx"

# --- FUNCIONES DE SOPORTE ---
def cargar_datos():
    if os.path.exists(DB_FILE):
        try: return pd.read_csv(DB_FILE)
        except: return pd.DataFrame()
    return pd.DataFrame()

def obtener_lista_choferes():
    if os.path.exists(CHOFERES_FILE):
        try:
            df_ch = pd.read_excel(CHOFERES_FILE)
            df_ch.columns = [c.strip().capitalize() for c in df_ch.columns]
            if "Nombre" in df_ch.columns:
                return sorted(df_ch["Nombre"].dropna().unique().tolist())
        except: pass
    return []

# --- MOTOR DE PREDICCIÓN IA ---
def predecir_consumo_ia(df, ruta, km_a_recorrer):
    if len(df) < 5: return None
    try:
        df_ia = df.copy()
        # Mapeo estricto para las dos rutas solicitadas
        rutas_map = {"Llano": 0, "Alta Montaña": 1}
        df_ia["Ruta_Num"] = df_ia["Ruta"].map(rutas_map)
        
        # Filtramos por si existen registros viejos de otras rutas que ya no usamos
        df_ia = df_ia.dropna(subset=["Ruta_Num"])
        
        if len(df_ia) < 3: return None

        X = df_ia[["KM_Recorr", "Ruta_Num"]]
        y = df_ia["L_Ticket"]
        
        modelo = LinearRegression()
        modelo.fit(X, y)
        
        pred = modelo.predict([[km_a_recorrer, rutas_map[ruta]]])
        return max(0, pred[0])
    except: return None

# --- CONFIGURACIÓN DE LA APP ---
st.set_page_config(page_title="Flota IA - Dual Route", layout="wide")
df_existente = cargar_datos()
lista_maestra_choferes = obtener_lista_choferes()
lista_trazas = sorted(df_existente["Traza"].unique().tolist()) if not df_existente.empty else []

st.title("🚛 Control de Flota: Llano vs Alta Montaña")

tab1, tab2, tab3 = st.tabs(["📝 Operación e IA", "📊 Dashboard", "🤖 Asistente Virtual"])

# --- TAB 1: REGISTRO Y PREDICCIÓN ---
with tab1:
    col_izq, col_der = st.columns([1, 2.5])
    
    with col_izq:
        st.subheader("🔮 Estimador IA")
        # Cambio solicitado: Solo Llano y Alta Montaña
        ruta_pred = st.radio("Próxima Ruta", ["Llano", "Alta Montaña"])
        km_pred = st.number_input("KMs estimados", min_value=1, value=100)
        
        if st.button("Predecir Litros"):
            prediccion = predecir_consumo_ia(df_existente, ruta_pred, km_pred)
            if prediccion:
                st.metric("Carga Sugerida", f"{prediccion:.1f} L")
            else:
                st.warning("Datos insuficientes para predecir.")

    with col_der:
        st.subheader("📋 Registro de Viaje")
        
        # Identificación (Chofer y Traza)
        c1, c2 = st.columns(2)
        with c1:
            ch_sel = st.selectbox("Chofer", ["-- Seleccionar --", "➕ NUEVO"] + lista_maestra_choferes)
            ch_final = st.text_input("Nombre:") if ch_sel == "➕ NUEVO" else ch_sel
        with c2:
            tr_sel = st.selectbox("Traza", ["-- Seleccionar --", "➕ NUEVA"] + lista_trazas)
            tr_final = st.text_input("Origen-Destino:") if tr_sel == "➕ NUEVA" else tr_sel

        movil_sel = st.selectbox("Móvil", [f"Móvil {i}" for i in range(1, 101)])
        
        ultimo_km = 0
        if not df_existente.empty:
            reg_m = df_existente[df_existente["Movil"] == movil_sel]
            if not reg_m.empty: ultimo_km = int(reg_m["KM_Fin"].iloc[-1])

        with st.form("form_registro", clear_on_submit=True):
            f1, f2, f3 = st.columns(3)
            fecha = f1.date_input("Fecha")
            marca = f2.selectbox("Marca", ["Scania", "Mercedes Benz"])
            # Cambio solicitado: Selección simplificada
            ruta_reg = f3.selectbox("Ruta", ["Llano", "Alta Montaña"])

            st.markdown("---")
            k1, k2, k3 = st.columns(3)
            km_i = k1.number_input("KM Inicial", value=ultimo_km)
            km_f = k2.number_input("KM Final")
            l_ralenti = k3.number_input("Litros Ralentí", min_value=0.0)

            l1, l2, l3 = st.columns(3)
            l_tk = l1.number_input("Litros Ticket", min_value=0.0)
            l_tab = l2.number_input("Litros Tablero", min_value=0.0)
            dias = l3.number_input("Días", min_value=1)

            if st.form_submit_button("💾 GUARDAR REGISTRO"):
                if ch_final in ["-- Seleccionar --", ""] or tr_final in ["-- Seleccionar --", ""] or km_f <= km_i:
                    st.error("Datos incompletos o erróneos.")
                else:
                    km_r = km_f - km_i
                    desv = (l_tk - l_tab) - l_ralenti
                    cons = (l_tk / km_r * 100) if km_r > 0 else 0
                    
                    nuevo = pd.DataFrame([{
                        "Fecha": str(fecha), "Chofer": ch_final, "Movil": movil_sel,
                        "Marca": marca, "Ruta": ruta_reg, "Traza": tr_final,
                        "KM_Ini": km_i, "KM_Fin": km_f, "KM_Recorr": km_r,
                        "L_Ralenti": l_ralenti, "L_Ticket": l_tk,
                        "Desvio_Neto": round(desv, 2), "Consumo_L100": round(cons, 2)
                    }])
                    nuevo.to_csv(DB_FILE, mode='a', header=not os.path.exists(DB_FILE), index=False)
                    st.success("Registro Exitoso.")
                    st.rerun()

# --- TAB 2 & 3 (DASHBOARD Y ASISTENTE) ---
with tab2:
    if not df_existente.empty:
        st.header("📊 Resumen Operativo")
        # Gráficos filtrando solo por las dos rutas actuales para evitar errores con datos viejos
        df_plot = df_existente[df_existente["Ruta"].isin(["Llano", "Alta Montaña"])]
        
        st.plotly_chart(px.box(df_plot, x="Ruta", y="Consumo_L100", color="Ruta", 
                               title="Comparativa de Consumo: Llano vs Montaña"), use_container_width=True)
        st.dataframe(df_existente, use_container_width=True)

with tab3:
    st.header("🤖 Consultas IA")
    if not df_existente.empty:
        st.write("Ahora puedes comparar directamente el rendimiento de tus unidades en los dos terrenos base.")
        if st.button("Ver Diferencia de Consumo Promedio"):
            diff = df_existente.groupby("Ruta")["Consumo_L100"].mean()
            st.write(diff)
import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# --- CONFIGURACIÓN DE LA CONEXIÓN ---
# En el sidebar o configuración, pegaremos la URL de tu Google Sheet
url_hoja = "https://docs.google.com/spreadsheets/d/1PEH7lbtoq_oAHwom0O5YYYskFm6ALJ6LCj1FfQKzpmQ/edit?gid=0#gid=0"

conn = st.connection("gsheets", type=GSheetsConnection)

def cargar_datos_google():
    try:
        # Lee los datos directamente desde Google Sheets
        return conn.read(spreadsheet=url_hoja)
    except:
        return pd.DataFrame()

# ... (El resto del código de la interfaz se mantiene igual) ...

# --- AL GUARDAR EL REGISTRO ---
# Cambiaremos la parte del botón de guardar para que haga esto:
if st.form_submit_button("💾 GUARDAR REGISTRO"):
    # ... (cálculos de km_r, desv, etc.) ...
    nuevo_dato = pd.DataFrame([{...}]) # Tus datos
    
    # Combinar existentes con el nuevo
    df_actualizado = pd.concat([df_existente, nuevo_dato], ignore_index=True)
    
    # Actualizar la hoja de Google
    conn.update(spreadsheet=url_hoja, data=df_actualizado)
    st.success("¡Datos guardados en Google Sheets!")            
