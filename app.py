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
    .driver-score { font-size: 24px; color: #4CAF50; font-weight: bold; }
    .medal-icon { font-size: 32px; margin-bottom: 5px; }
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
            else: 
                st.error("Clave incorrecta")
    st.stop()

# --- 3. CONEXIÓN Y DATOS ---
conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1PEH7lbtoq_oAHwom0O5YYYskFm6ALJ6LCj1FfQKzpmQ/edit?gid=0#gid=0"

if "precio_gasoil" not in st.session_state:
    st.session_state["precio_gasoil"] = 2065.0

def cargar_historial():
    try:
        df = conn.read(spreadsheet=URL, ttl=0)
        num_cols = ["Movil", "KM_Fin", "KM_Ini", "L_Ticket", "L_Tablero", "L_Ralenti", "Desvio_Neto", "Consumo_L100", "Costo_Total_ARS"]
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        if 'Fecha' in df.columns:
            df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=True, errors='coerce')
            df['Fecha'] = df['Fecha'].fillna(pd.Timestamp.now().normalize())
        return df
    except: return pd.DataFrame()

df_h = cargar_historial()

# --- 4. INTERFAZ ---
st.title("🚚 Inteligencia de Flota y Costos")
tabs = st.tabs(["⛽ Registro de Carga", "🦅 Ojo de Halcón", "📜 Historial"])

