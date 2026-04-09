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
    return ["Error al cargar choferes.xlsx"]

# --- 2. LOGIN ---
if "auth" not in st.session_state:
    st.title("🚛 Sistema de Control de Flota")
    _, col_log, _ = st.columns([1, 3, 1])
    with col_log:
        st.subheader("🔐 Acceso")
        c1, c2, c3 = st.columns([2, 2, 1])
        u = c1.text_input("Usuario", label_visibility="collapsed", placeholder="Usuario")
        p = c2.text_input("Clave", type="password", label_visibility="collapsed", placeholder="Contraseña")
        if c3.button("Entrar", use_container_width=True):
            if u == "ema_admin" and p == "jujuy2024":
                st.session_state["auth"] = True
                st.rerun()
            else: st.error("❌")
    st.stop()

# --- 3. CARGA DE LISTAS ---
df_h = obtener_datos()
lista_choferes = obtener_choferes_repo()

# Obtener trazas únicas ya registradas para evitar duplicados
trazas_existentes = ["NUEVA TRAZA"]
if not df_h.empty and "Traza" in df_h.columns:
    trazas_db = sorted(df_h["Traza"].unique().tolist())
    trazas_existentes.extend(trazas_db)

# --- 4. INTERFAZ ---
st.title("🚛 Inteligencia de Flota y Costos")
tabs = st.tabs(["⛽ Registro", "🦅 Inteligencia", "📜 Historial"])

# --- PESTAÑA REGISTRO ---
with tabs[0]:
    with st.form("registro", clear_on_submit=True):
        st.subheader("📝 Nuevo Registro de Carga")
        
        c_precio, _ = st.columns([1, 2])
        precio_gasoil = c_precio.number_input("Precio Litro Gasoil ($)", min_value=0.0, value=1100.0)
        
        st.divider()
        
        f1, f2, f3 = st.columns(3)
        with f1:
            fecha = st.date_input("Fecha", datetime.now(), format="DD/MM/YYYY")
            movil = st.number_input("Móvil (1-100)", min_value=1, max_value=100) # Volvió a ser manual 1-100
            chofer = st.selectbox("Chofer (desde Excel)", lista_choferes)
        with f2:
            marca = st.radio("Marca", ["SCANIA", "MERCEDES BENZ"], horizontal=True)
            ruta_tipo = st.radio("Tipo de Ruta", ["Llano", "Alta Montaña"], horizontal=True)
            
            # Lógica de Trazas Delimitadas
            traza_sel = st.selectbox("Seleccionar Traza Existente", trazas_existentes)
            if traza_sel == "NUEVA TRAZA":
                traza_final = st.text_input("Escribir Nueva Traza").upper()
            else:
                traza_final = traza_sel

        with f3:
            kmi = st.number_input("KM Inicial", min_value=0)
            kmf = st.number_input("KM Final", min_value=0)
            lt = st.number_input("Litros Ticket", min_value=0.0)
            ltab = st.number_input("Litros Tablero", min_value=0.0)
            lral = st.number_input("Litros Ralentí", min_value=0.0)
        
        # Cálculos
        recorrido = kmf - kmi
        consumo = (lt / recorrido * 100) if recorrido > 0 else 0
        desvio = lt - (ltab + lral)
        
        st.info(f"📊 **Pre-visualización:** {recorrido} km | {consumo:.2f} L/100 | Costo: $ {lt * precio_gasoil:,.0f}")
        
        if st.form_submit_button("💾 GUARDAR REGISTRO"):
            if kmf > kmi and lt > 0 and traza_final != "":
                nuevo = {
                    "Fecha": fecha.strftime('%d/%m/%Y'),
                    "Chofer": chofer, "Movil": movil, "Marca": marca, "Ruta": ruta_tipo, 
                    "Traza": traza_final, "KM_Ini": kmi, "KM_Fin": kmf, "KM_Recorr": recorrido, 
                    "L_Ticket": lt, "L_Tablero": ltab, "L_Ralenti": lral,
                    "Desvio_Neto": round(desvio, 2), "Consumo_L100": round(consumo, 2),
                    "Costo_Total_ARS": round(lt * precio_gasoil, 2), 
                    "Costo_Ralenti_ARS": round(lral * precio_gasoil, 2)
                }
                df_f = pd.concat([df_h, pd.DataFrame([nuevo])], ignore_index=True)
                conn.update(spreadsheet=SPREADSHEET_URL, data=df_f)
                st.success("✅ Registro guardado correctamente.")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Revisá que los KM sean correctos y que la Traza no esté vacía.")

# --- PESTAÑA IA ---
with tabs[1]:
    if not df_h.empty:
        m1, m2, m3 = st.columns(3)
        m1.metric("Gasto Total", f"$ {df_h['Costo_Total_ARS'].sum():,.0f}")
        m2.metric("Gasto Ralentí", f"$ {df_h['Costo_Ralenti_ARS'].sum():,.0f}")
        m3.metric("Promedio Flota", f"{df_h['Consumo_L100'].mean():,.1f} L/100")
        
        st.divider()
        g1, g2 = st.columns(2)
        with g1:
            st.subheader("🏆 Mejores Choferes")
            rank = df_h.groupby("Chofer")["Consumo_L100"].mean().sort_values().head(5).reset_index()
            for i, r in rank.iterrows():
                st.write(f"{['🥇','🥈','🥉','👤','👤'][i]} **{r['Chofer']}**: {r['Consumo_L100']:.2f}")
        with g2:
            st.subheader("🚨 Alertas de Desvío")
            alertas = df_h.groupby("Chofer")["Desvio_Neto"].sum().reset_index()
            for _, r in alertas.iterrows():
                if abs(r['Desvio_Neto']) > 50:
                    st.error(f"⚠️ **{r['Chofer']}**: {r['Desvio_Neto']:.1f} L")
    else: st.info("Sin datos para analizar.")

# --- PESTAÑA HISTORIAL ---
with tabs[2]:
    st.subheader("📜 Historial Completo")
    if not df_h.empty:
        st.dataframe(df_h.iloc[::-1], use_container_width=True)
        st.download_button("📥 Exportar CSV", df_h.to_csv(index=False), "historial.csv")
