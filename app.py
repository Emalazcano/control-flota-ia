import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime
import time
import os
import google.generativeai as genai

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Inteligencia de Flota Jujuy", layout="wide")

# --- CONFIGURACIÓN DE IA GEMINI ---
if "GOOGLE_API_KEY" in st.secrets:
    api_key_final = st.secrets["GOOGLE_API_KEY"].strip().strip('"')
    genai.configure(api_key=api_key_final)
    model = genai.GenerativeModel('gemini-2.0-flash')
else:
    st.warning("⚠️ Clave API no detectada en Secrets.")
    model = None

st.markdown("""
    <style>
    .metric-card { background-color: #1e2130; padding: 15px; border-radius: 12px; border: 1px solid #3d425a; text-align: center; }
    .driver-name { font-weight: bold; font-size: 16px; margin: 5px 0; color: white; }
    .driver-score { font-size: 24px; color: #4CAF50; font-weight: bold; }
    .medal-icon { font-size: 32px; margin-bottom: 5px; }
    .desvio-item { padding: 12px; border-radius: 8px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #3d425a; transition: transform 0.2s; }
    .desvio-item:hover { transform: scale(1.02); }
    .desvio-critico { background: #421212 !important; border: 1px solid #FF4B4B !important; }
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
def cargar_lista_choferes():
    try:
        df_c = pd.read_excel("choferes.xlsx")
        return sorted(df_c.iloc[:, 0].dropna().unique().tolist())
    except:
        return []

def cargar_historial():
    try:
        df = conn.read(spreadsheet=URL, ttl=0)
        num_cols = ["Movil", "KM_Fin", "KM_Ini", "L_Ticket", "L_Tablero", "L_Ralenti", "Desvio_Neto", "Consumo_L100", "Costo_Total_ARS"]
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        if 'Fecha' in df.columns:
            df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=True, errors='coerce').fillna(pd.Timestamp.now())
        return df
    except Exception as e:
        st.error(f"Error al cargar datos: {e}")
        return pd.DataFrame()

df_h = cargar_historial()
lista_personal = cargar_lista_choferes()

if not lista_personal and not df_h.empty:
    lista_personal = sorted(df_h["Chofer"].unique().tolist())
elif not lista_personal:
    lista_personal = ["NUEVO"]

# --- 4. INTERFAZ ---
st.title("🚚 Inteligencia de Flota y Costos")
tabs = st.tabs(["⛽ Registro de Carga", "🦅 Ojo de Halcón", "📜 Historial", "🤖 Asistente IA"])

# --- TAB 0: REGISTRO ---
with tabs[0]:
    st.subheader("📝 Nuevo Registro")
    with st.container(border=True):
        col_m1, col_m2 = st.columns([1, 2])
        with col_m1:
            movil_sel = st.selectbox("🔢 Móvil", list(range(1, 101)), index=35, key="movil_dinamico")
        
        # --- LÓGICA DE SUGERENCIAS (KM, MARCA Y CHOFER) ---
        km_sugerido = 0.0
        idx_marca = 0
        idx_chofer = 0
        marcas_disponibles = ["SCANIA", "MERCEDES BENZ"]
        
        if not df_h.empty:
            ult_m = df_h[df_h["Movil"] == movil_sel]
            if not ult_m.empty:
                # Sugerir KM
                km_sugerido = float(ult_m.sort_values("Fecha").iloc[-1]["KM_Fin"])
                
                # Sugerir Marca
                marca_hist = ult_m.sort_values("Fecha").iloc[-1]["Marca"]
                if marca_hist in marcas_disponibles:
                    idx_marca = marcas_disponibles.index(marca_hist)
                
                # Sugerir Chofer (NUEVO)
                chofer_hist = ult_m.sort_values("Fecha").iloc[-1]["Chofer"]
                if chofer_hist in lista_personal:
                    idx_chofer = lista_personal.index(chofer_hist)

        # --- FORMULARIO ---
        with st.form("registro_form_v2", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                marca = st.radio("🏷️ Marca", marcas_disponibles, index=idx_marca, horizontal=True)
                chofer = st.selectbox("👤 Chofer", options=lista_personal, index=idx_chofer)
                precio_comb = st.number_input("💰 Precio Litro Gasoil", value=float(st.session_state["precio_gasoil"]))
                fecha_input = st.date_input("📅 Fecha de Carga", datetime.now())
            with c2:
                ruta_tipo = st.radio("🏔️ Tipo de Ruta", ["Llano", "Alta Montaña"], horizontal=True)
                traza_ex = ["➕ NUEVA"] + (sorted(df_h["Traza"].unique().tolist()) if not df_h.empty else [])
                traza_sel = st.selectbox("🗺️ Traza", traza_ex)
                nt = st.text_input("✍️ Nombre Nueva Traza").upper()
                t_final = nt if (traza_sel == "➕ NUEVA") else traza_sel
            with c3:
                kmi = st.number_input("🛣️ KM Inicial", value=int(km_sugerido), step=1, format="%d")
                kmf = st.number_input("🏁 KM Final", value=0, step=1, format="%d")
                lt = st.number_input("⛽ Litros Ticket", value=0.0)
                ltab = st.number_input("📟 Litros Tablero", value=0.0)
                lral = st.number_input("⏳ Litros Ralentí", value=0.0)

            dist_v = int(kmf - kmi) if kmf > kmi else 0
            cons_v = (lt / dist_v * 100) if dist_v > 0 and lt > 0 else 0
            costo_v = lt * precio_comb
            desv_v = lt - (ltab + lral)
            
            st.markdown("---")
            v1, v2, v3, v4 = st.columns(4)
            with v1: st.metric("📏 KM Recorridos", f"{dist_v:,}")
            with v2: st.metric("🔢 Consumo", f"{cons_v:.1f} L/100")
            with v3: st.metric("💰 Costo Estimado", f"${costo_v:,.0f}")
            with v4: st.metric("🚨 Desvío (Ltrs)", f"{desv_v:.1f}", delta=f"{desv_v:.1f}", delta_color="inverse")
            submit_button = st.form_submit_button("💾 GUARDAR REGISTRO", use_container_width=True)

    if submit_button:
        # 1. Validación de KM: Que el final sea mayor al inicial
        if kmf <= kmi:
            st.error(f"⚠️ Error: El KM Final ({kmf}) debe ser mayor al KM Inicial ({kmi}).")
            st.stop()
        
        # 2. Validación de coherencia de carga
        if lt <= 0:
            st.error("⚠️ Error: Debes ingresar los Litros de Ticket.")
            st.stop()

        # 3. Validación de Consumo Físico (Rango lógico)
        dist_calculada = kmf - kmi
        consumo_estimado = (lt / dist_calculada * 100) if dist_calculada > 0 else 0
        
        if consumo_estimado > 100 or consumo_estimado < 10:
            st.warning(f"⚠️ Consumo fuera de rango lógico ({consumo_estimado:.1f} L/100km).")
            # Esto permite forzar el guardado si el valor es correcto pero inusual
            if not st.checkbox("Confirmar: ¿Los datos son correctos?"):
                st.stop()

        # Si supera las validaciones, procedemos con el guardado
        dist_final = int(kmf - kmi)
        cons_final = round((lt / dist_final * 100), 2) if dist_final > 0 else 0
        costo_final = round(lt * precio_comb, 2)
        desv_final = round(lt - (ltab + lral), 2)
        
        nuevo_reg = {
            "Fecha": fecha_input.strftime('%d/%m/%Y'), "Chofer": chofer, "Movil": movil_sel, "Marca": marca,
            "Ruta": ruta_tipo, "Traza": t_final, "KM_Ini": kmi, "KM_Fin": kmf, "KM_Recorr": dist_final,
            "L_Ticket": lt, "L_Tablero": ltab, "L_Ralenti": lral, "Consumo_L100": cons_final,
            "Costo_Total_ARS": costo_final, "Desvio_Neto": desv_final
        }
        
        with st.spinner("Guardando..."):
            df_final = pd.concat([df_h, pd.DataFrame([nuevo_reg])], ignore_index=True)
            df_final['Fecha'] = df_final['Fecha'].apply(lambda x: x.strftime('%d/%m/%Y') if hasattr(x, 'strftime') else str(x))
            conn.update(spreadsheet=URL, data=df_final)
            st.success("✅ Guardado.")
            time.sleep(1); st.rerun()

# --- TAB 1: OJO DE HALCÓN ---
with tabs[1]:
    if not df_h.empty:
        df_ana = df_h.copy()
        df_ana['Mes_Año'] = df_ana['Fecha'].dt.to_period('M').astype(str)
        st.markdown("### 🔍 Filtros")
        c_f1, c_f2 = st.columns(2)
        mes_sel = c_f1.selectbox("📅 Mes", ["Todos"] + sorted(df_ana['Mes_Año'].unique().tolist(), reverse=True))
        ruta_sel = c_f2.multiselect("🏔️ Ruta", df_ana['Ruta'].unique(), default=df_ana['Ruta'].unique())
        df_filtrado = df_ana[df_ana['Ruta'].isin(ruta_sel)]
        if mes_sel != "Todos": df_filtrado = df_filtrado[df_filtrado['Mes_Año'] == mes_sel]
        csv = df_filtrado.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar reporte filtrado (CSV)",
            data=csv,
            file_name='reporte_flota.csv',
            mime='text/csv',    

        st.divider()
        st.subheader("🏆 Ranking de Eficiencia (Top 5)")
        top_5 = df_filtrado.groupby("Chofer")["Consumo_L100"].mean().sort_values().head(5).reset_index()
        cols = st.columns(5)
        medallas = ["🥇", "🥈", "🥉", "👤", "👤"]
        for i, row in top_5.iterrows():
            with cols[i]:
                st.markdown(f'<div class="metric-card"><div class="medal-icon">{medallas[i]}</div><div class="driver-name">{row["Chofer"]}</div><div class="driver-score">{row["Consumo_L100"]:.1f}</div><div style="color:#aab;font-size:12px;">L/100</div></div>', unsafe_allow_html=True)

        st.divider()
        st.subheader("⚠️ Ranking de Desvíos de Combustible")
        df_desv = df_filtrado.groupby("Chofer")["Desvio_Neto"].sum().reset_index()
        df_desv = df_desv[df_desv['Desvio_Neto'] > 50].sort_values("Desvio_Neto", ascending=False)

        if df_desv.empty:
            st.info("✅ No hay desvíos críticos.")
        else:
            for _, row in df_desv.iterrows():
                st.markdown(f'<div class="desvio-item desvio-critico"><div><b>{row["Chofer"]}</b><br><small>🚨 Crítico (>50L)</small></div><b>{row["Desvio_Neto"]:.1f} L</b></div>', unsafe_allow_html=True)

        st.divider()
        st.subheader("📊 Reporte de Desvíos por Unidad (Móvil)")
        df_movil = df_filtrado.groupby("Movil")["Desvio_Neto"].sum().reset_index()
        df_movil = df_movil[df_movil['Desvio_Neto'] > 50].sort_values("Desvio_Neto", ascending=False)
        
        if df_movil.empty:
            st.info("✅ No hay desvíos críticos.")
        else:
            for _, row in df_movil.iterrows():
                st.markdown(f'<div class="desvio-item desvio-critico"><div><b>Unidad Nº {int(row["Movil"])}</b><br><small>🚨 Crítico (>50L)</small></div><b>{row["Desvio_Neto"]:.1f} L</b></div>', unsafe_allow_html=True)

        st.divider()
        st.subheader("📊 Comparativa: Scania vs Mercedes por Ruta")
        df_comp = df_filtrado.groupby(["Ruta", "Marca"])["Consumo_L100"].mean().reset_index()
        fig_comp = px.bar(df_comp, x="Ruta", y="Consumo_L100", color="Marca", barmode="group", text_auto='.1f', template="plotly_dark")
        st.plotly_chart(fig_comp, use_container_width=True)

# --- TAB 2: HISTORIAL ---
with tabs[2]:
    if not df_h.empty:
        df_v = df_h.copy().sort_values("Fecha", ascending=False)
        # Aquí formateamos la fecha a DD/MM/YYYY para que no se vea la hora
        df_v['Fecha'] = df_v['Fecha'].dt.strftime('%d/%m/%Y')
        st.dataframe(df_v, use_container_width=True)

# --- TAB 3: ASISTENTE IA ---
with tabs[3]:
    st.subheader("🤖 Consultas con IA")
    
    if "messages" not in st.session_state: 
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]): 
            st.markdown(message["content"])

    with st.form("ai_form", clear_on_submit=True):
        pregunta = st.text_input("¿Qué quieres saber sobre la flota?", key="input_ia")
        btn_enviar = st.form_submit_button("Consultar IA")

    if btn_enviar and pregunta and model:
        st.session_state.messages.append({"role": "user", "content": pregunta})
        with st.chat_message("user"): 
            st.markdown(pregunta)
        
        with st.chat_message("assistant"):
            with st.spinner("Analizando..."):
                resumen = df_h.groupby('Chofer')['Consumo_L100'].mean().head(5).to_string()
                ctx = f"Eres experto en Flota Jujuy. Rendimiento promedio: {resumen}."
                
                # Intentamos la consulta hasta 2 veces si falla por saturación
                for intento in range(2):
                    try:
                        response = model.generate_content(f"{ctx}\nPregunta: {pregunta}")
                        res_text = response.text
                        st.markdown(res_text)
                        st.session_state.messages.append({"role": "assistant", "content": res_text})
                        break # Si salió bien, salimos del bucle
                    except Exception as e:
                        if intento == 0:
                            time.sleep(5) # Esperamos 5 segundos antes del segundo intento
                        else:
                            st.error("⚠️ Límite de cuota excedido. Por favor, espera un minuto e intenta nuevamente. (El plan gratuito tiene límites por minuto).")
