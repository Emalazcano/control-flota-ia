import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime
import time
import os

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Control Flota Jujuy", layout="wide")

conn = st.connection("gsheets", type=GSheetsConnection)
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1PEH7lbtoq_oAHwom0O5YYYskFm6ALJ6LCj1FfQKzpmQ/edit?gid=0#gid=0"

if "precio_gasoil_fijo" not in st.session_state:
    st.session_state["precio_gasoil_fijo"] = 1100.0

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
def obtener_choferes_repo():
    archivo = "choferes.xlsx"
    if os.path.exists(archivo):
        try:
            xl = pd.read_excel(archivo)
            col = "Chofer" if "Chofer" in xl.columns else xl.columns[0]
            return sorted(xl[col].dropna().unique().tolist())
        except: pass
    return ["Error: choferes.xlsx no encontrado"]

# --- 2. LOGIN ---
if "auth" not in st.session_state:
    st.title("🚚 Sistema de Control de Flota")
    _, col_log, _ = st.columns([1, 3, 1])
    with col_log:
        st.subheader("🔐 Acceso")
        c1, c2, c3 = st.columns([2, 2, 1])
        u = c1.text_input("Usuario", placeholder="Usuario")
        p = c2.text_input("Clave", type="password", placeholder="Contraseña")
        if c3.button("Ingresar", use_container_width=True):
            if u == "ema_admin" and p == "jujuy2024":
                st.session_state["auth"] = True
                st.rerun()
            else: st.error("❌")
    st.stop()

# --- 3. CARGA DE DATOS Y TRAZAS ---
df_h = obtener_datos()
lista_choferes = obtener_choferes_repo()

trazas_en_db = []
if not df_h.empty and "Traza" in df_h.columns:
    trazas_en_db = [str(t).strip().upper() for t in df_h["Traza"].unique() if t]

trazas_para_selector = ["➕ NUEVA TRAZA"] + sorted(trazas_en_db)

# --- 4. INTERFAZ PRINCIPAL ---
st.title("🚚 Inteligencia de Flota y Costos")
tabs = st.tabs(["⛽ Registro de Carga", "🦅 Ojo de Halcón (IA)", "📜 Historial Completo"])

# --- TAB REGISTRO ---
with tabs[0]:
    st.subheader("📝 Nuevo Registro")
    c_p, _ = st.columns([1, 2])
    precio_gasoil = c_p.number_input("💵 Precio Gasoil por Litro ($)", min_value=0.0, value=st.session_state["precio_gasoil_fijo"])
    st.session_state["precio_gasoil_fijo"] = precio_gasoil

    with st.form("registro_final", clear_on_submit=True):
        st.divider()
        f1, f2, f3 = st.columns(3)
        with f1:
            fecha = st.date_input("📅 Fecha", datetime.now(), format="DD/MM/YYYY")
            movil = st.number_input("🔢 Móvil (1-100)", min_value=1, max_value=100)
            chofer = st.selectbox("👤 Chofer", lista_choferes)
        with f2:
            marca = st.radio("🚛 Marca", ["SCANIA", "MERCEDES BENZ"], horizontal=True)
            ruta_tipo = st.radio("🏔️ Tipo de Ruta", ["Llano", "Alta Montaña"], horizontal=True)
            traza_sel = st.selectbox("📍 Seleccionar Traza", trazas_para_selector)
            nueva_traza_input = st.text_input("✍️ Escribir Nombre de Nueva Traza").strip().upper() if traza_sel == "➕ NUEVA TRAZA" else ""
            traza_final = nueva_traza_input if traza_sel == "➕ NUEVA TRAZA" else traza_sel
        with f3:
            kmi = st.number_input("🛣️ KM Inicial", min_value=0)
            kmf = st.number_input("🏁 KM Final", min_value=0)
            lt = st.number_input("⛽ Litros Ticket", min_value=0.0)
            ltab = st.number_input("📟 Litros Tablero", min_value=0.0)
            lral = st.number_input("⏳ Litros Ralentí", min_value=0.0)
        
        recorrido = kmf - kmi
        consumo = (lt / recorrido * 100) if recorrido > 0 else 0
        costo_v = lt * precio_gasoil
        st.info(f"📊 **Resumen:** {recorrido} km | {consumo:.2f} L/100 | **Costo: $ {costo_v:,.2f}**")
        
        if st.form_submit_button("💾 GUARDAR REGISTRO"):
            if traza_sel == "➕ NUEVA TRAZA" and traza_final in trazas_en_db:
                st.error(f"🚫 La ruta '{traza_final}' ya existe. Selecciónala de la lista.")
            elif kmf > kmi and lt > 0 and tra_final != "":
                nuevo = {
                    "Fecha": fecha.strftime('%Y-%m-%d'), "Chofer": chofer, "Movil": movil, "Marca": marca, "Ruta": ruta_tipo, 
                    "Traza": traza_final, "KM_Ini": kmi, "KM_Fin": kmf, "KM_Recorr": recorrido, 
                    "L_Ticket": lt, "L_Tablero": ltab, "L_Ralenti": lral,
                    "Desvio_Neto": round(lt - (ltab + lral), 2), "Consumo_L100": round(consumo, 2),
                    "Costo_Total_ARS": round(costo_v, 2), "Costo_Ralenti_ARS": round(lral * precio_gasoil, 2)
                }
                df_f = pd.concat([df_h, pd.DataFrame([nuevo])], ignore_index=True)
                conn.update(spreadsheet=SPREADSHEET_URL, data=df_f)
                st.success("✅ Guardado")
                time.sleep(1)
                st.rerun()

