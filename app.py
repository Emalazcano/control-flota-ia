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

# --- TAB 2: OJO DE HALCÓN (REDiseño VISUAL COMPLETO) ---
with tabs[1]:
    if not df_h.empty:
        # 3) PROMEDIO GENERAL DE FLOTA (Tarjetas Superiores)
        st.markdown("### 🦅 Inteligencia de Flota")
        m1, m2, m3 = st.columns(3)
        with m1:
            st.markdown(f'<div style="background:#1e2130; padding:20px; border-radius:10px; border-left: 5px solid #636EFA; text-align:center;">'
                        f'<p style="margin:0; color:#aab;">Promedio General</p>'
                        f'<h2 style="margin:0; color:white;">{df_h["Consumo_L100"].mean():,.1f} <span style="font-size:15px;">L/100</span></h2></div>', unsafe_allow_html=True)
        with m2:
            st.markdown(f'<div style="background:#1e2130; padding:20px; border-radius:10px; border-left: 5px solid #00CC96; text-align:center;">'
                        f'<p style="margin:0; color:#aab;">Total Combustible</p>'
                        f'<h2 style="margin:0; color:white;">{df_h["L_Ticket"].sum():,.0f} <span style="font-size:15px;">Litros</span></h2></div>', unsafe_allow_html=True)
        with m3:
            st.markdown(f'<div style="background:#1e2130; padding:20px; border-radius:10px; border-left: 5px solid #EF553B; text-align:center;">'
                        f'<p style="margin:0; color:#aab;">Gasto Acumulado</p>'
                        f'<h2 style="margin:0; color:white;">$ {df_h["Costo_Total_ARS"].sum():,.0f}</h2></div>', unsafe_allow_html=True)

        st.divider()

        # 1) CUADRO DE HONOR CON MEDALLAS (Ranking Choferes)
        st.markdown("### 🏆 Cuadro de Honor: Mejores Promedios")
        top_3 = df_h.groupby("Chofer")["Consumo_L100"].mean().sort_values().head(3).reset_index()
        medallas = ["🥇", "🥈", "🥉"]
        col_med1, col_med2, col_med3 = st.columns(3)
        
        for i, row in top_3.iterrows():
            with [col_med1, col_med2, col_med3][i]:
                st.markdown(f"""
                    <div style="background: linear-gradient(145deg, #1e2130, #25293d); padding: 25px; border-radius: 15px; text-align: center; border: 1px solid #3d425a;">
                        <div style="font-size: 50px;">{medallas[i]}</div>
                        <div style="font-weight: bold; font-size: 18px; color: white; margin-top:10px;">{row['Chofer']}</div>
                        <div style="font-size: 32px; color: #4CAF50; font-weight: bold;">{row['Consumo_L100']:.1f}</div>
                        <div style="color: #aab; font-size: 14px;">L/100 KM</div>
                    </div>
                """, unsafe_allow_html=True)

        st.divider()

        # 1.1) DETALLE POR RUTA
        st.markdown("##### 📍 Rendimiento por Tipo de Ruta")
        cr1, cr2 = st.columns(2)
        with cr1:
            st.markdown('<p style="text-align:center; color:#00CC96;">🟢 RUTA: LLANO</p>', unsafe_allow_html=True)
            df_llano = df_h[df_h["Ruta"] == "Llano"].groupby("Chofer")["Consumo_L100"].mean().sort_values().reset_index()
            st.dataframe(df_llano.rename(columns={"Consumo_L100": "Promedio L/100"}), use_container_width=True, hide_index=True)
        with cr2:
            st.markdown('<p style="text-align:center; color:#EF553B;">🔴 RUTA: ALTA MONTAÑA</p>', unsafe_allow_html=True)
            df_montana = df_h[df_h["Ruta"] == "Alta Montaña"].groupby("Chofer")["Consumo_L100"].mean().sort_values().reset_index()
            st.dataframe(df_montana.rename(columns={"Consumo_L100": "Promedio L/100"}), use_container_width=True, hide_index=True)

        st.divider()

        # 2) DESVÍO CON TOLERANCIA (Visualización Limpia)
        st.markdown("### ⚠️ Control de Desvíos de Combustible")
        desvio_ch = df_h.groupby("Chofer")["Desvio_Neto"].sum().reset_index()
        desvio_ch["Alerta"] = desvio_ch["Desvio_Neto"].apply(lambda x: "🚨 EXCESO (>50L)" if x > 50 else "✅ DENTRO DE LÍMITE")
        
        fig_desvio = px.bar(desvio_ch, x="Desvio_Neto", y="Chofer", orientation='h',
                            color="Alerta", color_discrete_map={"🚨 EXCESO (>50L)": "#FF4B4B", "✅ DENTRO DE LÍMITE": "#00CC96"},
                            template="plotly_dark", barmode="group")
        fig_desvio.add_vline(x=50, line_dash="dash", line_color="#FFD700", annotation_text="Límite 50L")
        fig_desvio.update_layout(showlegend=True, margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig_desvio, use_container_width=True)

        st.divider()

        # 4 y 5) RANKING UNIDADES Y RALENTÍ
        col_f1, col_f2 = st.columns(2)
        
        with col_f1:
            st.markdown("##### 🔢 Eficiencia por Unidad (Móviles)")
            rank_movil = df_h.groupby("Movil")["Consumo_L100"].mean().sort_values().head(10).reset_index()
            fig_mov = px.bar(rank_movil, x="Consumo_L100", y="Movil", orientation='h',
                             color="Consumo_L100", color_continuous_scale="GnBu_r", template="plotly_dark")
            fig_mov.update_layout(yaxis={'type':'category'})
            st.plotly_chart(fig_mov, use_container_width=True)

        with col_f2:
            st.markdown("##### ⏳ Pérdida por Ralentí Acumulado")
            rank_ral = df_h.groupby("Chofer")["L_Ralenti"].sum().sort_values(ascending=False).head(10).reset_index()
            fig_ral = px.bar(rank_ral, x="L_Ralenti", y="Chofer", orientation='h',
                             color="L_Ralenti", color_continuous_scale="Reds", template="plotly_dark")
            st.plotly_chart(fig_ral, use_container_width=True)

    else:
        st.info("Sin datos para el Dashboard.")
