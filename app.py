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

# --- TAB 2: OJO DE HALCÓN (DASHBOARD REDISEÑADO A RANKINGS VISUALES) ---
with tabs[1]:
    if not df_h.empty:
        # 3) PROMEDIO GENERAL DE FLOTA (Tarjetas Superiores Estilizadas)
        st.markdown("### 🦅 Estado General de la Flota")
        m1, m2, m3 = st.columns(3)
        prom_gral = df_h['Consumo_L100'].mean()
        
        with m1:
            st.markdown(f"""
                <div style="background:#1e2130; padding:20px; border-radius:10px; border-left: 5px solid #636EFA; text-align:center;">
                    <p style="margin:0; color:#aab; font-size:14px;">📉 PROMEDIO GENERAL FLOTA</p>
                    <h2 style="margin:0; color:white; font-size:36px;">{prom_gral:,.1f} <span style="font-size:18px;">L/100 KM</span></h2>
                </div>
            """, unsafe_allow_html=True)
            
        with m2:
            l_tot = df_h['L_Ticket'].sum()
            st.markdown(f"""
                <div style="background:#1e2130; padding:20px; border-radius:10px; border-left: 5px solid #00CC96; text-align:center;">
                    <p style="margin:0; color:#aab; font-size:14px;">⛽ TOTAL COMBUSTIBLE CARGADO</p>
                    <h2 style="margin:0; color:white; font-size:36px;">{l_tot:,.0f} <span style="font-size:18px;">LITROS</span></h2>
                </div>
            """, unsafe_allow_html=True)
            
        with m3:
            costo_tot = df_h['Costo_Total_ARS'].sum()
            st.markdown(f"""
                <div style="background:#1e2130; padding:20px; border-radius:10px; border-left: 5px solid #EF553B; text-align:center;">
                    <p style="margin:0; color:#aab; font-size:14px;">💰 GASTO TOTAL ACUMULADO</p>
                    <h2 style="margin:0; color:white; font-size:36px;">$ {costo_tot:,.0f}</h2>
                </div>
            """, unsafe_allow_html=True)

        st.divider()

        # 1) CUADRO DE HONOR: PROMEDIO POR RUTA (Estilo Medallas image_bab940.png)
        st.markdown("### 🏆 Cuadro de Honor: Eco-Driving por Ruta")
        
        # Función para renderizar el podio (Top 3)
        def render_podio_html(df_ranking, categoria, icono):
            st.markdown(f'<div class="category-header" style="background:#1e2130; padding:10px; border-radius:8px; text-align:center; margin-bottom:15px; border:1px solid #3d425a;"><h4>{icono} RUTA: {categoria.upper()}</h4></div>', unsafe_allow_html=True)
            
            if not df_ranking.empty:
                top_3 = df_ranking.head(3)
                cols = st.columns(3)
                medallas = ["🥇 ORO", "🥈 PLATA", "🥉 BRONCE"]
                colores_med = ["#FFD700", "#C0C0C0", "#CD7F32"]
                
                for i, row in top_3.iterrows():
                    with cols[i]:
                        st.markdown(f"""
                            <div style="background: linear-gradient(145deg, #1e2130, #25293d); padding: 20px; border-radius: 15px; text-align: center; border: 1px solid {colores_med[i]};">
                                <div style="font-size: 18px; font-weight:bold; color: {colores_med[i]};">{medallas[i]}</div>
                                <div style="font-weight: bold; font-size: 16px; color: white; margin-top:10px;">{row['Chofer']}</div>
                                <div style="font-size: 28px; color: #4CAF50; font-weight: bold;">{row['Consumo_L100']:.1f}</div>
                                <div style="color: #aab; font-size: 12px;">L/100 KM</div>
                            </div>
                        """, unsafe_allow_html=True)
            else:
                st.info(f"Sin datos en ruta {categoria}")

        # Ejecutamos los podios
        df_llano = df_h[df_h["Ruta"] == "Llano"].groupby("Chofer")["Consumo_L100"].mean().sort_values().reset_index()
        df_montana = df_h[df_h["Ruta"] == "Alta Montaña"].groupby("Consumo_L100"].mean().sort_values().reset_index()
        
        render_podio_html(df_llano, "Llano", "🟢")
        render_podio_html(df_montana, "Alta Montaña", "🔴")

        st.divider()

        # 2, 4 y 5) RANKINGS VISUALES (Reemplazo de los gráficos de barras por Listas de Honor)
        col_r1, col_r2, col_r3 = st.columns(3)

        with col_r1:
            # 2) DESVÍO DE COMBUSTIBLE CON TOLERANCIA (Semáforo visual)
            st.markdown("##### 🚨 Semáforo de Desvíos (Tolerancia 50L)")
            desvio_ch = df_h.groupby("Chofer")["Desvio_Neto"].sum().sort_values(ascending=False).reset_index()
            
            for _, row in desvio_ch.iterrows():
                # Lógica de colores semafórica
                color_bg = "#FF4B4B" if row['Desvio_Neto'] > 50 else "#1e2130"
                color_text = "white" if row['Desvio_Neto'] > 50 else "#aab"
                icono = "🚨 EXCESO" if row['Desvio_Neto'] > 50 else "✅ OK"
                
                st.markdown(f"""
                    <div style="background:{color_bg}; padding:10px; border-radius:8px; margin-bottom:5px; border:1px solid #3d425a; display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-weight:bold; color:{color_text};">{row['Chofer']}</span>
                        <div style="text-align:right;">
                            <span style="font-size:18px; font-weight:bold; color:{color_text};">{row['Desvio_Neto']:.1f} L</span>
                            <br><span style="font-size:11px; color:{color_text};">{icono}</span>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

        with col_r2:
            # 4) RANKING DE PROMEDIO DE LAS UNIDADES (Top 10 Eficiencia)
            st.markdown("##### 🔢 Listado Eficiencia por Unidad (Top 10)")
            rank_movil = df_h.groupby("Movil")["Consumo_L100"].mean().sort_values().head(10).reset_index()
            # Escala de colores GnBu_r para eficiencia
            colores_eff = px.colors.sequential.GnBu_r
            
            for i, row in rank_movil.iterrows():
                # Asignamos color de la escala según la posición
                color_idx = int((i / 10) * len(colores_eff))
                st.markdown(f"""
                    <div style="background:#1e2130; padding:10px; border-radius:8px; margin-bottom:5px; border:1px solid #3d425a; border-left: 5px solid {colores_eff[color_idx]}; display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-weight:bold; color:white;">Móvil {row['Movil']}</span>
                        <span style="font-size:18px; font-weight:bold; color:{colores_eff[color_idx]};">{row['Consumo_L100']:.1f} L/100</span>
                    </div>
                """, unsafe_allow_html=True)

        with col_r3:
            # 5) RANKING DE RALENTÍ POR CHOFERES (Top 10 Desperdicio)
            st.markdown("##### ⏳ Listado Desperdicio Ralentí (Top 10 L)")
            rank_ral = df_h.groupby("Chofer")["L_Ralenti"].sum().sort_values(ascending=False).head(10).reset_index()
            # Escala de colores Reds para desperdicio
            colores_waste = px.colors.sequential.Reds_r
            
            for i, row in rank_ral.iterrows():
                # Asignamos color de la escala Reds (invertido para que el mayor sea rojo fuerte)
                color_idx = int((i / 10) * len(colores_waste))
                st.markdown(f"""
                    <div style="background:#1e2130; padding:10px; border-radius:8px; margin-bottom:5px; border:1px solid #3d425a; border-left: 5px solid {colores_waste[color_idx]}; display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-weight:bold; color:white;">{row['Chofer']}</span>
                        <span style="font-size:18px; font-weight:bold; color:{colores_waste[color_idx]};">{row['L_Ralenti']:.1f} L</span>
                    </div>
                """, unsafe_allow_html=True)

    else:
        st.info("Sin datos para generar el Dashboard. Cargue registros primero.")
