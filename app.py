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
        num_cols = ["Movil", "KM_Fin", "KM_Ini", "L_Ticket", "L_Tablero", "L_Ralenti", "Desvio_Neto", "Consumo_L100", "Costo_Total_ARS"]
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        if 'Fecha' in df.columns:
            df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=True, errors='coerce')
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
    movil_sel = st.selectbox("🔢 Móvil", list(range(1, 101)), index=36)
    
    km_sugerido = 0.0
    if not df_h.empty:
        try:
            m_buscado = float(movil_sel)
            ult_reg = df_h[df_h["Movil"] == m_buscado]
            if not ult_reg.empty:
                ult_reg = ult_reg.sort_values("Fecha")
                km_sugerido = float(ult_reg.iloc[-1]["KM_Fin"])
        except: km_sugerido = 0.0

    if km_sugerido > 0:
        st.success(f"✅ KM Inicial recuperado: {km_sugerido}")
    else:
        st.info(f"ℹ️ No hay registros previos para el móvil {movil_sel}")

    with st.form("registro_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("##### 🚛 Vehículo")             
            marca = st.radio("🏷️ Marca", ["SCANIA", "MERCEDES BENZ"], horizontal=True)
            chofer = st.selectbox("👤 Chofer", lista_choferes)
            st.session_state["precio_gasoil"] = st.number_input("💰 Precio Litro Gasoil", value=float(st.session_state["precio_gasoil"]))
            fecha_sel = st.date_input("📅 Fecha de Carga", datetime.now())
        with col2:
            st.markdown("##### 📍 Ruta")
            ruta_tipo = st.radio("🏔️ Tipo de Ruta", ["Llano", "Alta Montaña"], horizontal=True)
            traza_existente = ["➕ NUEVA"] + (sorted(df_h["Traza"].unique().tolist()) if not df_h.empty else [])
            traza = st.selectbox("🗺️ Traza", traza_existente)
            nt = st.text_input("✍️ Nombre Nueva Traza").upper()
            t_final = nt if (traza == "➕ NUEVA" and nt != "") else traza
        with col3:
            st.markdown("##### ⛽ Consumo")
            kmi = st.number_input("🛣️ KM Inicial", value=float(km_sugerido))
            kmf = st.number_input("🏁 KM Final")
            lt = st.number_input("⛽ Litros Ticket")
            ltab = st.number_input("📟 Litros Tablero")
            lral = st.number_input("⏳ Litros Ralentí")

            distancia = kmf - kmi
            consumo = (lt / distancia * 100) if distancia > 0 else 0
            costo_t = lt * st.session_state["precio_gasoil"]
            desvio_n = lt - (ltab + lral)

            if distancia > 0:
                st.divider()
                st.info(f"📏 Recorrido: **{distancia} KM**")
                st.info(f"📊 Consumo: **{consumo:.1f} L/100**")
                st.info(f"💰 Costo: **${costo_t:,.0f}**")
                if 10 <= consumo < 15 or 80 < consumo <= 120:
                    st.warning(f"⚠️ Consumo inusual ({consumo:.1f} L/100).")
                elif consumo < 10 or consumo > 120:
                    st.error(f"🚨 ERROR: Consumo ({consumo:.1f} L/100) ilógico.")

        submit = st.form_submit_button("💾 GUARDAR REGISTRO", use_container_width=True)
        if submit:
            if kmf <= kmi or lt <= 0 or t_final == "":
                st.error("⚠️ Datos inválidos.")
            elif consumo < 10 or consumo > 120:
                st.error(f"❌ No se puede guardar: Consumo imposible ({consumo:.1f}).")
            else:
                nuevo_reg = {
                    "Fecha": fecha_sel.strftime('%d/%m/%Y'),
                    "Chofer": chofer, "Movil": movil_sel, "Marca": marca,
                    "Ruta": ruta_tipo, "Traza": t_final, "KM_Ini": kmi, "KM_Fin": kmf,
                    "KM_Recorr": distancia, "L_Ticket": lt, "L_Tablero": ltab, "L_Ralenti": lral,
                    "Consumo_L100": round(consumo, 2), "Costo_Total_ARS": round(costo_t, 2), "Desvio_Neto": round(desvio_n, 2)
                }
                with st.spinner("Guardando..."):
                    df_final = pd.concat([df_h, pd.DataFrame([nuevo_reg])], ignore_index=True)
                    conn.update(spreadsheet=URL, data=df_final)
                    st.success("✅ ¡Registro guardado!")
                    time.sleep(1)
                    st.rerun()

# --- TAB 2: OJO DE HALCÓN ---
with tabs[1]:
    if not df_h.empty:
        df_ana = df_h.dropna(subset=['Fecha']).copy()
        df_ana['Mes_Año'] = df_ana['Fecha'].dt.to_period('M').astype(str)
        
        st.markdown("### 🔍 Inteligencia de Datos")
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
        m1.markdown(f'<div class="metric-card" style="border-left:5px solid #636EFA;"><p style="color:#aab;font-size:14px;">📉 PROMEDIO</p><h2>{df_filtrado["Consumo_L100"].mean():,.1f} L/100</h2></div>', unsafe_allow_html=True)
        m2.markdown(f'<div class="metric-card" style="border-left:5px solid #00CC96;"><p style="color:#aab;font-size:14px;">⛽ TOTAL CARGADO</p><h2>{df_filtrado["L_Ticket"].sum():,.0f} Lts</h2></div>', unsafe_allow_html=True)
        m3.markdown(f'<div class="metric-card" style="border-left:5px solid #EF553B;"><p style="color:#aab;font-size:14px;">💰 INVERSIÓN</p><h2>$ {df_filtrado["Costo_Total_ARS"].sum():,.0f}</h2></div>', unsafe_allow_html=True)

        # 2. CUADRO DE HONOR Y DESVÍOS
        st.divider()
        st.markdown("### 🏆 Ranking de Eficiencia y ⚠️ Desvíos")
        top_5 = df_filtrado.groupby("Chofer")["Consumo_L100"].mean().sort_values().head(5).reset_index()
        cols = st.columns(5)
        iconos = ["🥇", "🥈", "🥉", "👤", "👤"]
        for i, row in top_5.iterrows():
            if i < len(cols):
                with cols[i]:
                    st.markdown(f'<div class="metric-card"><div style="font-size:40px;">{iconos[i]}</div><div class="driver-name">{row["Chofer"]}</div><div class="driver-score">{row["Consumo_L100"]:.1f}</div><div style="color:#aab;font-size:12px;">L/100</div></div>', unsafe_allow_html=True)

        st.markdown("##### Historial de Desvíos Mensuales")
        df_desv = df_filtrado.groupby("Chofer")["Desvio_Neto"].sum().sort_values(ascending=False).reset_index()
        ca1, ca2 = st.columns(2)
        for i, row in df_desv.iterrows():
            exc = row['Desvio_Neto'] > 50
            target = ca1 if i % 2 == 0 else ca2
            target.markdown(f'<div style="background:{"#421212" if exc else "#1e2130"};padding:12px;border-radius:8px;border:1px solid {"#FF4B4B" if exc else "#3d425a"};margin-bottom:8px;display:flex;justify-content:space-between;align-items:center;"><div><b style="color:white;">{row["Chofer"]}</b><br><small style="color:{"#FF4B4B" if exc else "#00CC96"};">{"🚨 EXCESO" if exc else "✅ OK"}</small></div><b style="font-size:20px;color:white;">{row["Desvio_Neto"]:.1f} L</b></div>', unsafe_allow_html=True)

        # 3. GRÁFICOS AL FINAL (IMPACTO VISUAL)
        st.divider()
        st.markdown("### 📊 Inteligencia de Datos Avanzada")
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            df_t = df_ana.groupby('Mes_Año')['Consumo_L100'].mean().reset_index()
            fig_t = px.area(df_t, x='Mes_Año', y='Consumo_L100', title="📈 Evolución de Consumo", color_discrete_sequence=["#00FFC8"])
            fig_t.update_traces(mode="lines+markers", line_shape="spline", line_width=3)
            fig_t.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_t, use_container_width=True)
        with col_g2:
            df_m = df_filtrado.groupby("Marca")["Consumo_L100"].mean().reset_index()
            fig_m = px.bar(df_m, x='Marca', y='Consumo_L100', title="🚛 Scania vs Mercedes (L/100)", color='Marca', color_discrete_map={"SCANIA": "#EF553B", "MERCEDES BENZ": "#636EFA"})
            fig_m.update_traces(textposition="outside", texttemplate='%{y:.1f}')
            fig_m.update_layout(template="plotly_dark", showlegend=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_m, use_container_width=True)

# --- TAB 3: HISTORIAL ---
with tabs[2]:
    st.subheader("📜 Registros Guardados")
    if not df_h.empty:
        df_display = df_h.copy()
        df_display['Fecha'] = pd.to_datetime(df_display['Fecha']).dt.strftime('%d/%m/%Y')
        st.dataframe(df_display.sort_values("Fecha", ascending=False), use_container_width=True)
