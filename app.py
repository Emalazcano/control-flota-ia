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

# --- TAB 2: OJO DE HALCÓN (RANKING EJECUTIVO FINAL) ---
with tabs[1]:
    if not df_h.empty:
        # 3) MÉTRICAS DE CABECERA
        st.markdown("### 🦅 Inteligencia de Flota")
        m1, m2, m3 = st.columns(3)
        with m1:
            st.markdown(f'<div style="background:#1e2130; padding:20px; border-radius:12px; border-left: 5px solid #636EFA; text-align:center;"><p style="margin:0; color:#aab; font-size:14px;">📉 PROMEDIO FLOTA</p><h2 style="margin:0; color:white;">{df_h["Consumo_L100"].mean():,.1f} <span style="font-size:16px;">L/100</span></h2></div>', unsafe_allow_html=True)
        with m2:
            st.markdown(f'<div style="background:#1e2130; padding:20px; border-radius:12px; border-left: 5px solid #00CC96; text-align:center;"><p style="margin:0; color:#aab; font-size:14px;">⛽ TOTAL CARGADO</p><h2 style="margin:0; color:white;">{df_h["L_Ticket"].sum():,.0f} <span style="font-size:16px;">Lts</span></h2></div>', unsafe_allow_html=True)
        with m3:
            st.markdown(f'<div style="background:#1e2130; padding:20px; border-radius:12px; border-left: 5px solid #EF553B; text-align:center;"><p style="margin:0; color:#aab; font-size:14px;">💰 INVERSIÓN TOTAL</p><h2 style="margin:0; color:white;">$ {df_h["Costo_Total_ARS"].sum():,.0f}</h2></div>', unsafe_allow_html=True)

        st.divider()

        # 1) CUADRO DE HONOR: ECO-DRIVING (image_bab940.png)
        st.markdown("### 🏆 Cuadro de Honor: Eco-Driving")
        top_5 = df_h.groupby("Chofer")["Consumo_L100"].mean().sort_values().head(5).reset_index()
        cols = st.columns(5)
        # Usamos los iconos y estilos exactos de tu captura
        iconos = ["🥇", "🥈", "🥉", "👤", "👤"]
        for i, row in top_5.iterrows():
            with cols[i]:
                st.markdown(f"""
                    <div style="background:#1e2130; padding:15px; border-radius:10px; border:1px solid #3d425a; text-align:center; min-height:190px;">
                        <div style="font-size:40px; filter: drop-shadow(0 0 5px rgba(255,255,255,0.2));">{iconos[i]}</div>
                        <div style="font-weight:bold; color:white; font-size:14px; margin:15px 0;">{row['Chofer']}</div>
                        <div style="font-size:30px; color:#4CAF50; font-weight:bold;">{row['Consumo_L100']:.1f}</div>
                        <div style="color:#aab; font-size:12px;">L/100</div>
                    </div>
                """, unsafe_allow_html=True)

        st.divider()

        # 2) RANKING DE DESVÍO DE COMBUSTIBLE (Sustituye imagen_c607c2.png por Ranking)
        st.markdown("### ⚠️ Ranking de Alerta: Control de Desvíos")
        st.info("Tolerancia máxima permitida: 50 Litros")
        
        df_desv = df_h.groupby("Chofer")["Desvio_Neto"].sum().sort_values(ascending=False).reset_index()
        
        # Layout de dos columnas para no hacer la lista eterna
        col_alert1, col_alert2 = st.columns(2)
        
        for i, row in df_desv.iterrows():
            # Definir estilo si supera la tolerancia de 50L
            exceso = row['Desvio_Neto'] > 50
            bg_color = "#421212" if exceso else "#1e2130"
            border_color = "#FF4B4B" if exceso else "#3d425a"
            text_color = "#FF4B4B" if exceso else "#00CC96"
            label = "🚨 EXCESO" if exceso else "✅ DENTRO DEL LÍMITE"
            
            target_col = col_alert1 if i % 2 == 0 else col_alert2
            
            with target_col:
                st.markdown(f"""
                    <div style="background:{bg_color}; padding:12px; border-radius:8px; border:1px solid {border_color}; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <div style="font-weight:bold; color:white; font-size:15px;">{row['Chofer']}</div>
                            <div style="font-size:11px; color:{text_color}; font-weight:bold;">{label}</div>
                        </div>
                        <div style="text-align:right;">
                            <div style="font-size:22px; font-weight:bold; color:white;">{row['Desvio_Neto']:.1f} <span style="font-size:12px;">Lts</span></div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

        st.divider()

        # 4 y 5) RANKINGS DE UNIDADES Y RALENTÍ (image_c600bc.png)
        st.markdown("### 📊 Análisis de Eficiencia y Ralentí")
        c_low1, c_low2 = st.columns(2)
        
        with c_low1:
            st.markdown("##### 🔢 Ranking por Unidad (Móviles)")
            rank_m = df_h.groupby("Movil")["Consumo_L100"].mean().sort_values(ascending=True).head(10).reset_index()
            # Mostramos como tabla de ranking limpia
            for i, row in rank_m.iterrows():
                st.markdown(f"""
                    <div style="background:#1e2130; padding:8px 15px; border-radius:6px; margin-bottom:4px; border-left:4px solid #00CC96; display:flex; justify-content:space-between;">
                        <span style="color:white;">#{i+1} Móvil <b>{row['Movil']}</b></span>
                        <span style="color:#00CC96; font-weight:bold;">{row['Consumo_L100']:.1f} L/100</span>
                    </div>
                """, unsafe_allow_html=True)

        with c_low2:
            st.markdown("##### ⏳ Ranking Desperdicio Ralentí")
            rank_r = df_h.groupby("Chofer")["L_Ralenti"].sum().sort_values(ascending=False).head(10).reset_index()
            for i, row in rank_r.iterrows():
                st.markdown(f"""
                    <div style="background:#1e2130; padding:8px 15px; border-radius:6px; margin-bottom:4px; border-left:4px solid #EF553B; display:flex; justify-content:space-between;">
                        <span style="color:white;">{row['Chofer']}</span>
                        <span style="color:#EF553B; font-weight:bold;">{row['L_Ralenti']:.1f} Lts</span>
                    </div>
                """, unsafe_allow_html=True)

    else:
        st.warning("No hay datos cargados para generar los rankings.")
