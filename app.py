import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import time
import os

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Control Flota Jujuy", layout="wide")

conn = st.connection("gsheets", type=GSheetsConnection)
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1PEH7lbtoq_oAHwom0O5YYYskFm6ALJ6LCj1FfQKzpmQ/edit?gid=0#gid=0"

def obtener_datos():
    try:
        df = conn.read(spreadsheet=SPREADSHEET_URL, ttl=0)
        cols_num = ["Costo_Total_ARS", "L_Ticket", "Costo_Ralenti_ARS", "Consumo_L100", "Desvio_Neto", "L_Tablero", "L_Ralenti"]
        for c in cols_num:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        return df
    except:
        return pd.DataFrame()

@st.cache_data
def obtener_listas_excel():
    archivo = "choferes.xlsx"
    lista_c = ["Cargar Choferes"]
    lista_m = [1] # Valor por defecto
    if os.path.exists(archivo):
        try:
            xl = pd.read_excel(archivo)
            # Buscamos la columna de Choferes
            col_c = "Chofer" if "Chofer" in xl.columns else None
            if col_c:
                lista_c = sorted(xl[col_c].dropna().unique().tolist())
            
            # Buscamos la columna de Móviles (asumiendo que se llama 'Movil' o 'Interno')
            col_m = "Movil" if "Movil" in xl.columns else ("Interno" if "Interno" in xl.columns else None)
            if col_m:
                lista_m = sorted(xl[col_m].dropna().unique().tolist())
        except:
            pass
    return lista_c, lista_m

# --- 2. LOGIN ---
if "auth" not in st.session_state:
    st.title("🚛 Sistema de Control de Flota")
    _, col_log, _ = st.columns([1, 3, 1])
    with col_log:
        st.subheader("🔐 Acceso")
        c1, c2, c3 = st.columns([2, 2, 1])
        u = c1.text_input("Usuario", label_visibility="collapsed", placeholder="Usuario")
        p = c2.text_input("Clave", type="password", label_visibility="collapsed", placeholder="Contraseña")
        if c3.button("Entrar", use_container_width=True):
            if u == "ema_admin" and p == "jujuy2024":
                st.session_state["auth"] = True
                st.rerun()
            else: st.error("❌")
    st.stop()

# --- 3. CARGA DE DATOS ---
df_h = obtener_datos()
choferes, moviles = obtener_listas_excel()

# --- 4. INTERFAZ ---
st.title("🚛 Inteligencia de Flota y Costos")
tabs = st.tabs(["⛽ Registro", "🦅 Inteligencia", "📜 Historial"])

# --- PESTAÑA REGISTRO ---
with tabs[0]:
    with st.form("registro", clear_on_submit=True):
        st.subheader("📝 Nuevo Registro de Carga")
        
        c_precio, _ = st.columns([1, 2])
        precio_gasoil = c_precio.number_input("Precio Litro Gasoil ($)", min_value=0.0, value=1100.0, step=10.0)
        
        st.divider()
        
        f1, f2, f3 = st.columns(3)
        with f1:
            fecha = st.date_input("Fecha", datetime.now(), format="DD/MM/YYYY")
            # CAMBIO AQUÍ: Ahora es un selectbox con los móviles del Excel
            movil_sel = st.selectbox("Móvil", moviles)
            chofer_sel = st.selectbox("Chofer", choferes)
        with f2:
            marca = st.radio("Marca", ["SCANIA", "MERCEDES BENZ"], horizontal=True)
            ruta = st.radio("Ruta", ["Llano", "Alta Montaña"], horizontal=True)
            traza = st.text_input("Traza").upper()
        with f3:
            kmi = st.number_input("KM Inicial", min_value=0)
            kmf = st.number_input("KM Final", min_value=0)
            lt = st.number_input("Litros Ticket", min_value=0.0)
            ltab = st.number_input("Litros Tablero", min_value=0.0)
            lral = st.number_input("Litros Ralentí", min_value=0.0)
        
        recorrido = kmf - kmi
        consumo_estimado = (lt / recorrido * 100) if recorrido > 0 else 0
        desvio = lt - (ltab + lral)
        costo_v = lt * precio_gasoil
        
        st.info(f"📊 **Calculadora:** Recorrido: {recorrido} km | Consumo: {consumo_estimado:.2f} L/100 | Costo: $ {costo_v:,.0f}")
        
        if st.form_submit_button("💾 GUARDAR"):
            if kmf > kmi and lt > 0:
                nuevo = {
                    "Fecha": fecha.strftime('%d/%m/%Y'),
                    "Chofer": chofer_sel, "Movil": movil_sel, "Marca": marca, "Ruta": ruta, 
                    "Traza": traza, "KM_Ini": kmi, "KM_Fin": kmf, "KM_Recorr": recorrido, 
                    "L_Ticket": lt, "L_Tablero": ltab, "L_Ralenti": lral,
                    "Desvio_Neto": round(desvio, 2), "Consumo_L100": round(consumo_estimado, 2),
                    "Costo_Total_ARS": round(costo_v, 2), "Costo_Ralenti_ARS": round(lral * precio_gasoil, 2)
                }
                df_f = pd.concat([df_h, pd.DataFrame([nuevo])], ignore_index=True)
                conn.update(spreadsheet=SPREADSHEET_URL, data=df_f)
                st.success("✅ Guardado")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Error en KM o Litros.")

# --- PESTAÑA IA ---
with tabs[1]:
    if not df_h.empty:
        m1, m2, m3 = st.columns(3)
        m1.metric("Gasto Acumulado", f"$ {df_h['Costo_Total_ARS'].sum():,.0f}")
        m2.metric("Pérdida Ralentí", f"$ {df_h['Costo_Ralenti_ARS'].sum():,.0f}")
        m3.metric("Consumo Promedio", f"{df_h['Consumo_L100'].mean():,.1f} L/100")
        
        st.divider()
        g1, g2 = st.columns(2)
        with g1:
            st.subheader("🏆 Eco-Driving")
            rank = df_h.groupby("Chofer")["Consumo_L100"].mean().sort_values().head(5).reset_index()
            for i, r in rank.iterrows():
                st.write(f"{['🥇','🥈','🥉','👤','👤'][i]} **{r['Chofer']}**: {r['Consumo_L100']:.2f} L/100")
        with g2:
            st.subheader("🚨 Desvíos (>50L)")
            alertas = df_h.groupby("Chofer")["Desvio_Neto"].sum().reset_index()
            for _, r in alertas.iterrows():
                val = r['Desvio_Neto']
                if val > 50: st.error(f"**{r['Chofer']}**: {val:.1f} L")
                elif val < -50: st.warning(f"**{r['Chofer']}**: {val:.1f} L")
                else: st.write(f"**{r['Chofer']}**: {val:.1f} L (OK)")
    else: st.info("Sin datos.")

# --- PESTAÑA HISTORIAL ---
with tabs[2]:
    st.subheader("📜 Historial Completo")
    if not df_h.empty:
        st.dataframe(df_h.iloc[::-1], use_container_width=True)
        st.download_button("📥 Exportar CSV", df_h.to_csv(index=False), "historial.csv")
