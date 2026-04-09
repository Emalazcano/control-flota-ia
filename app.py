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

# --- 2. SISTEMA DE LOGIN ---
if "auth" not in st.session_state:
    st.title("🚚 Sistema de Control de Flota")
    _, col_log, _ = st.columns([1, 2, 1])
    with col_log:
        st.subheader("🔐 Acceso de Usuario")
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.button("Ingresar", use_container_width=True):
            if u == "ema_admin" and p == "jujuy2024":
                st.session_state["auth"] = True
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
    st.stop()

# --- 3. CONEXIÓN Y DATOS ---
conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1PEH7lbtoq_oAHwom0O5YYYskFm6ALJ6LCj1FfQKzpmQ/edit?gid=0#gid=0"

if "precio_gasoil" not in st.session_state:
    st.session_state["precio_gasoil"] = 1100.0

def cargar_datos():
    try:
        df = conn.read(spreadsheet=URL, ttl=0)
        cols = ["Costo_Total_ARS", "L_Ticket", "Consumo_L100", "Desvio_Neto", "KM_Fin", "Costo_Ralenti_ARS", "L_Tablero", "L_Ralenti"]
        for c in cols:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        return df
    except: return pd.DataFrame()

df_h = cargar_datos()

# --- 4. INTERFAZ ---
st.title("🚚 Inteligencia de Flota y Costos")
tabs = st.tabs(["⛽ Registro de Carga", "🦅 Ojo de Halcón (IA)", "📜 Historial"])

# --- TAB 1: REGISTRO ---
with tabs[0]:
    st.subheader("📝 Nuevo Registro")
    
    # Precio Gasoil dinámico
    c_p, _ = st.columns([1, 2])
    st.session_state["precio_gasoil"] = c_p.number_input("💵 Precio Gasoil por Litro ($)", value=st.session_state["precio_gasoil"])
    
    with st.form("registro_form", clear_on_submit=True):
        f1, f2, f3 = st.columns(3)
        with f1:
            movil_sel = st.selectbox("🔢 Móvil", list(range(1, 101)))
            km_auto = int(df_h[df_h["Movil"] == movil_sel]["KM_Fin"].max()) if not df_h.empty else 0
            kmi = st.number_input("🛣️ KM Inicial", value=km_auto)
            chofer = st.selectbox("👤 Chofer", sorted(df_h["Chofer"].unique())) if not df_h.empty else st.text_input("Chofer")
            marca = st.radio("🚛 Marca del Vehículo", ["SCANIA", "MERCEDES BENZ"], horizontal=True)
            
        with f2:
            ruta_tipo = st.radio("🏔️ Tipo de Ruta", ["Llano", "Alta Montaña"], horizontal=True)
            traza = st.selectbox("📍 Traza", ["➕ NUEVA"] + sorted(df_h["Traza"].unique().tolist()) if not df_h.empty else ["➕ NUEVA"])
            nt = st.text_input("✍️ Nombre Nueva Traza").upper() if traza == "➕ NUEVA" else ""
            t_final = nt if traza == "➕ NUEVA" else traza
            
        with f3:
            kmf = st.number_input("🏁 KM Final")
            lt = st.number_input("⛽ Litros Ticket")
            ltab = st.number_input("📟 Litros Tablero")
            lral = st.number_input("⏳ Litros Ralentí")

        # Calculadora de cálculos en tiempo real
        recorrido = kmf - kmi
        consumo_estimado = (lt / recorrido * 100) if recorrido > 0 else 0
        costo_viaje = lt * st.session_state["precio_gasoil"]
        desvio = lt - (ltab + lral)
        
        st.divider()
        if recorrido > 0:
            st.info(f"📊 **Resumen:** {recorrido} KM | {consumo_estimado:.1f} L/100 | Costo: ${costo_viaje:,.2f}")

        if st.form_submit_button("💾 GUARDAR REGISTRO"):
            if kmf <= kmi or lt <= 0 or t_final == "":
                st.error("⚠️ Datos incompletos o erróneos.")
            else:
                nuevo_dato = {
                    "Fecha": datetime.now().strftime('%Y-%m-%d'),
                    "Movil": movil_sel, "Chofer": chofer, "Marca": marca, "Ruta": ruta_tipo,
                    "Traza": t_final, "KM_Ini": kmi, "KM_Fin": kmf, "KM_Recorr": recorrido,
                    "L_Ticket": lt, "L_Tablero": ltab, "L_Ralenti": lral,
                    "Desvio_Neto": round(desvio, 2), "Consumo_L100": round(consumo_estimado, 2),
                    "Costo_Total_ARS": round(costo_viaje, 2),
                    "Costo_Ralenti_ARS": round(lral * st.session_state["precio_gasoil"], 2)
                }
                df_actualizado = pd.concat([df_h, pd.DataFrame([nuevo_dato])], ignore_index=True)
                conn.update(spreadsheet=URL, data=df_actualizado)
                st.success("✅ Guardado")
                time.sleep(1)
                st.rerun()

# --- TAB 2: OJO DE HALCÓN ---
with tabs[1]:
    if not df_h.empty:
        m1, m2, m3 = st.columns(3)
        m1.metric("💰 Gasto Histórico", f"$ {df_h['Costo_Total_ARS'].sum():,.0f}")
        m2.metric("🛑 Pérdida Ralentí", f"$ {df_h['Costo_Ralenti_ARS'].sum():,.0f}")
        m3.metric("📉 Consumo Promedio", f"{df_h['Consumo_L100'].mean():,.1f} L/100")
        
        st.divider()
        st.markdown("### 🏆 Cuadro de Honor: Eco-Driving")

        def render_podio(categoria):
            st.markdown(f'<div class="category-header"><h3>{ "🏔️" if categoria == "Alta Montaña" else "🛣️" } {categoria}</h3></div>', unsafe_allow_html=True)
            df_cat = df_h[df_h["Ruta"] == categoria]
            if not df_cat.empty:
                top = df_cat.groupby("Chofer")["Consumo_L100"].mean().sort_values().head(3).reset_index()
                cols = st.columns(3)
                meds = [("🥇", "medal-gold"), ("🥈", "medal-silver"), ("🥉", "medal-bronze")]
                for i, row in top.iterrows():
                    with cols[i]:
                        st.markdown(f"""<div class="metric-card"><div class="{meds[i][1]}">{meds[i][0]}</div><div class="driver-name">{row['Chofer']}</div><div class="driver-score">{row['Consumo_L100']:.1f}</div><div style="font-size: 11px; color: #aab;">L/100</div></div>""", unsafe_allow_html=True)
            else: st.info(f"Sin datos en {categoria}")

        c_llano, c_mont = st.columns(2)
        with c_llano: render_podio("Llano")
        with c_mont: render_podio("Alta Montaña")

with tabs[2]:
    st.dataframe(df_h.iloc[::-1], use_container_width=True)