# --- TAB INTELIGENCIA (RECUPERANDO GRÁFICOS) ---
with tabs[1]:
    st.subheader("🦅 Inteligencia de Flota")
    if not df_h.empty:
        m1, m2, m3 = st.columns(3)
        m1.metric("💰 Gasto Histórico", f"$ {df_h['Costo_Total_ARS'].sum():,.0f}")
        m2.metric("🛑 Pérdida Ralentí", f"$ {df_h['Costo_Ralenti_ARS'].sum():,.0f}")
        m3.metric("📉 Consumo Promedio", f"{df_h['Consumo_L100'].mean():,.1f} L/100")
        
        st.divider()
        col_g1, col_g2 = st.columns(2)
        
        with col_g1:
            st.subheader("📉 Dispersión de Desvíos")
            fig1 = px.scatter(df_h, x="Fecha", y="Desvio_Neto", color="Marca", size=df_h["Desvio_Neto"].abs(),
                             color_discrete_map={"SCANIA": "#EF553B", "MERCEDES BENZ": "#636EFA"}, template="plotly_dark")
            st.plotly_chart(fig1, use_container_width=True)
            
        with col_g2:
            st.subheader("⚠️ Desvío por Chofer")
            df_desvio = df_h.groupby("Chofer")["Desvio_Neto"].sum().reset_index()
            fig2 = px.bar(df_desvio, x="Desvio_Neto", y="Chofer", orientation='h', color="Desvio_Neto",
                          color_continuous_scale="Reds", template="plotly_dark")
            st.plotly_chart(fig2, use_container_width=True)

        st.divider()
        c_i, c_d = st.columns(2)
        with c_i:
            st.subheader("🏆 Top 5 Eco-Driving")
            rank = df_h.groupby("Chofer")["Consumo_L100"].mean().sort_values().head(5)
            st.table(rank)
        with c_d:
            st.subheader("🚨 Alertas de Desvío")
            for _, r in df_desvio.iterrows():
                if abs(r['Desvio_Neto']) > 50: st.error(f"⚠️ **{r['Chofer']}**: {r['Desvio_Neto']:.1f} L")

# --- TAB HISTORIAL ---
with tabs[2]:
    st.subheader("📜 Historial Completo")
    if not df_h.empty:
        st.dataframe(df_h.iloc[::-1], use_container_width=True)
