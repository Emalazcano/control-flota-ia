import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
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
    .driver-name { font-weight: bold; font-size: 16px; margin: 5px 0; }
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
    df = conn.read(spreadsheet=URL, ttl=0)
    # Asegurar que las columnas críticas sean numéricas
    cols = ["Costo_Total_ARS", "L_Ticket", "Consumo_L100", "Desvio_Neto", "KM_Fin", "KM_Recorr"]
    for c in cols:
        if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
    return df

df_h = cargar_datos()

# --- 2. INTERFAZ ---
st.title("🚚 Inteligencia de Flota y Costos")
tabs = st.tabs(["⛽ Registro de Carga", "🦅 Ojo de Halcón (IA)", "📜 Historial"])

with tabs[0]:
    # Lógica de registro (se mantiene igual con KM auto-correlativo)
    st.subheader("📝 Nuevo Registro")
    # ... (resto del código de registro que ya tenemos funcionando)

# --- 3. LÓGICA ECO-DRIVING DIFERENCIADA ---
with tabs[1]:
    if not df_h.empty:
        # Métricas Generales
        m1, m2, m3 = st.columns(3)
        m1.metric("💰 Gasto Total", f"$ {df_h['Costo_Total_ARS'].sum():,.0f}")
        m2.metric("🛑 Pérdida Ralentí", f"$ {df_h['Costo_Ralenti_ARS'].sum():,.0f}")
        m3.metric("📉 Promedio Global", f"{df_h['Consumo_L100'].mean():,.1f} L/100")
        
        st.divider()
        st.markdown("### 🏆 Cuadro de Honor: Eco-Driving")

        # Función para renderizar el ranking por categoría
        def render_ranking(categoria):
            st.markdown(f'<div class="category-header"><h3>🏔️ Categoría: {categoria}</h3></div>', unsafe_allow_html=True)
            # Filtramos por tipo de ruta
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
                            <div style="font-size: 11px; color: #aab;">L/100 EN {categoria.upper()}</div>
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.info(f"No hay datos registrados para {categoria} todavía.")

        # Separación visual Llano vs Alta Montaña
        col_llano, col_montana = st.columns(2)
        with col_llano:
            render_ranking("Llano")
        with col_montana:
            render_ranking("Alta Montaña")

        st.divider()
        
        # Gráficos de apoyo (Dispersión se mantiene para ver tendencias)
        st.subheader("📉 Dispersión de Desvíos por Tipo de Ruta")
        fig = px.scatter(df_h, x="Fecha", y="Desvio_Neto", color="Ruta", 
                         size=df_h["Desvio_Neto"].abs().clip(lower=1),
                         template="plotly_dark", 
                         color_discrete_map={"Llano": "#00CC96", "Alta Montaña": "#EF553B"})
        st.plotly_chart(fig, use_container_width=True)

with tabs[2]:
    st.dataframe(df_h.iloc[::-1], use_container_width=True)
