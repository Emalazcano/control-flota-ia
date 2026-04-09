import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import time
import os

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Control Flota Jujuy", layout="wide")

conn = st.connection("gsheets", type=GSheetsConnection)
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1PEH7lbtoq_oAHwom0O5YYYskFm6ALJ6LCj1FfQKzpmQ/edit?gid=0#gid=0"

# Persistencia del precio del gasoil
if "precio_gasoil_fijo" not in st.session_state:
    st.session_state["precio_gasoil_fijo"] = 1100.0

def obtener_datos():
    try:
        df = conn.read(spreadsheet=SPREADSHEET_URL, ttl=0)
        cols_num = ["Costo_Total_ARS", "L_Ticket", "Costo_Ralenti_ARS", "Consumo_L100", "Desvio_Neto", "L_Tablero", "L_Ralenti"]
        for c in cols_num:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        return df
    except:
        return pd.DataFrame()

@st.cache_data
def obtener_choferes_repo():
    archivo = "choferes.xlsx"
    if os.path.exists(archivo):
        try:
            xl = pd.read_excel(archivo)
            col = "Chofer" if "Chofer" in xl.columns else xl.columns[0]
            return sorted(xl[col].dropna().unique().tolist())
        except: pass
    return ["Error: choferes.xlsx no encontrado"]

# --- 2. LOGIN ---
if "auth" not in st.session_state:
    st.title("🚚 Sistema de Control de Flota")
    _, col_log, _ = st.columns([1, 3, 1])
    with col_log:
        st.subheader("🔐 Acceso")
        c1, c2, c3 = st.columns([2, 2, 1])
        u = c1.text_input("Usuario", placeholder="Usuario")
        p = c2.text_input("Clave", type="password", placeholder="Contraseña")
        if c3.button("Ingresar", use_container_width=True):
            if u == "ema_admin" and p == "jujuy2024":
                st.session_state["auth"] = True
                st.rerun()
            else: st.error("❌")
    st.stop()

# --- 3. CARGA DE DATOS ---
df_h = obtener_datos()
lista_choferes = obtener_choferes_repo()

# Obtener lista limpia de trazas para validación
trazas_en_db = []
if not df_h.empty and "Traza" in df_h.columns:
    trazas_en_db = [str(t).strip().upper() for t in df_h["Traza"].unique() if t]

trazas_para_selector = ["➕ NUEVA TRAZA"] + sorted(trazas_en_db)

# --- 4. INTERFAZ ---
st.title("🚚 Inteligencia de Flota y Costos")
tabs = st.tabs(["⛽ Registro de Carga", "🦅 Ojo de Halcón (IA)", "📜 Historial Completo"])

with tabs[0]:
    st.subheader("📝 Nuevo Registro")
    
    c_p, _ = st.columns([1, 2])
    precio_gasoil = c_p.number_input("💵 Precio Gasoil por Litro ($)", 
                                     min_value=0.0, 
                                     value=st.session_state["precio_gasoil_fijo"], 
                                     step=0.1)
    st.session_state["precio_gasoil_fijo"] = precio_gasoil

    with st.form("registro_final", clear_on_submit=True):
        st.divider()
        f1, f2, f3 = st.columns(3)
        with f1:
            fecha = st.date_input("📅 Fecha", datetime.now(), format="DD/MM/YYYY")
            movil = st.number_input("🔢 Móvil (1-100)", min_value=1, max_value=100)
            chofer = st.selectbox("👤 Chofer", lista_choferes)
        
        with f2:
            marca = st.radio("🚛 Marca", ["SCANIA", "MERCEDES BENZ"], horizontal=True)
            ruta_tipo = st.radio("🏔️ Tipo de Ruta", ["Llano", "Alta Montaña"], horizontal=True)
            
            # Selector de traza
            traza_sel = st.selectbox("📍 Seleccionar Traza Existente", trazas_para_selector)
            nueva_traza_input = ""
            if traza_sel == "➕ NUEVA TRAZA":
                nueva_traza_input = st.text_input("✍️ Escribir Nombre de Nueva Traza").strip().upper()
            
            traza_final = nueva_traza_input if traza_sel == "➕ NUEVA TRAZA" else traza_sel

        with f3:
            kmi = st.number_input("🛣️ KM Inicial", min_value=0)
            kmf = st.number_input("🏁 KM Final", min_value=0)
            lt = st.number_input("⛽ Litros Ticket", min_value=0.0)
            ltab = st.number_input("📟 Litros Tablero", min_value=0.0)
            lral = st.number_input("⏳ Litros Ralentí", min_value=0.0)
        
        recorrido = kmf - kmi
        consumo = (lt / recorrido * 100) if recorrido > 0 else 0
        costo_v = lt * precio_gasoil
        
        st.info(f"📊 **Resumen:** {recorrido} km | {consumo:.2f} L/100 | **Costo Estimado: $ {costo_v:,.2f}**")
        
        if st.form_submit_button("💾 GUARDAR REGISTRO"):
            # --- VALIDACIÓN CRÍTICA DE DUPLICADOS ---
            if traza_sel == "➕ NUEVA TRAZA" and traza_final in trazas_en_db:
                st.error(f"🚫 La ruta '{traza_final}' YA ESTÁ REGISTRADA. Por favor, selecciónala directamente del menú desplegable arriba.")
            elif traza_sel == "➕ NUEVA TRAZA" and not nueva_traza_input:
                st.error("⚠️ Por favor, escribe el nombre de la nueva traza.")
            elif kmf <= kmi:
                st.error("⚠️ El KM Final debe ser mayor al Inicial.")
            elif lt <= 0:
                st.error("⚠️ Los litros de ticket deben ser mayores a 0.")
            else:
                # Proceder con el guardado
                nuevo = {
                    "Fecha": fecha.strftime('%d/%m/%Y'),
                    "Chofer": chofer, "Movil": movil, "Marca": marca, "Ruta": ruta_tipo, 
                    "Traza": traza_final, "KM_Ini": kmi, "KM_Fin": kmf, "KM_Recorr": recorrido, 
                    "L_Ticket": lt, "L_Tablero": ltab, "L_Ralenti": lral,
                    "Desvio_Neto": round(lt - (ltab + lral), 2), 
                    "Consumo_L100": round(consumo, 2),
                    "Costo_Total_ARS": round(costo_v, 2), 
                    "Costo_Ralenti_ARS": round(lral * precio_gasoil, 2)
                }
                df_f = pd.concat([df_h, pd.DataFrame([nuevo])], ignore_index=True)
                conn.update(spreadsheet=SPREADSHEET_URL, data=df_f)
                st.success(f"✅ Guardado correctamente. Costo: $ {costo_v:,.2f}")
                time.sleep(1)
                st.rerun()

# --- PESTAÑAS DE INTELIGENCIA E HISTORIAL (CONSERVANDO TODOS LOS ICONOS) ---
with tabs[1]:
    st.subheader("🦅 Inteligencia de Flota")
    if not df_h.empty:
        m1, m2, m3 = st.columns(3)
        m1.metric("💰 Gasto Histórico", f"$ {df_h['Costo_Total_ARS'].sum():,.0f}")
        m2.metric("🛑 Pérdida Ralentí", f"$ {df_h['Costo_Ralenti_ARS'].sum():,.0f}")
        m3.metric("📉 Consumo Promedio", f"{df_h['Consumo_L100'].mean():,.1f} L/100")
    else: st.info("Sin datos.")

with tabs[2]:
    st.subheader("📜 Historial Completo")
    if not df_h.empty:
        st.dataframe(df_h.iloc[::-1], use_container_width=True)
