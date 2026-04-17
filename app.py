import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime
import time
import requests

# ══════════════════════════════════════════
# 1. CONFIGURACIÓN DE PÁGINA
# ══════════════════════════════════════════
st.set_page_config(page_title="Inteligencia de Flota Jujuy", layout="wide")

# ══════════════════════════════════════════
# 2. CONFIGURACIÓN IA (ANTHROPIC)
# ══════════════════════════════════════════
ANTHROPIC_API_KEY = st.secrets.get("ANTHROPIC_API_KEY", None)
ia_disponible = ANTHROPIC_API_KEY is not None

def consultar_claude(contexto: str, pregunta: str) -> str:
    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-3-haiku-20240307",
                "max_tokens": 1024,
                "system": contexto,
                "messages": [{"role": "user", "content": pregunta}],
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["content"][0]["text"]
    except Exception as e:
        return f"❌ Error: {e}"

# ══════════════════════════════════════════
# 3. ESTILOS CSS
# ══════════════════════════════════════════
st.markdown("""
    <style>
    .kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 1.5rem; }
    .kpi-card { background: #1e2130; border: 1px solid #3d425a; border-radius: 12px; padding: 16px 18px; }
    .kpi-label { font-size: 11px; color: #8892aa; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 6px; }
    .kpi-value { font-size: 28px; font-weight: 600; color: white; }
    .kpi-sub   { font-size: 11px; color: #5a6278; margin-top: 3px; }
    .kpi-good .kpi-value { color: #00CC96; }
    .kpi-warn .kpi-value { color: #FFA500; }
    .kpi-bad  .kpi-value { color: #FF4B4B; }
    .ranking-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin-bottom: 1.5rem; }
    .rank-card { background: #1e2130; border: 1px solid #3d425a; border-radius: 12px; padding: 14px 10px; text-align: center; }
    .rank-card.gold { border: 2px solid #EF9F27; }
    .rank-pos  { font-size: 24px; margin-bottom: 6px; }
    .rank-name { font-size: 12px; font-weight: 600; color: white; margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .rank-score { font-size: 20px; font-weight: 600; color: #00CC96; }
    .rank-unit  { font-size: 10px; color: #5a6278; }
    .desvio-item { padding: 12px 16px; border-radius: 8px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; }
    .desvio-critico { background: #2a1414; border: 1px solid #5a2020; border-left: 4px solid #FF4B4B; }
    .desvio-ok      { background: #0d2318; border: 1px solid #0d3d25; border-left: 4px solid #00CC96; }
    .chat-burbuja-user { background: #1e2130; border: 1px solid #3d425a; border-radius: 12px 12px 2px 12px; padding: 12px 16px; margin-bottom: 8px; color: white; }
    .chat-burbuja-ia   { background: #0d2318; border: 1px solid #0d3d25; border-radius: 12px 12px 12px 2px; padding: 12px 16px; margin-bottom: 16px; color: #e0ffe8; }
    </style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════
# 4. LOGIN
# ══════════════════════════════════════════
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

# ══════════════════════════════════════════
# 5. CONEXIÓN Y DATOS
# ══════════════════════════════════════════
conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1PEH7lbtoq_oAHwom0O5YYYskFm6ALJ6LCj1FfQKzpmQ/edit?gid=0#gid=0"

if "precio_gasoil" not in st.session_state:
    st.session_state["precio_gasoil"] = 2065.0
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

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
    except:
        return pd.DataFrame()

df_h = cargar_historial()
lista_personal = sorted(df_h["Chofer"].unique().tolist()) if not df_h.empty else ["NUEVO"]

# ══════════════════════════════════════════
# 6. INTERFAZ PRINCIPAL
# ══════════════════════════════════════════
st.title("🚛 Inteligencia de Flota y Costos")
tabs = st.tabs(["⛽ Registro de Carga", "🦅 Ojo de Halcón", "📜 Historial", "🤖 Asistente IA"])

# TAB 1: REGISTRO
with tabs[0]:
    st.subheader("📝 Nuevo Registro")
    km_sugerido = 0.0

    with st.form("registro_form", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns(4)

        with c1:
            movil_sel = st.selectbox("🔢 Móvil", list(range(1, 101)), index=36)
            if not df_h.empty:
                ult_m = df_h[df_h["Movil"] == movil_sel]
                if not ult_m.empty:
                    km_sugerido = float(ult_m.sort_values("Fecha").iloc[-1]["KM_Fin"])
            
            kmi = st.number_input("🛣️ KM Inicial", value=int(km_sugerido), step=1)
            kmf = st.number_input("🏁 KM Final", value=0, step=1)

        with c2:
            marca = st.radio("🏷️ Marca", ["SCANIA", "MERCEDES BENZ"], horizontal=True)
            ruta_tipo = st.radio("🏔️ Tipo de Ruta", ["Llano", "Alta Montaña"], horizontal=True)
            traza_ex = ["➕ NUEVA"] + (sorted(df_h["Traza"].unique().tolist()) if not df_h.empty else [])
            traza_sel = st.selectbox("🗺️ Traza", traza_ex)
            nt = st.text_input("✍️ Nueva Traza").upper()
            t_final = nt if (traza_sel == "➕ NUEVA") else traza_sel

        with c3:
            chofer = st.selectbox("👤 Chofer", options=lista_personal)
            fecha_input = st.date_input("📅 Fecha")
            precio_comb = st.number_input("💰 Precio Litro ($)", value=float(st.session_state["precio_gasoil"]))
            st.divider()
            lt = st.number_input("⛽ Litros Ticket", value=0.0)
            ltab = st.number_input("📟 Litros Tablero", value=0.0)
            lral = st.number_input("⏳ Litros Ralentí", value=0.0)

        with c4:
            dist_prev = int(kmf - kmi) if kmf > kmi else 0
            cons_prev = (lt / dist_prev * 100) if dist_prev > 0 and lt > 0 else 0
            st.markdown("### Vista previa")
            st.metric("📏 KM Recorridos", f"{dist_prev:,}")
            st.metric("🔢 Consumo", f"{cons_prev:.1f} L/100")
            st.metric("💵 Costo", f"${(lt * precio_comb):,.0f}")

        guardado = st.form_submit_button("💾 GUARDAR REGISTRO", use_container_width=True, type="primary")

    if guardado:
        if kmf <= kmi or lt <= 0:
            st.error("Datos inválidos.")
        else:
            dist = int(kmf - kmi)
            nuevo_reg = {
                "Fecha": fecha_input.strftime('%d/%m/%Y'),
                "Chofer": chofer, "Movil": movil_sel, "Marca": marca, "Ruta": ruta_tipo,
                "Traza": t_final, "KM_Ini": kmi, "KM_Fin": kmf, "KM_Recorr": dist,
                "L_Ticket": lt, "L_Tablero": ltab, "L_Ralenti": lral,
                "Consumo_L100": round((lt / dist * 100), 2),
                "Costo_Total_ARS": round(lt * precio_comb, 2),
                "Desvio_Neto": round(lt - (ltab + lral), 2),
            }
            df_final = pd.concat([df_h, pd.DataFrame([nuevo_reg])], ignore_index=True)
            conn.update(spreadsheet=URL, data=df_final)
            st.success("✅ ¡Guardado!")
            time.sleep(1)
            st.rerun()

# ──────────────────────────────────────────
# TAB 2: OJO DE HALCÓN
# ──────────────────────────────────────────
with tabs[1]:
    if df_h.empty:
        st.info("Sin datos todavía. Cargá el primer registro.")
    else:
        df_ana = df_h.copy()
        df_ana['Mes_Año'] = df_ana['Fecha'].dt.to_period('M').astype(str)

        st.markdown("### 🔍 Filtros")
        c_f1, c_f2 = st.columns(2)
        mes_sel  = c_f1.selectbox("📅 Mes", ["Todos"] + sorted(df_ana['Mes_Año'].unique().tolist(), reverse=True))
        ruta_sel = c_f2.multiselect("🏔️ Ruta", df_ana['Ruta'].unique(), default=list(df_ana['Ruta'].unique()))

        df_f = df_ana[df_ana['Ruta'].isin(ruta_sel)]
        if mes_sel != "Todos":
            df_f = df_f[df_f['Mes_Año'] == mes_sel]

        st.divider()

        # KPIs
        st.markdown('<div class="section-title">Resumen del período</div>', unsafe_allow_html=True)
        consumo_prom = df_f["Consumo_L100"].mean()           if not df_f.empty else 0
        desvio_total = df_f["Desvio_Neto"].sum()             if not df_f.empty else 0
        costo_total  = df_f["Costo_Total_ARS"].sum()         if not df_f.empty else 0
        alertas      = int((df_f["Desvio_Neto"] > 50).sum()) if not df_f.empty else 0

        kpi_consumo = "kpi-good" if consumo_prom < 35 else ("kpi-warn" if consumo_prom < 42 else "kpi-bad")
        kpi_desvio  = "kpi-good" if desvio_total < 100 else ("kpi-warn" if desvio_total < 300 else "kpi-bad")
        kpi_alertas = "kpi-good" if alertas == 0 else ("kpi-warn" if alertas <= 2 else "kpi-bad")

        st.markdown(f"""
        <div class="kpi-grid">
            <div class="kpi-card {kpi_consumo}">
                <div class="kpi-label">Consumo promedio</div>
                <div class="kpi-value">{consumo_prom:.1f}</div>
                <div class="kpi-sub">L / 100 km · flota completa</div>
            </div>
            <div class="kpi-card {kpi_desvio}">
                <div class="kpi-label">Desvío acumulado</div>
                <div class="kpi-value">{desvio_total:.0f} L</div>
                <div class="kpi-sub">ticket vs tablero + ralentí</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Costo total</div>
                <div class="kpi-value">${costo_total:,.0f}</div>
                <div class="kpi-sub">ARS · período seleccionado</div>
            </div>
            <div class="kpi-card {kpi_alertas}">
                <div class="kpi-label">Alertas críticas</div>
                <div class="kpi-value">{alertas}</div>
                <div class="kpi-sub">desvíos &gt; 50 L</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # Ranking
        st.markdown('<div class="section-title">🏆 Ranking de eficiencia — Top 5</div>', unsafe_allow_html=True)
        top_5    = df_f.groupby("Chofer")["Consumo_L100"].mean().sort_values().head(5).reset_index()
        medallas = ["🥇", "🥈", "🥉", "4°", "5°"]
        ranking_html = '<div class="ranking-grid">'
        for i, row in top_5.iterrows():
            clase_gold    = "gold" if i == 0 else ""
            ranking_html += f"""
            <div class="rank-card {clase_gold}">
                <div class="rank-pos">{medallas[i]}</div>
                <div class="rank-name">{row["Chofer"]}</div>
                <div class="rank-score">{row["Consumo_L100"]:.1f}</div>
                <div class="rank-unit">L / 100 km</div>
            </div>"""
        ranking_html += '</div>'
        st.markdown(ranking_html, unsafe_allow_html=True)

        st.divider()

        # Desvíos + Gráfico
        col_d, col_g = st.columns(2)
        with col_d:
            st.markdown('<div class="section-title">⚠️ Desvíos por chofer</div>', unsafe_allow_html=True)
            df_desv = df_f.groupby("Chofer")["Desvio_Neto"].sum().sort_values(ascending=False).reset_index()
            for _, row in df_desv.iterrows():
                critico    = row['Desvio_Neto'] > 50
                clase_div  = "desvio-critico" if critico else "desvio-ok"
                badge_html = (
                    '<span class="badge badge-crit">Crítico &gt;50L</span>'
                    if critico else
                    '<span class="badge badge-ok">Controlado</span>'
                )
                st.markdown(f"""
                <div class="desvio-item {clase_div}">
                    <div>
                        <span style='color:white;font-size:15px;font-weight:600;'>{row["Chofer"]}</span><br>
                        {badge_html}
                    </div>
                    <b style="font-size:20px;color:white;">{row["Desvio_Neto"]:.1f} L</b>
                </div>""", unsafe_allow_html=True)

        with col_g:
            st.markdown('<div class="section-title">📊 Scania vs Mercedes · L/100km por ruta</div>', unsafe_allow_html=True)
            df_comp = df_f.groupby(["Ruta", "Marca"])["Consumo_L100"].mean().reset_index()
            if not df_comp.empty:
                fig = px.bar(
                    df_comp, x="Ruta", y="Consumo_L100", color="Marca",
                    barmode="group", text_auto='.1f',
                    color_discrete_map={"SCANIA": "#378ADD", "MERCEDES BENZ": "#EF9F27"},
                    template="plotly_dark",
                    labels={"Consumo_L100": "L/100km", "Ruta": ""},
                )
                fig.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    legend_title_text="",
                    margin=dict(t=10, b=10, l=10, r=10),
                )
                st.plotly_chart(fig, use_container_width=True)

