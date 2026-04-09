import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, date
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
        df.columns = df.columns.str.strip()
        num_cols = ["KM_Fin", "KM_Ini", "L_Ticket", "L_Tablero", "L_Ralenti", "Desvio_Neto", "Consumo_L100", "Costo_Total_ARS"]
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        if 'Fecha' in df.columns:
            df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
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
    
    # Precio fuera para persistencia
    cp_col, _ = st.columns([1, 3])
    st.session_state["precio_gasoil"] = cp_col.number_input("💵 Precio Gasoil por Litro ($)", value=st.session_state["precio_gasoil"])
    
    # --- SELECTORES DINÁMICOS (FUERA DEL FORM PARA REACTIVIDAD) ---
    st.markdown("##### 📅 1. Identificación del Viaje")
    c_prep1, c_prep2, c_prep3 = st.columns(3)
    
    with c_prep1:
        fecha_viaje = st.date_input("Fecha", value=date.today())
    
    with c_prep2:
        movil_sel = st.selectbox("🔢 Móvil", list(range(1, 101)), index=36)
        
        # Búsqueda instantánea del último KM
        km_sugerido = 0.0
        if not df_h.empty:
            ult_reg = df_h[df_h["Movil"].astype(str) == str(movil_sel)]
            if not ult_reg.empty:
                ult_reg = ult_reg.sort_values("Fecha")
                km_sugerido = float(ult_reg.iloc[-1]["KM_Fin"])

    # --- FORMULARIO PRINCIPAL ---
    with st.form("registro_form", clear_on_submit=True):
        f_col1, f_col2, f_col3 = st.columns(3)
        
        with f_col1:
            st.markdown("##### 🚛 Vehículo")
            marca = st.radio("🏷️ Marca", ["SCANIA", "MERCEDES BENZ"], horizontal=True)
            chofer = st.selectbox("👤 Chofer", lista_choferes)
            
        with f_col2:
            st.markdown("##### 📍 Ruta")
            ruta_tipo = st.radio("🏔️ Tipo de Ruta", ["Llano", "Alta Montaña"], horizontal=True)
            traza_existente = ["➕ NUEVA"] + (sorted(df_h["Traza"].unique().tolist()) if not df_h.empty else [])
            traza = st.selectbox("🗺️ Traza", traza_existente)
            nt = st.text_input("✍️ Nombre Nueva Traza").upper()
            t_final = nt if (traza == "➕ NUEVA" and nt != "") else traza
            
        with f_col3:
            st.markdown("##### ⛽ Consumo")
            kmi = st.number_input("🛣️ KM Inicial", value=km_sugerido, step=1.0)
            kmf = st.number_input("🏁 KM Final", step=1.0)
            lt = st.number_input("⛽ Litros Ticket", step=0.1)
            ltab = st.number_input("📟 Litros Tablero", step=0.1)
            lral = st.number_input("⏳ Litros Ralentí", step=0.1)

        # Cálculos
        distancia = kmf - kmi
        consumo = (lt / distancia * 100) if distancia > 0 else 0
        costo_t = lt * st.session_state["precio_gasoil"]
        desvio_n = lt - (ltab + lral)
        
        if distancia > 0:
            st.divider()
            r1, r2, r3 = st.columns(3)
            r1.metric("📏 Recorrido", f"{distancia:,.1f} KM")
            r2.metric("📊 Consumo", f"{consumo:.1f} L/100")
            r3.metric("💰 Costo Total", f"${costo_t:,.0f}")

        submit = st.form_submit_button("💾 GUARDAR REGISTRO", use_container_width=True)

        if submit:
            if kmf <= kmi or lt <= 0 or t_final == "":
                st.error("⚠️ Datos inválidos. Revise KMs y Traza.")
            else:
                nuevo_reg = {
                    "Fecha": fecha_viaje.strftime('%Y-%m-%d'), 
                    "Movil": movil_sel,
                    "Chofer": chofer, "Marca": marca, "Ruta": ruta_tipo, "Traza": t_final,
                    "KM_Ini": kmi, "KM_Fin": kmf, "KM_Recorr": distancia, "L_Ticket": lt,
                    "L_Tablero": ltab, "L_Ralenti": lral, "Consumo_L100": round(consumo, 2),
                    "Costo_Total_ARS": round(costo_t, 2), "Desvio_Neto": round(desvio_n, 2)
                }
                df_up = pd.concat([df_h, pd.DataFrame([nuevo_reg])], ignore_index=True)
                conn.update(spreadsheet=URL, data=df_up)
                st.success("✅ Registro guardado!")
                time.sleep(1)
                st.rerun()

