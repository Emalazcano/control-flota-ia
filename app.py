import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime
import time
import os

# --- 1. CONFIGURACIÓN Y ESTILOS ---
st.set_page_config(page_title="Inteligencia de Flota Jujuy", layout="wide")

st.markdown("""
    <style>
    .metric-card { background-color: #1e2130; padding: 15px; border-radius: 12px; border: 1px solid #3d425a; text-align: center; }
    .driver-name { font-weight: bold; font-size: 16px; margin: 5px 0; color: white; }
    .driver-score { font-size: 22px; color: #4CAF50; font-weight: bold; }
    .category-header { background: linear-gradient(90deg, #1e2130, #3d425a); padding: 10px; border-radius: 8px; margin-bottom: 15px; text-align: center; }
    </style>
""", unsafe_allow_html=True)

# --- 2. LOGIN ---
if "auth" not in st.session_state:
    st.title("🚚 Sistema de Control de Flota")
    _, col_log, _ = st.columns([1, 2, 1])
    with col_log:
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.button("Ingresar", use_container_width=True):
            if u == "ema_admin" and p == "jujuy2024":
                st.session_state["auth"] = True
                st.rerun()
            else: st.error("Clave incorrecta")
    st.stop()

# --- 3. DATOS Y CONEXIONES ---
conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1PEH7lbtoq_oAHwom0O5YYYskFm6ALJ6LCj1FfQKzpmQ/edit?gid=0#gid=0"

if "precio_gasoil" not in st.session_state:
    st.session_state["precio_gasoil"] = 2065.0

@st.cache_data(ttl=600)
def obtener_choferes():
    if os.path.exists("choferes.xlsx"):
        try:
            xl = pd.read_excel("choferes.xlsx")
            return sorted(xl.iloc[:, 0].dropna().unique().tolist())
        except: pass
    return ["ADELMO JORGE", "BENITEZ DIEGO", "GONZALEZ FABIAN"]

def cargar_historial():
    try:
        df = conn.read(spreadsheet=URL, ttl=0)
        num_cols = ["KM_Fin", "L_Ticket", "L_Tablero", "L_Ralenti", "Desvio_Neto", "Consumo_L100", "Costo_Total_ARS"]
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df
    except: return pd.DataFrame()

df_h = cargar_historial()
lista_choferes = obtener_choferes()

# --- 4. INTERFAZ ---
st.title("🚚 Inteligencia de Flota y Costos")
tabs = st.tabs(["⛽ Registro de Carga", "🦅 Ojo de Halcón (IA)", "📜 Historial"])