# --- TAB 1: REGISTRO ---
with tabs[0]:
    st.subheader("📝 Nuevo Registro")
    
    def limpiar_sesion_form():
        for k in ["kmf_k", "lt_k", "ltab_k", "lral_k", "nt_k"]:
            if k in st.session_state:
                st.session_state[k] = 0.0 if k != "nt_k" else ""

    movil_sel = st.selectbox("🔢 Móvil", list(range(1, 101)), index=36)
    
    km_sugerido = 0.0
    if not df_h.empty:
        ult_m = df_h[df_h["Movil"] == movil_sel]
        if not ult_m.empty:
            km_sugerido = float(ult_m.sort_values("Fecha").iloc[-1]["KM_Fin"])

    with st.form("registro_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            marca = st.radio("🏷️ Marca", ["SCANIA", "MERCEDES BENZ"], horizontal=True)
            chofer_lista = sorted(df_h["Chofer"].unique().tolist()) if not df_h.empty else ["NUEVO"]
            chofer = st.selectbox("👤 Chofer", chofer_lista)
            precio_comb = st.number_input("💰 Precio Litro Gasoil", value=float(st.session_state["precio_gasoil"]))
            fecha_input = st.date_input("📅 Fecha de Carga", datetime.now())
        with col2:
            ruta_tipo = st.radio("🏔️ Tipo de Ruta", ["Llano", "Alta Montaña"], horizontal=True)
            trazas_disponibles = ["➕ NUEVA"] + (sorted(df_h["Traza"].unique().tolist()) if not df_h.empty else [])
            traza_sel = st.selectbox("🗺️ Traza", trazas_disponibles)
            nt = st.text_input("✍️ Nombre Nueva Traza", key="nt_k").upper()
            t_final = nt if (traza_sel == "➕ NUEVA" and nt != "") else traza_sel
        with col3:
            kmi = st.number_input("🛣️ KM Inicial", value=float(km_sugerido))
            kmf = st.number_input("🏁 KM Final", key="kmf_k")
            lt = st.number_input("⛽ Litros Ticket", key="lt_k")
            ltab = st.number_input("📟 Litros Tablero", key="ltab_k")
            lral = st.number_input("⏳ Litros Ralentí", key="lral_k")

        if st.form_submit_button("💾 GUARDAR REGISTRO", use_container_width=True):
            dist = kmf - kmi
            cons = (lt / dist * 100) if dist > 0 else 0
            costo_viaje = round(lt * precio_comb, 2)
            desv = lt - (ltab + lral)

            if kmf <= kmi or lt <= 0 or t_final == "":
                st.error("⚠️ Datos inválidos.")
            else:
                nuevo_reg = {
                    "Fecha": fecha_input.strftime('%d/%m/%Y'),
                    "Chofer": chofer, "Movil": movil_sel, "Marca": marca,
                    "Ruta": ruta_tipo, "Traza": t_final, "KM_Ini": kmi, "KM_Fin": kmf,
                    "KM_Recorr": dist, "L_Ticket": lt, "L_Tablero": ltab, "L_Ralenti": lral,
                    "Consumo_L100": round(cons, 2), 
                    "Costo_Total_ARS": costo_viaje, 
                    "Desvio_Neto": round(desv, 2)
                }
                with st.spinner("Guardando..."):
                    df_final = pd.concat([df_h, pd.DataFrame([nuevo_reg])], ignore_index=True)
                    conn.update(spreadsheet=URL, data=df_final)
                    st.session_state["precio_gasoil"] = precio_comb
                    limpiar_sesion_form()
                    st.success(f"✅ Guardado el {fecha_input.strftime('%d/%m/%Y')}")
                    time.sleep(1)
                    st.rerun()

# --- TAB 2: OJO DE HALCÓN ---
with tabs[1]:
    if not df_h.empty:
        df_ana = df_h.copy()
        df_ana['Mes_Año'] = df_ana['Fecha'].dt.to_period('M').astype(str)
        
        st.markdown("### 🔍 Filtros de Inteligencia")
        c_f1, c_f2 = st.columns(2)
        with c_f1:
            mes_sel = st.selectbox("📅 Mes de Análisis", ["Todos"] + sorted(df_ana['Mes_Año'].unique().tolist(), reverse=True))
        with c_f2:
            ruta_sel = st.multiselect("🏔️ Filtrar por Ruta", df_ana['Ruta'].unique(), default=df_ana['Ruta'].unique())

        df_filtrado = df_ana[df_ana['Ruta'].isin(ruta_sel)]
        if mes_sel != "Todos":
            df_filtrado = df_filtrado[df_filtrado['Mes_Año'] == mes_sel]

        # 1. MÉTRICAS CLAVE
        st.divider()
        m1, m2, m3 = st.columns(3)
        m1.markdown(f'<div class="metric-card" style="border-left:5px solid #636EFA;"><p style="color:#aab;font-size:14px;">📉 PROMEDIO FLOTA</p><h2>{df_filtrado["Consumo_L100"].mean():,.1f} L/100</h2></div>', unsafe_allow_html=True)
        m2.markdown(f'<div class="metric-card" style="border-left:5px solid #00CC96;"><p style="color:#aab;font-size:14px;">⛽ TOTAL LITROS</p><h2>{df_filtrado["L_Ticket"].sum():,.0f} Lts</h2></div>', unsafe_allow_html=True)
        m3.markdown(f'<div class="metric-card" style="border-left:5px solid #EF553B;"><p style="color:#aab;font-size:14px;">💰 INVERSIÓN TOTAL</p><h2>$ {df_filtrado["Costo_Total_ARS"].sum():,.0f}</h2></div>', unsafe_allow_html=True)

        # 2. CUADRO DE HONOR Y DESVÍOS
        st.divider()
        col_rank, col_desv = st.columns([0.6, 0.4])
        
        with col_rank:
            st.subheader("🏆 Ranking de Eficiencia (Top 5)")
            top_5 = df_filtrado.groupby("Chofer")["Consumo_L100"].mean().sort_values().head(5).reset_index()
            cols = st.columns(5)
            medallas = ["🥇", "🥈", "🥉", "👤", "👤"]
            for i, row in top_5.iterrows():
                with cols[i]:
                    st.markdown(f'<div class="metric-card"><div class="medal-icon">{medallas[i]}</div><div class="driver-name">{row["Chofer"]}</div><div class="driver-score">{row["Consumo_L100"]:.1f}</div></div>', unsafe_allow_html=True)

        with col_desv:
            st.subheader("⚠️ Desvíos")
            df_desv = df_filtrado.groupby("Chofer")["Desvio_Neto"].sum().sort_values(ascending=False).reset_index()
            for i, row in df_desv.head(4).iterrows():
                exc = row['Desvio_Neto'] > 50
                st.markdown(f'<div style="background:{"#421212" if exc else "#1e2130"};padding:12px;border-radius:8px;border:1px solid {"#FF4B4B" if exc else "#3d425a"};margin-bottom:8px;display:flex;justify-content:space-between;align-items:center;"><b style="color:white;">{row["Chofer"]}</b><b style="color:white;">{row["Desvio_Neto"]:.1f} L</b></div>', unsafe_allow_html=True)

        # 3. GRÁFICOS (REINTEGRADOS)
        st.divider()
        st.subheader("📊 Análisis Visual de Flota")
        g1, g2 = st.columns(2)
        with g1:
            df_t = df_ana.groupby('Mes_Año')['Consumo_L100'].mean().reset_index()
            fig_t = px.area(df_t, x='Mes_Año', y='Consumo_L100', title="📈 Evolución de Consumo", color_discrete_sequence=["#00FFC8"])
            fig_t.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_t, use_container_width=True)
        with g2:
            df_m = df_filtrado.groupby("Marca")["Consumo_L100"].mean().reset_index()
            fig_m = px.bar(df_m, x='Marca', y='Consumo_L100', title="🚛 Consumo por Marca", color='Marca', color_discrete_map={"SCANIA": "#EF553B", "MERCEDES BENZ": "#636EFA"})
            fig_m.update_layout(template="plotly_dark", showlegend=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_m, use_container_width=True)

# --- TAB 3: HISTORIAL ---
with tabs[2]:
    if not df_h.empty:
        df_v = df_h.copy()
        df_v['Fecha'] = df_v['Fecha'].dt.strftime('%d/%m/%Y')
        st.dataframe(df_v.sort_values("Fecha", ascending=False), use_container_width=True)