# --- TAB 2: OJO DE HALCÓN ---
with tabs[1]:
    if not df_h.empty:
        df_h = df_h.dropna(subset=['Fecha'])
        st.markdown("### 🔍 Filtros de Análisis")
        f_c1, _ = st.columns([1, 2])
        with f_c1:
            df_h['Mes_Año'] = df_h['Fecha'].dt.strftime('%m-%Y')
            meses_disp = ["Todos"] + sorted(df_h['Mes_Año'].unique().tolist(), reverse=True)
            mes_sel = st.selectbox("📅 Periodo", meses_disp)
        
        df_view = df_h[df_h['Mes_Año'] == mes_sel].copy() if mes_sel != "Todos" else df_h.copy()
        
        st.divider()
        m1, m2, m3 = st.columns(3)
        m1.markdown(f'<div class="metric-card" style="border-left:5px solid #636EFA;"><p style="color:#aab;font-size:14px;">📉 PROMEDIO</p><h2>{df_view["Consumo_L100"].mean():,.1f} L/100</h2></div>', unsafe_allow_html=True)
        m2.markdown(f'<div class="metric-card" style="border-left:5px solid #00CC96;"><p style="color:#aab;font-size:14px;">⛽ TOTAL CARGADO</p><h2>{df_view["L_Ticket"].sum():,.0f} Lts</h2></div>', unsafe_allow_html=True)
        m3.markdown(f'<div class="metric-card" style="border-left:5px solid #EF553B;"><p style="color:#aab;font-size:14px;">💰 INVERSIÓN</p><h2>$ {df_view["Costo_Total_ARS"].sum():,.0f}</h2></div>', unsafe_allow_html=True)

        st.divider()
        st.markdown("### 🏆 Ranking Eco-Driving")
        t5 = df_view.groupby("Chofer")["Consumo_L100"].mean().sort_values().head(5).reset_index()
        cols_r = st.columns(5)
        meds = ["🥇", "🥈", "🥉", "👤", "👤"]
        for idx, r in t5.iterrows():
            cols_r[idx].markdown(f'<div class="metric-card"><div style="font-size:40px;">{meds[idx]}</div><div class="driver-name">{r["Chofer"]}</div><div class="driver-score">{r["Consumo_L100"]:.1f}</div><small style="color:#aab;">L/100</small></div>', unsafe_allow_html=True)

        st.divider()
        st.markdown("### ⚠️ Control de Desvíos (>50L)")
        df_d = df_view.groupby("Chofer")["Desvio_Neto"].sum().sort_values(ascending=False).reset_index()
        a1, a2 = st.columns(2)
        for i, row in df_d.iterrows():
            is_ex = row['Desvio_Neto'] > 50
            col_target = a1 if i % 2 == 0 else a2
            col_target.markdown(f'<div style="background:{"#421212" if is_ex else "#1e2130"};padding:12px;border-radius:8px;border:1px solid {"#FF4B4B" if is_ex else "#3d425a"};margin-bottom:8px;display:flex;justify-content:space-between;align-items:center;"><div><b style="color:white;">{row["Chofer"]}</b><br><small style="color:{"#FF4B4B" if is_ex else "#00CC96"};">{"🚨 EXCESO" if is_ex else "✅ OK"}</small></div><b style="font-size:20px;color:white;">{row["Desvio_Neto"]:.1f} L</b></div>', unsafe_allow_html=True)

# --- TAB 3: HISTORIAL ---
with tabs[2]:
    st.subheader("📜 Historial de Registros")
    if not df_h.empty:
        st.dataframe(df_h.sort_values("Fecha", ascending=False), use_container_width=True)
    else: st.info("Sin registros.")