# --- TAB 1: REGISTRO ---
with tabs[0]:
    st.subheader("📝 Nuevo Registro")
    cp, _ = st.columns([1, 3])
    st.session_state["precio_gasoil"] = cp.number_input("💵 Precio Gasoil por Litro ($)", value=st.session_state["precio_gasoil"])
    
    with st.form("registro_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("##### 🚛 Vehículo")
            movil_sel = st.selectbox("🔢 Móvil", list(range(1, 101)), index=36)
            marca = st.radio("🏷️ Marca", ["SCANIA", "MERCEDES BENZ"], horizontal=True)
            chofer = st.selectbox("👤 Chofer", lista_choferes)
        with col2:
            st.markdown("##### 📍 Ruta")
            ruta_tipo = st.radio("🏔️ Tipo de Ruta", ["Llano", "Alta Montaña"], horizontal=True)
            traza_existente = ["➕ NUEVA"] + (sorted(df_h["Traza"].unique().tolist()) if not df_h.empty else [])
            traza = st.selectbox("🗺️ Traza", traza_existente)
            nt = st.text_input("✍️ Nombre Nueva Traza").upper()
            t_final = nt if (traza == "➕ NUEVA" and nt != "") else traza
        with col3:
            st.markdown("##### ⛽ Consumo")
            km_previo = df_h[df_h["Movil"] == movil_sel]["KM_Fin"].max() if (not df_h.empty and movil_sel in df_h["Movil"].values) else 0
            kmi = st.number_input("🛣️ KM Inicial", value=int(km_previo))
            kmf = st.number_input("🏁 KM Final")
            lt = st.number_input("⛽ Litros Ticket")
            ltab = st.number_input("📟 Litros Tablero")
            lral = st.number_input("⏳ Litros Ralentí")

        # --- CALCULADORA DE COSTO (RECUPERADA) ---
        distancia = kmf - kmi
        consumo = (lt / distancia * 100) if distancia > 0 else 0
        costo_t = lt * st.session_state["precio_gasoil"]
        desvio_n = lt - (ltab + lral)
        
        if distancia > 0:
            st.divider()
            c1, c2, c3 = st.columns(3)
            c1.info(f"📏 Recorrido: **{distancia} KM**")
            c2.info(f"📊 Consumo: **{consumo:.1f} L/100**")
            c3.info(f"💰 Costo Viaje: **${costo_t:,.0f}**")

        submit = st.form_submit_button("💾 GUARDAR REGISTRO", use_container_width=True)

        if submit:
            if kmf <= kmi or lt <= 0 or t_final == "":
                st.error("⚠️ Datos inválidos.")
            else:
                nuevo_reg = {
                    "Fecha": datetime.now().strftime('%Y-%m-%d'), "Movil": movil_sel,
                    "Chofer": chofer, "Marca": marca, "Ruta": ruta_tipo, "Traza": t_final,
                    "KM_Ini": kmi, "KM_Fin": kmf, "KM_Recorr": distancia, "L_Ticket": lt,
                    "L_Tablero": ltab, "L_Ralenti": lral, "Consumo_L100": round(consumo, 2),
                    "Costo_Total_ARS": round(costo_t, 2), "Desvio_Neto": round(desvio_n, 2)
                }
                df_up = pd.concat([df_h, pd.DataFrame([nuevo_reg])], ignore_index=True)
                conn.update(spreadsheet=URL, data=df_up)
                st.success("✅ ¡Registro guardado!")
                time.sleep(1)
                st.rerun()

# --- TAB 2: OJO DE HALCÓN (DASHBOARD RECUPERADO) ---
with tabs[1]:
    if not df_h.empty:
        st.subheader("🦅 Inteligencia de Flota")
        m1, m2, m3 = st.columns(3)
        m1.metric("💰 Gasto Total", f"$ {df_h['Costo_Total_ARS'].sum():,.0f}")
        m2.metric("🛑 Pérdida Ralentí", f"$ {(df_h['L_Ralenti'] * st.session_state['precio_gasoil']).sum():,.0f}")
        m3.metric("📉 Promedio General", f"{df_h['Consumo_L100'].mean():,.1f} L/100")
        
        st.divider()
        col_g1, col_g2 = st.columns(2)
        
        with col_g1:
            st.markdown("📊 **Desvíos por Marca y Fecha**")
            fig1 = px.scatter(df_h, x="Fecha", y="Desvio_Neto", color="Marca", 
                              size=df_h["L_Ticket"].abs().clip(lower=1), 
                              hover_data=["Chofer", "Movil", "Traza"],
                              color_discrete_map={"SCANIA": "#EF553B", "MERCEDES BENZ": "#636EFA"},
                              template="plotly_dark")
            st.plotly_chart(fig1, use_container_width=True)

        with col_g2:
            st.markdown("⚠️ **Ranking de Desvío Acumulado por Chofer**")
            desvio_ch = df_h.groupby("Chofer")["Desvio_Neto"].sum().sort_values(ascending=False).reset_index()
            fig2 = px.bar(desvio_ch, x="Desvio_Neto", y="Chofer", orientation='h',
                          color="Desvio_Neto", color_continuous_scale="Reds",
                          template="plotly_dark")
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Sin datos para el Dashboard.")

with tabs[2]:
    st.dataframe(df_h.iloc[::-1], use_container_width=True)
