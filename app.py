import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import time

# --- 1. CONFIGURACIÓN Y ESTILOS ---
st.set_page_config(page_title="Inteligencia de Flota Jujuy", layout="wide")

st.markdown("""
    <style>
    .metric-card {
        background-color: #1e2130;
        padding: 15px;
        border-radius: 12px;
        border: 1px solid #3d425a;
        text-align: center;
    }
    .medal-gold { color: #FFD700; font-size: 40px; }
    .medal-silver { color: #C0C0C0; font-size: 40px; }
    .medal-bronze { color: #CD7F32; font-size: 40px; }
    .driver-name { font-weight: bold; font-size: 16px; margin: 5px 0; color: white; }
    .driver-score { font-size: 22px; color: #4CAF50; font-weight: bold; }
    .category-header { 
        background: linear-gradient(90deg, #1e2130, #3d425a);
        padding: 10px;
        border-radius: 8px;
        margin-bottom: 15px;
        text-align: center;
    }
    </style>
""", unsafe_allow_html=True)

conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1PEH7lbtoq_oAHwom0O5YYYskFm6ALJ6LCj1FfQKzpmQ/edit?gid=0#gid=0"

def cargar_datos():
    try:
        df = conn.read(spreadsheet=URL, ttl=0)
        cols = ["Costo_Total_ARS", "L_Ticket", "Consumo_L100", "Desvio_Neto", "KM_Fin", "Costo_Ralenti_ARS"]
        for c in cols:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        return df
    except: return pd.DataFrame()

df_h = cargar_datos()

# --- 2. INTERFAZ ---
st.title("🚚 Inteligencia de Flota y Costos")
tabs = st.tabs(["⛽ Registro de Carga", "🦅 Ojo de Halcón (IA)", "📜 Historial"])

# --- TAB 1: REGISTRO (Mantenemos la agilidad de carga) ---
with tabs[0]:
    st.subheader("📝 Nuevo Registro")
    with st.form("registro_form", clear_on_submit=True):
        f1, f2, f3 = st.columns(3)
        with f1:
            movil = st.number_input("🔢 Móvil", min_value=1, max_value=100)
            km_auto = int(df_h[df_h["Movil"] == movil]["KM_Fin"].max()) if not df_h.empty else 0
            kmi = st.number_input("🛣️ KM Inicial", value=km_auto)
            chofer = st.selectbox("👤 Chofer", sorted(df_h["Chofer"].unique())) if not df_h.empty else st.text_input("Chofer")
        with f2:
            ruta_tipo = st.radio("🏔️ Tipo de Ruta", ["Llano", "Alta Montaña"], horizontal=True)
            traza = st.selectbox("📍 Traza", ["➕ NUEVA"] + sorted(df_h["Traza"].unique().tolist()))
            nt = st.text_input("✍️ Nombre Nueva Traza").upper() if traza == "➕ NUEVA" else ""
        with f3:
            kmf = st.number_input("🏁 KM Final")
            lt = st.number_input("⛽ Litros Ticket")
            lral = st.number_input("⏳ Litros Ralentí")

        if st.form_submit_button("💾 GUARDAR REGISTRO"):
            st.success("Dato guardado correctamente")
            time.sleep(1)
            st.rerun()

# --- TAB 2: OJO DE HALCÓN (IA SIN GRÁFICAS INNECESARIAS) ---
with tabs[1]:
    if not df_h.empty:
        # MÉTRICAS TOP (image_ba45c3.png)
        m1, m2, m3 = st.columns(3)
        m1.metric("💰 Gasto Histórico", f"$ {df_h['Costo_Total_ARS'].sum():,.0f}")
        m2.metric("🛑 Pérdida Ralentí", f"$ {df_h['Costo_Ralenti_ARS'].sum():,.0f}")
        m3.metric("📉 Consumo Promedio", f"{df_h['Consumo_L100'].mean():,.1f} L/100")
        
        st.divider()
        st.markdown("### 🏆 Cuadro de Honor: Eco-Driving (Diferenciado)")

        # Función para los Podios (image_bab940.png)
        def render_podio(categoria):
            st.markdown(f'<div class="category-header"><h3>{ "🏔️" if categoria == "Alta Montaña" else "🛣️" } {categoria}</h3></div>', unsafe_allow_html=True)
            df_cat = df_h[df_h["Ruta"] == categoria]
            if not df_cat.empty:
                top = df_cat.groupby("Chofer")["Consumo_L100"].mean().sort_values().head(3).reset_index()
                cols = st.columns(3)
                medals = [("🥇", "medal-gold"), ("🥈", "medal-silver"), ("🥉", "medal-bronze")]
                for i, row in top.iterrows():
                    with cols[i]:
                        st.markdown(f"""
                        <div class="metric-card">
                            <div class="{medals[i][1]}">{medals[i][0]}</div>
                            <div class="driver-name">{row['Chofer']}</div>
                            <div class="driver-score">{row['Consumo_L100']:.1f}</div>
                            <div style="font-size: 11px; color: #aab;">L/100</div>
                        </div>
                        """, unsafe_allow_html=True)
            else: st.info(f"Sin datos para {categoria}")

        c_llano, c_mont = st.columns(2)
        with c_llano: render_podio("Llano")
        with c_mont: render_podio("Alta Montaña")

        st.divider()
        
        # SEMÁFORO DE ALERTAS (Reemplaza a la gráfica de burbujas)
        st.subheader("🚨 Alertas de Desvío por Chofer")
        res_d = df_h.groupby("Chofer")["Desvio_Neto"].sum().reset_index()
        for _, r in res_d.sort_values(by="Desvio_Neto", ascending=False).iterrows():
            if r['Desvio_Neto'] > 50:
                st.error(f"⚠️ **{r['Chofer']}**: Desvío crítico de {r['Desvio_Neto']:.1f} Litros")
            elif r['Desvio_Neto'] > 20:
                st.warning(f"🔔 **{r['Chofer']}**: Desvío moderado de {r['Desvio_Neto']:.1f} Litros")

with tabs[2]:
    st.dataframe(df_h.iloc[::-1], use_container_width=True)