# ──────────────────────────────────────────
# TAB 3: HISTORIAL
# ──────────────────────────────────────────
with tabs[2]:
    if df_h.empty:
        st.info("Sin datos todavía.")
    else:
        df_v = df_h.copy().sort_values("Fecha", ascending=False)
        df_v['Fecha'] = df_v['Fecha'].dt.strftime('%d/%m/%Y')
        st.dataframe(
            df_v,
            use_container_width=True,
            column_config={
                "KM_Ini":          st.column_config.NumberColumn("KM Inicial",   format="%d"),
                "KM_Fin":          st.column_config.NumberColumn("KM Final",     format="%d"),
                "KM_Recorr":       st.column_config.NumberColumn("KM Recorrido", format="%d"),
                "Costo_Total_ARS": st.column_config.NumberColumn("Costo ARS",    format="$%,.0f"),
                "Consumo_L100":    st.column_config.NumberColumn("L/100km",      format="%.1f"),
                "Desvio_Neto":     st.column_config.NumberColumn("Desvío L",     format="%.1f"),
            }
        )

# ──────────────────────────────────────────
# TAB 4: ASISTENTE IA
# ──────────────────────────────────────────
with tabs[3]:
    st.subheader("🤖 Asistente de Flota con IA")

    if not ia_disponible:
        st.error("La IA no está configurada.")
        st.markdown("""
        **Para activarla:**
        1. Entrá a [console.anthropic.com](https://console.anthropic.com) → creá cuenta gratuita → generá una API Key (`sk-ant-...`)
        2. En Streamlit Cloud → tu app → **Settings → Secrets** → agregá:
        ```
        ANTHROPIC_API_KEY = "sk-ant-tu_clave_aqui"
        ```
        3. Reiniciá la app
        """)
    else:
        st.markdown('<div class="section-title">Consultas rápidas</div>', unsafe_allow_html=True)
        sugerencias = [
            "¿Qué chofer tiene el mayor desvío?",
            "¿Cuál consume menos, Scania o Mercedes?",
            "¿Hay anomalías en los datos?",
            "Dame un resumen ejecutivo",
        ]
        cols_sug = st.columns(4)
        for i, sug in enumerate(sugerencias):
            if cols_sug[i].button(sug, use_container_width=True, key=f"sug_{i}"):
                st.session_state["pregunta_rapida"] = sug
                st.rerun()

        st.divider()

        for msg in st.session_state["chat_history"]:
            if msg["rol"] == "user":
                st.markdown(f'<div class="chat-label-user">Vos</div><div class="chat-burbuja-user">{msg["texto"]}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="chat-label-ia">🤖 Asistente IA</div><div class="chat-burbuja-ia">{msg["texto"]}</div>', unsafe_allow_html=True)

        pregunta_default = st.session_state.pop("pregunta_rapida", "") if "pregunta_rapida" in st.session_state else ""
        pregunta = st.text_input(
            "¿Qué querés saber sobre la flota?",
            value=pregunta_default,
            placeholder="Ej: ¿Quién consume más en rutas de montaña?",
        )

        col_enviar, col_limpiar = st.columns([4, 1])
        enviar  = col_enviar.button("Consultar ↗", use_container_width=True, type="primary")
        limpiar = col_limpiar.button("Limpiar chat", use_container_width=True)

        if limpiar:
            st.session_state["chat_history"] = []
            st.rerun()

        if enviar and pregunta.strip():
            st.session_state["chat_history"].append({"rol": "user", "texto": pregunta})
            with st.spinner("Analizando datos de la flota..."):
                respuesta = consultar_claude(generar_contexto_ia(df_h), pregunta)
                st.session_state["chat_history"].append({"rol": "ia", "texto": respuesta})
            st.rerun()


                    
