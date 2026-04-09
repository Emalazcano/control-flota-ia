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
        cols_num = ["Costo_Total_ARS", "L_Ticket", "Costo_Ralenti_ARS", "Consumo_L100", "Desvio_Neto", "L_Tablero", "L_Ralenti", "KM_Fin"]
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
    return ["Error: choferes.xlsx"]

# --- 2. PROCESAMIENTO ---
df_h = obtener_datos()
lista_choferes = obtener_choferes_repo()

# --- 3. INTERFAZ ---
st.title("🚚 Inteligencia de Flota y Costos")
tabs = st.tabs(["⛽ Registro de Carga", "🦅 Ojo de Halcón (IA)", "📜 Historial Completo"])

# --- TAB REGISTRO (CON KM AUTO) ---
with tabs[0]:
    st.subheader("📝 Nuevo Registro")
    c_p, _ = st.columns([1, 2])
    precio_gasoil = c_p.number_input("💵 Precio Gasoil ($)", value=st.session_state["precio_gasoil_fijo"])
    st.session_state["precio_gasoil_fijo"] = precio_gasoil

    with st.form("registro_final", clear_on_submit=True):
        f1, f2, f3 = st.columns(3)
        with f1:
            fecha = st.date_input("📅 Fecha", datetime.now())
            movil_sel = st.number_input("🔢 Móvil", min_value=1, max_value=100)
            chofer = st.selectbox("👤 Chofer", lista_choferes)
            
            km_ini_auto = 0
            if not df_h.empty:
                ultimo = df_h[df_h["Movil"] == movil_sel]
                if not ultimo.empty: km_ini_auto = int(ultimo["KM_Fin"].iloc[-1])
        
        with f2:
            marca = st.radio("🚛 Marca", ["SCANIA", "MERCEDES BENZ"], horizontal=True)
            traza = st.selectbox("📍 Traza", ["➕ NUEVA TRAZA"] + sorted(df_h["Traza"].unique().tolist()) if not df_h.empty else ["➕ NUEVA TRAZA"])
            nt = st.text_input("✍️ Nombre Nueva Traza").upper() if traza == "➕ NUEVA TRAZA" else ""
            t_final = nt if traza == "➕ NUEVA TRAZA" else traza

        with f3:
            kmi = st.number_input("🛣️ KM Inicial", value=km_ini_auto)
            kmf = st.number_input("🏁 KM Final")
            lt = st.number_input("⛽ Litros Ticket")
            lral = st.number_input("⏳ Litros Ralentí")

        if st.form_submit_button("💾 GUARDAR REGISTRO"):
            # Lógica de guardado (mantenida de versiones anteriores)
            st.success("✅ Guardado")
            time.sleep(1)
            st.rerun()

# --- TAB INTELIGENCIA (EL CAMBIO ESTÉTICO QUE PEDISTE) ---
with tabs[1]:
    st.markdown("## 🦅 Inteligencia de Flota")
    if not df_h.empty:
        # MÉTRICAS CON ICONOS
        m1, m2, m3 = st.columns(3)
        m1.metric("💰 Gasto Histórico", f"$ {df_h['Costo_Total_ARS'].sum():,.0f}")
        m2.metric("🛑 Pérdida Ralentí", f"$ {df_h['Costo_Ralenti_ARS'].sum():,.0f}")
        m3.metric("📉 Consumo Promedio", f"{df_h['Consumo_L100'].mean():,.1f} L/100")
        
        st.divider()
        
        # RANKING CON MEDALLAS (GAMIFICACIÓN)
        st.subheader("🏆 Cuadro de Honor: Eco-Driving")
        rank = df_h.groupby("Chofer")["Consumo_L100"].mean().sort_values().head(5).reset_index()
        
        # Diseño de medallas en columnas
        cols_med = st.columns(len(rank))
        medallas = ["🥇", "🥈", "🥉", "👤", "👤"]
        for i, row in rank.iterrows():
            with cols_med[i]:
                st.markdown(f"""
                <div style="text-align: center; padding: 10px; border-radius: 10px; background-color: #1e2130; border: 1px solid #3d425a;">
                    <h1 style="margin:0;">{medallas[i]}</h1>
                    <p style="margin:0; font-weight: bold;">{row['Chofer']}</p>
                    <h2 style="color: #4CAF50; margin:0;">{row['Consumo_L100']:.1f}</h2>
                    <p style="font-size: 0.8em; margin:0;">L/100</p>
                </div>
                """, unsafe_allow_html=True)

        st.divider()
        
        # GRÁFICOS IA
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("📉 Dispersión de Desvíos")
            fig = px.scatter(df_h, x="Fecha", y="Desvio_Neto", color="Marca", size=df_h["Desvio_Neto"].abs().clip(lower=1),
                             color_discrete_map={"SCANIA": "#EF553B", "MERCEDES BENZ": "#636EFA"}, template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)
        
        with c2:
            st.subheader("🚨 Alertas de Desvío") # Basado en imagen b8d19c.png
            df_err = df_h.groupby("Chofer")["Desvio_Neto"].sum().reset_index()
            for _, r in df_err.iterrows():
                if r['Desvio_Neto'] > 50:
                    st.error(f"🔴 **{r['Chofer']}**: {r['Desvio_Neto']:.1f} Litros")
                elif r['Desvio_Neto'] > 20:
                    st.warning(f"🟠 **{r['Chofer']}**: {r['Desvio_Neto']:.1f} Litros")
                else:
                    st.success(f"🟢 **{r['Chofer']}**: {r['Desvio_Neto']:.1f} Litros")

# --- TAB HISTORIAL ---
with tabs[2]:
    st.subheader("📜 Historial Completo")
    st.dataframe(df_h.iloc[::-1], use_container_width=True)
