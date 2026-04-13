import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime
import time
import os

# --- 1. CONFIGURACIÓN Y ESTILOS ---
st.set_page_config(page_title="Inteligencia de Flota Jujuy", layout="wide")

# CSS MEJORADO: Restaurado diseño profesional y colores nítidos
st.markdown("""
    <style>
    .metric-card { background-color: #1e2130; padding: 15px; border-radius: 12px; border: 1px solid #3d425a; text-align: center; }
    .driver-name { font-weight: bold; font-size: 16px; margin: 5px 0; color: white; }
    .driver-score { font-size: 24px; color: #4CAF50; font-weight: bold; }
    .medal-icon { font-size: 32px; margin-bottom: 5px; }
    
    /* Estilos para las tarjetas de desvío (RESTAURADOS) */
    .desvio-item { 
        padding: 12px; 
        border-radius: 8px; 
        margin-bottom: 10px; 
        display: flex; 
        justify-content: space-between; 
        align-items: center; 
        border: 1px solid #3d425a;
        transition: transform 0.2s; /* Un toquecito de hover */
    }
    .desvio-item:hover { transform: scale(1.02); }
    .desvio-critico { background: #421212 !important; border: 1px solid #FF4B4B !important; }
    .desvio-ok { background: #0c2b18 !important; border: 1px solid #00CC96 !important; }
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
        # Convertir columnas numéricas
        num_cols = ["Movil", "KM_Fin", "KM_Ini", "L_Ticket", "L_Tablero", "L_Ralenti", "Desvio_Neto", "Consumo_L100", "Costo_Total_ARS"]
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # Limpieza de fechas al LEER (dayfirst obligatorio)
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
    
    # Función para limpiar memoria de los campos
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
            chofer = st.selectbox("👤 Chofer", sorted(df_h["Chofer"].unique().tolist()) if not df_h.empty else ["NUEVO"])
            precio_comb = st.number_input("💰 Precio Litro Gasoil", value=float(st.session_state["precio_gasoil"]))
            fecha_input = st.date_input("📅 Fecha de Carga", datetime.now())
        with col2:
            ruta_tipo = st.radio("🏔️ Tipo de Ruta", ["Llano", "Alta Montaña"], horizontal=True)
            traza_ex = ["➕ NUEVA"] + (sorted(df_h["Traza"].unique().tolist()) if not df_h.empty else [])
            traza_sel = st.selectbox("🗺️ Traza", traza_ex)
            nt = st.text_input("✍️ Nombre Nueva Traza", key="nt_k").upper()
            t_final = nt if (traza_sel == "➕ NUEVA") else traza_sel
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
                    st.success(f"✅ Guardado el {fecha_input.strftime('%d/%m/%Y')} - Costo: ${costo_viaje:,.2f}")
                    time.sleep(1)
                    st.rerun()

# --- TAB 2: OJO DE HALCÓN (CORREGIDO) ---
with tabs[1]:
    if not df_h.empty:
        # Filtros
        df_ana = df_h.copy()
        df_ana['Mes_Año'] = df_ana['Fecha'].dt.to_period('M').astype(str)
        
        st.markdown("### 🔍 Filtros")
        c_f1, c_f2 = st.columns(2)
        mes_sel = c_f1.selectbox("📅 Mes", ["Todos"] + sorted(df_ana['Mes_Año'].unique().tolist(), reverse=True))
        ruta_sel = c_f2.multiselect("🏔️ Ruta", df_ana['Ruta'].unique(), default=df_ana['Ruta'].unique())

        df_filtrado = df_ana[df_ana['Ruta'].isin(ruta_sel)]
        if mes_sel != "Todos": df_filtrado = df_filtrado[df_filtrado['Mes_Año'] == mes_sel]

        # 1. Ranking de Eficiencia
        st.divider()
        st.subheader("🏆 Ranking de Eficiencia (Top 5)")
        top_5 = df_filtrado.groupby("Chofer")["Consumo_L100"].mean().sort_values().head(5).reset_index()
        cols = st.columns(5)
        medallas = ["🥇", "🥈", "🥉", "👤", "👤"]
        for i, row in top_5.iterrows():
            with cols[i]:
                st.markdown(f'<div class="metric-card"><div class="medal-icon">{medallas[i]}</div><div class="driver-name">{row["Chofer"]}</div><div class="driver-score">{row["Consumo_L100"]:.1f}</div><div style="color:#aab;font-size:12px;">L/100</div></div>', unsafe_allow_html=True)

        # 2. Ranking de Desvíos (DISEÑO RESTAURADO Y COLORES)
        st.divider()
        st.subheader("⚠️ Ranking de Desvíos de Combustible")
        df_desv = df_filtrado.groupby("Chofer")["Desvio_Neto"].sum().sort_values(ascending=False).reset_index()
        
        # Ocupar todo el ancho disponible para las tarjetas de desvío
        for i, row in df_desv.iterrows():
            exc_critico = row['Desvio_Neto'] > 50
            # Clase dinámica: desvio-critico (Rojo) o desvio-ok (Verde)
            clase_color = "desvio-critico" if exc_critico else "desvio-ok"
            icono_alerta = "🚨" if exc_critico else "✅"
            
            # HTML para tarjeta ancha restaurada
            html_desvio = f"""
                <div class="desvio-item {clase_color}">
                    <div>
                        <span style='color:white; font-size:16px; font-weight:bold;'>{row["Chofer"]}</span>
                        <br><small style='color:#aab;'>{icono_alerta} {"Crítico (>50L)" if exc_critico else "Controlado"}</small>
                    </div>
                    <b style="font-size:20px; color:white;">{row["Desvio_Neto"]:.1f} L</b>
                </div>
            """
            st.markdown(html_desvio, unsafe_allow_html=True)

        # 3. Gráficos
        st.divider()
        g1, g2 = st.columns(2)
        with g1:
            df_t = df_ana.groupby('Mes_Año')['Consumo_L100'].mean().reset_index()
            st.plotly_chart(px.area(df_t, x='Mes_Año', y='Consumo_L100', title="📈 Evolución", template="plotly_dark"), use_container_width=True)
        with g2:
            df_m = df_filtrado.groupby("Marca")["Consumo_L100"].mean().reset_index()
            st.plotly_chart(px.bar(df_m, x='Marca', y='Consumo_L100', color='Marca', title="🚛 Eficiencia", template="plotly_dark"), use_container_width=True)

# --- TAB 3: HISTORIAL ---
with tabs[2]:
    if not df_h.empty:
        df_v = df_h.copy()
        df_v['Fecha'] = df_v['Fecha'].dt.strftime('%d/%m/%Y')
        st.dataframe(df_v.sort_values("Fecha", ascending=False), use_container_width=True)
