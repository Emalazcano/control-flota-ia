import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime
import time

# Debe ejecutarse antes de cualquier otro comando de Streamlit.
st.set_page_config(page_title="Inteligencia de Flota Jujuy", layout="wide")

# --- CSS PARA OPTIMIZACIÓN MÓVIL ---
st.markdown("""
    <style>
    /* Ajustes generales para pantallas pequeñas */
    @media only screen and (max-width: 600px) {
        .stMetric {
            background-color: #f0f2f6;
            padding: 10px;
            border-radius: 10px;
            margin-bottom: 10px;
        }
        [data-testid="stMetricValue"] {
            font-size: 20px !important;
        }
        /* Botones más grandes para dedos */
        div.stButton > button {
            width: 100%;
            height: 50px;
            font-size: 16px;
        }
        /* Ajustar espaciado de formularios */
        .stForm {
            padding: 10px !important;
        }
    }
    /* Mejora visual de tarjetas en todas las pantallas */
    .metric-card {
        background: #1e1e1e;
        padding: 15px;
        border-radius: 10px;
        border-left: 4px solid #4a90e2;
        margin-bottom: 10px;
        text-align: center;
    }
    .driver-name { font-weight: bold; font-size: 14px; }
    .driver-score { font-size: 20px; color: #4a90e2; }
    </style>
""", unsafe_allow_html=True)

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
        # Compatibilidad con registros anteriores: L_Ticket pasa a llamarse L_Taller.
        if "L_Taller" not in df.columns and "L_Ticket" in df.columns:
            df = df.rename(columns={"L_Ticket": "L_Taller"})
        elif "L_Taller" in df.columns and "L_Ticket" in df.columns:
            df["L_Taller"] = pd.to_numeric(df["L_Taller"], errors="coerce").fillna(
                pd.to_numeric(df["L_Ticket"], errors="coerce")
            )
            df = df.drop(columns=["L_Ticket"])

        # Los viajes anteriores no tenían una carga en ruta registrada.
        if "L_Taller" not in df.columns:
            df["L_Taller"] = 0
        if "L_Ruta" not in df.columns:
            df["L_Ruta"] = 0
        if "L_Tablero" not in df.columns:
            df["L_Tablero"] = 0
        if "L_Ralenti" not in df.columns:
            df["L_Ralenti"] = 0
        if "Desvio_Neto" not in df.columns:
            df["Desvio_Neto"] = 0

        num_cols = ["Movil", "KM_Fin", "KM_Ini", "L_Taller", "L_Ruta", "L_Tablero", "L_Ralenti", "Promedio_Tablero_L100", "Lectura_Tablero_L_Inicial", "Lectura_Tablero_L_Final", "Lectura_Ralenti_L_Inicial", "Lectura_Ralenti_L_Final", "KM_Tablero_Reset_Inicial", "Promedio_Tablero_L100_Inicial", "KM_Tablero_Reset_Final", "Promedio_Tablero_L100_Final", "Desvio_Neto", "Consumo_L100", "Costo_Total_ARS"]
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # Las cantidades de litros se muestran y guardan como litros enteros.
        for col in ["L_Taller", "L_Ruta", "L_Tablero", "L_Ralenti"]:
            df[col] = df[col].round().astype("int64")
        df["Desvio_Neto"] = df["L_Taller"] + df["L_Ruta"] - df["L_Tablero"]

        if 'Fecha' in df.columns:                                              # ← adentro del try
            df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=True, errors='coerce')
            df['Fecha'] = df['Fecha'].dt.normalize()
            df['Fecha'] = df['Fecha'].fillna(pd.Timestamp.today().normalize())

        return df

    except Exception as e:                                                     # ← después del return
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
tabs = st.tabs(["📝 Registro", "📜 Historial", "👁️ Ojo de Halcón", "📈 Analítica"])

# --- TAB 0: REGISTRO ---
with tabs[0]:
    st.subheader("📝 Nuevo Registro")
    
    # 1. Selector de móvil fuera del formulario para que detecte el cambio al instante
    col_m1, col_m2, _ = st.columns([1, 1, 1])
    movil_sel = col_m1.selectbox("🔢 Selecciona Móvil", list(range(1, 101)), index=34, key="movil_selector")
    
    # 2. Lógica de recuperación de datos (fuera del formulario para que calcule al cambiar el móvil)
    km_sugerido = 0.0
    idx_marca = 0
    idx_chofer = 0
    marcas_disponibles = ["SCANIA", "MERCEDES BENZ"]
    
    if not df_h.empty:
        # Filtramos por el móvil seleccionado (forzando a entero)
        hist_movil = df_h[df_h["Movil"] == int(movil_sel)]
        if not hist_movil.empty:
            ult_r = hist_movil.sort_values("Fecha").iloc[-1]
            km_sugerido = float(ult_r["KM_Fin"])
            
            # Buscamos índices para autocompletar
            if ult_r["Marca"] in marcas_disponibles:
                idx_marca = marcas_disponibles.index(ult_r["Marca"])
            if ult_r["Chofer"] in lista_personal:
                idx_chofer = lista_personal.index(ult_r["Chofer"])

    # Fuera del formulario para que los campos de tablero cambien al seleccionar la marca.
    marca = col_m2.radio("🏷️ Marca", marcas_disponibles, index=idx_marca, horizontal=True, key=f"m_{movil_sel}")

    # 3. Formulario con KEYS dinámicos (esto fuerza el refresco de los widgets)
    with st.form("registro_form_v2", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            chofer = st.selectbox("👤 Chofer", options=lista_personal, index=idx_chofer, key=f"c_{movil_sel}")
            precio_comb = st.number_input("💰 Precio Litro Gasoil", value=float(st.session_state["precio_gasoil"]))
            fecha_input = st.date_input("📅 Fecha de Carga", datetime.now())
        
        with c2:
            ruta_tipo = st.radio("🏔️ Tipo de Ruta", ["Llano", "Alta Montaña"], horizontal=True)
            traza_ex = ["➕ NUEVA"] + (sorted(df_h["Traza"].dropna().astype(str).unique().tolist()) if not df_h.empty and "Traza" in df_h.columns else [])
            traza_sel = st.selectbox("🗺️ Traza", traza_ex)
            nt = st.text_input("✍️ Nombre Nueva Traza").upper()
            t_final = nt if (traza_sel == "➕ NUEVA") else traza_sel
        
        with c3:
            kmi = st.number_input("🛣️ KM Inicial", value=int(km_sugerido), step=1, format="%d")
            kmf = st.number_input("🏁 KM Final", value=0, step=1, format="%d")
            l_taller = st.number_input("⛽ Litros cargados en taller / cisterna", min_value=0.0, value=0.0, step=1.0, format="%.0f", help="Combustible cargado en la cisterna de la empresa.")
            l_ruta = st.number_input("🛣️ Litros cargados en ruta", min_value=0.0, value=0.0, step=1.0, format="%.0f", help="Combustible cargado fuera de la empresa durante el viaje.")
            if marca == "MERCEDES BENZ":
                promedio_tablero = st.number_input("📈 Promedio del tablero (L/100 km)", min_value=0.0, value=0.0, key=f"prom_tab_{movil_sel}")
                distancia_tablero = max(kmf - kmi, 0)
                ltab = int(round(promedio_tablero * distancia_tablero / 100))
                st.caption(f"Litros consumidos estimados en el período: {ltab} L")
                lral = st.number_input("⏳ Litros de ralentí (opcional)", min_value=0.0, value=0.0, step=1.0, format="%.0f", key=f"ral_{movil_sel}")
            else:
                promedio_tablero = None
                ltab = st.number_input("📟 Litros consumidos según tablero", min_value=0.0, value=0.0, step=1.0, format="%.0f")
                lral = st.number_input("⏳ Litros consumidos en ralentí", min_value=0.0, value=0.0, step=1.0, format="%.0f")

        # Redondear las cantidades registradas al litro más cercano.
        l_taller, l_ruta, ltab, lral = [int(round(v)) for v in (l_taller, l_ruta, ltab, lral)]

        # Métricas visuales
        dist_v = int(kmf - kmi) if kmf > kmi else 0
        litros_cargados_total = l_taller + l_ruta
        desvio_v = litros_cargados_total - ltab
        st.markdown("---")
        v1, v2, v3, v4 = st.columns(4)
        with v1: st.metric("📏 KM", f"{dist_v:,}")
        with v2: st.metric("🔢 Consumo", f"{(litros_cargados_total/dist_v*100 if dist_v>0 else 0):.1f} L/100")
        with v3: st.metric("💰 Costo", f"${(litros_cargados_total*precio_comb):,.0f}")
        with v4: st.metric("🚨 Desvío vs tablero", f"{desvio_v:,.0f} L")
        
        submit_button = st.form_submit_button("💾 GUARDAR REGISTRO", use_container_width=True)

    # Lógica de guardado
    if submit_button:
        # Validar datos antes de escribir en la hoja.
        if kmf <= kmi:
            st.error("⚠️ El KM Final debe ser mayor al Inicial."); st.stop()
        if precio_comb <= 0 or litros_cargados_total <= 0 or lral < 0:
            st.error("⚠️ El precio debe ser positivo, registra litros cargados en taller o en ruta y no ingreses litros negativos."); st.stop()
        if marca == "MERCEDES BENZ":
            if promedio_tablero <= 0:
                st.error("⚠️ Ingresa el promedio del tablero en L/100 km."); st.stop()
        if traza_sel == "➕ NUEVA" and not nt.strip():
            st.error("⚠️ Escribe el nombre de la nueva traza."); st.stop()
        
        dist_final = int(kmf - kmi)
        nuevo_reg = {
            "Fecha": fecha_input.strftime('%d/%m/%Y'), "Chofer": chofer, "Movil": movil_sel, "Marca": marca,
            "Ruta": ruta_tipo, "Traza": t_final, "KM_Ini": kmi, "KM_Fin": kmf, "KM_Recorr": dist_final,
            "L_Taller": l_taller, "L_Ruta": l_ruta, "L_Tablero": ltab, "L_Ralenti": lral,
            "Promedio_Tablero_L100": promedio_tablero,
            "Consumo_L100": round((litros_cargados_total/dist_final*100 if dist_final > 0 else 0), 2),
            "Costo_Total_ARS": round(litros_cargados_total * precio_comb, 2),
            "Desvio_Neto": int(litros_cargados_total - ltab)
        }
        
        df_final = pd.concat([df_h, pd.DataFrame([nuevo_reg])], ignore_index=True)
        df_final['Fecha'] = pd.to_datetime(df_final['Fecha'], dayfirst=True, errors='coerce')
        df_final['Fecha'] = df_final['Fecha'].dt.strftime('%d/%m/%Y')
        try:
            conn.update(spreadsheet=URL, data=df_final)
            st.success("✅ Guardado."); time.sleep(1); st.rerun()
        except Exception as e:
            st.error(f"No se pudo guardar el registro en Google Sheets: {e}")

# --- TAB 1: OJO DE HALCÓN ---
with tabs[2]:
    if not df_h.empty:
        df_ana = df_h.copy()
        df_ana['Fecha'] = pd.to_datetime(df_ana['Fecha'])
        df_ana['Mes_Año'] = df_ana['Fecha'].dt.to_period('M').astype(str)
        for col in ["L_Taller", "L_Ruta", "L_Tablero"]:
            if col not in df_ana.columns:
                df_ana[col] = 0
            df_ana[col] = pd.to_numeric(df_ana[col], errors="coerce").fillna(0)
        if "KM_Recorr" not in df_ana.columns:
            df_ana["KM_Recorr"] = pd.to_numeric(df_ana["KM_Fin"], errors="coerce").fillna(0) - pd.to_numeric(df_ana["KM_Ini"], errors="coerce").fillna(0)
        df_ana["KM_Recorr"] = pd.to_numeric(df_ana["KM_Recorr"], errors="coerce").fillna(0).clip(lower=0)
        st.markdown("### 🔍 Filtros")
        c_f1, c_f2 = st.columns(2)
        meses_disponibles = sorted(df_ana['Mes_Año'].unique().tolist(), reverse=True)
        opciones_mes = ["Todos"] + meses_disponibles
        mes_sel = c_f1.selectbox("📅 Mes", opciones_mes, index=1 if meses_disponibles else 0)
        ruta_sel = c_f2.multiselect("🏔️ Ruta", df_ana['Ruta'].unique(), default=df_ana['Ruta'].unique())
        df_filtrado = df_ana[df_ana['Ruta'].isin(ruta_sel)]
        if mes_sel != "Todos": df_filtrado = df_filtrado[df_filtrado['Mes_Año'] == mes_sel]
        df_filtrado = df_filtrado.copy()
        df_filtrado["Litros_Cargados_Total"] = df_filtrado["L_Taller"] + df_filtrado["L_Ruta"]
        df_filtrado["Desvio_Bruto"] = df_filtrado["Litros_Cargados_Total"] - df_filtrado["L_Tablero"]

        # Detectar diferencias repetidas por móvil y mes, usando todos los tipos de ruta.
        # Así el patrón del tablero se separa del desvío atribuible a un chofer.
        df_base_unidad = df_ana if mes_sel == "Todos" else df_ana[df_ana["Mes_Año"] == mes_sel]
        df_base_unidad = df_base_unidad.copy()
        df_base_unidad["Desvio_Bruto"] = df_base_unidad["L_Taller"] + df_base_unidad["L_Ruta"] - df_base_unidad["L_Tablero"]
        desvio_unidad = df_base_unidad.groupby(["Mes_Año", "Movil"], dropna=False).agg(
            Viajes=("Desvio_Bruto", "count"),
            Promedio_Bruto=("Desvio_Bruto", "mean"),
            Variacion=("Desvio_Bruto", "std"),
        ).reset_index()
        desvio_unidad["Variacion"] = desvio_unidad["Variacion"].fillna(0)
        patron_sostenido = (desvio_unidad["Viajes"] >= 2) & (desvio_unidad["Promedio_Bruto"].abs() > 50) & (desvio_unidad["Variacion"] <= 50)
        desvio_unidad["Evaluación"] = "Sin patrón sostenido detectado"
        desvio_unidad.loc[patron_sostenido, "Evaluación"] = "Diferencia repetida: revisar tablero"
        desvio_unidad["Sesgo_Tablero"] = desvio_unidad["Promedio_Bruto"].where(patron_sostenido, 0).round().astype(int)
        df_filtrado = df_filtrado.merge(desvio_unidad[["Mes_Año", "Movil", "Sesgo_Tablero"]], on=["Mes_Año", "Movil"], how="left")
        df_filtrado["Sesgo_Tablero"] = df_filtrado["Sesgo_Tablero"].fillna(0)
        df_filtrado["Desvio_Tras_Sesgo"] = df_filtrado["Desvio_Bruto"] - df_filtrado["Sesgo_Tablero"]

        # El margen de la cisterna solo aplica cuando hubo una carga en el taller.
        df_filtrado["Margen_Cisterna"] = 50 * df_filtrado["L_Taller"].gt(0).astype(int)
        fuera_margen = df_filtrado["Desvio_Tras_Sesgo"].abs() > df_filtrado["Margen_Cisterna"]
        df_filtrado["Desvio_Ajustado"] = df_filtrado["Desvio_Tras_Sesgo"] - df_filtrado["Margen_Cisterna"] * df_filtrado["Desvio_Tras_Sesgo"].gt(df_filtrado["Margen_Cisterna"]).astype(int) + df_filtrado["Margen_Cisterna"] * df_filtrado["Desvio_Tras_Sesgo"].lt(-df_filtrado["Margen_Cisterna"]).astype(int)
        df_filtrado.loc[~fuera_margen, "Desvio_Ajustado"] = 0
        df_filtrado["Desvio_Ajustado_Abs"] = df_filtrado["Desvio_Ajustado"].abs()
        st.divider()
        st.subheader("🏆 Ranking mensual de eficiencia (Top 5 por mes)")
        st.caption("Cada barra muestra cuántos litros usa el camión para recorrer 100 km. Menos litros por 100 km significa mejor eficiencia. El cálculo usa litros cargados ÷ kilómetros recorridos; la tolerancia de la cisterna puede influir en el promedio.")
        ranking_mensual = df_filtrado.groupby(["Mes_Año", "Chofer"], dropna=False).agg(
            Litros_Cargados=("Litros_Cargados_Total", "sum"),
            KM_Recorridos=("KM_Recorr", "sum"),
            Viajes=("KM_Recorr", "size"),
        ).reset_index()
        ranking_mensual = ranking_mensual[ranking_mensual["KM_Recorridos"] > 0].copy()
        ranking_mensual["Promedio_L_100km"] = ranking_mensual["Litros_Cargados"] / ranking_mensual["KM_Recorridos"] * 100
        ranking_mensual["Puesto"] = ranking_mensual.groupby("Mes_Año")["Promedio_L_100km"].rank(method="first").astype(int)
        ranking_mensual = ranking_mensual[ranking_mensual["Puesto"] <= 5].sort_values(["Mes_Año", "Puesto"], ascending=[False, True])
        if ranking_mensual.empty:
            st.info("No hay kilómetros válidos para calcular el ranking.")
        else:
            medallas = ["🥇", "🥈", "🥉"]

            def mostrar_ranking_mes(datos_mes):
                datos_mes = datos_mes.sort_values("Promedio_L_100km", ascending=True).reset_index(drop=True)
                tarjetas = st.columns(3)
                for i, fila in datos_mes.head(3).iterrows():
                    tarjetas[i].metric(
                        label=f"{medallas[i]} Puesto {i + 1}: {fila['Chofer']}",
                        value=f"{fila['Promedio_L_100km']:.0f} L/100 km",
                        delta=f"{int(fila['Viajes'])} viajes · {fila['KM_Recorridos']:,.0f} km",
                        delta_color="off",
                    )

                grafico_ranking = datos_mes.copy()
                grafico_ranking["Etiqueta"] = grafico_ranking["Promedio_L_100km"].round().astype(int).astype(str)
                fig_ranking = px.bar(
                    grafico_ranking,
                    x="Promedio_L_100km",
                    y="Chofer",
                    orientation="h",
                    color="Promedio_L_100km",
                    color_continuous_scale="RdYlGn_r",
                    text="Etiqueta",
                    hover_data={"Viajes": True, "KM_Recorridos": ":,.0f", "Litros_Cargados": ":,.0f", "Promedio_L_100km": ":.2f", "Etiqueta": False},
                    labels={"Promedio_L_100km": "L/100 km", "Chofer": "Chofer"},
                    template="plotly_dark",
                )
                fig_ranking.update_traces(texttemplate="%{text} L/100 km", textposition="outside", cliponaxis=False)
                fig_ranking.update_yaxes(autorange="reversed", title="")
                fig_ranking.update_xaxes(title="Litros por 100 km (menos = mejor)", tickformat=".0f")
                fig_ranking.update_layout(
                    height=320,
                    margin=dict(l=10, r=90, t=10, b=10),
                    coloraxis_showscale=False,
                )
                st.plotly_chart(fig_ranking, use_container_width=True)

            meses_ranking = sorted(ranking_mensual["Mes_Año"].unique().tolist(), reverse=True)
            if mes_sel == "Todos":
                for i, mes in enumerate(meses_ranking):
                    with st.expander(f"📅 {mes}", expanded=(i == 0)):
                        mostrar_ranking_mes(ranking_mensual[ranking_mensual["Mes_Año"] == mes])
            else:
                mostrar_ranking_mes(ranking_mensual[ranking_mensual["Mes_Año"] == mes_sel])

        st.divider()
        st.subheader("⚠️ Desvíos por chofer y mes")
        st.caption("El desvío por chofer se calcula viaje a viaje: primero descuenta un patrón repetido del tablero del móvil, si se detecta; después aplica hasta ±50 L por viaje cuando hubo carga en el taller. Las cargas solo en ruta no reciben ese margen. Se conservan los desvíos brutos para comparar.")
        resumen_desvios = df_filtrado.groupby(["Mes_Año", "Chofer"], dropna=False).agg(
            Viajes=("Desvio_Bruto", "size"),
            Viajes_Dentro_Margen=("Desvio_Ajustado", lambda s: int((s == 0).sum())),
            Desvio_Bruto_Neto=("Desvio_Bruto", "sum"),
            Desvio_Ajustado_Neto=("Desvio_Ajustado", "sum"),
            Desvio_Ajustado_Absoluto=("Desvio_Ajustado_Abs", "sum"),
        ).reset_index().sort_values(["Mes_Año", "Desvio_Ajustado_Absoluto"], ascending=[False, False])
        if resumen_desvios.empty:
            st.info("No hay viajes para calcular desvíos.")
        else:
            st.dataframe(
                resumen_desvios.rename(columns={
                    "Mes_Año": "Mes", "Viajes_Dentro_Margen": "Viajes dentro del margen tras ajuste de unidad",
                    "Desvio_Bruto_Neto": "Desvío bruto neto (L)",
                    "Desvio_Ajustado_Neto": "Desvío fuera del margen (neto, L)",
                    "Desvio_Ajustado_Absoluto": "Desvíos fuera del margen (total, L)",
                }),
                use_container_width=True,
                hide_index=True,
            )

        with st.expander("Ver desvío viaje por viaje"):
            detalle_desvios = df_filtrado[["Fecha", "Mes_Año", "Movil", "Chofer", "L_Taller", "L_Ruta", "L_Tablero", "Desvio_Bruto", "Sesgo_Tablero", "Desvio_Tras_Sesgo", "Margen_Cisterna", "Desvio_Ajustado"]].sort_values("Desvio_Ajustado", key=lambda s: s.abs(), ascending=False)
            st.dataframe(
                detalle_desvios.rename(columns={
                    "Fecha": "Fecha", "Mes_Año": "Mes", "Movil": "Móvil", "Chofer": "Chofer",
                    "L_Taller": "Litros taller", "L_Ruta": "Litros ruta", "L_Tablero": "Litros tablero",
                    "Desvio_Bruto": "Desvío bruto (L)", "Sesgo_Tablero": "Patrón promedio del móvil (L)",
                    "Desvio_Tras_Sesgo": "Desvío tras patrón de unidad (L)",
                    "Margen_Cisterna": "Margen cisterna aplicado (L)",
                    "Desvio_Ajustado": "Desvío neto fuera de ±50 L (L)",
                }),
                use_container_width=True,
                hide_index=True,
            )

        st.divider()
        st.subheader("🚌 Diferencia repetida por unidad")
        st.caption("Es una señal para revisar el tablero, no una conclusión definitiva: marca diferencias promedio mayores a 50 L repetidas en al menos dos viajes, con una variación entre viajes de hasta 50 L.")
        desvio_unidad_vista = desvio_unidad.copy()
        desvio_unidad_vista[["Promedio_Bruto", "Variacion"]] = desvio_unidad_vista[["Promedio_Bruto", "Variacion"]].round(0)
        st.dataframe(
            desvio_unidad_vista.rename(columns={
                "Mes_Año": "Mes", "Movil": "Móvil", "Promedio_Bruto": "Diferencia promedio vs tablero (L)",
                "Variacion": "Variación entre viajes (L)",
            }),
            use_container_width=True,
            hide_index=True,
        )

        st.divider()
        st.subheader("🗺️ Recorridos y promedio por marca")
        st.caption("Cada fila agrupa los viajes cargados por recorrido, tipo de ruta y marca. El promedio está ponderado por los kilómetros recorridos y usa los litros cargados en taller más los cargados en ruta.")
        if "Traza" not in df_filtrado.columns:
            df_filtrado["Traza"] = "Sin recorrido"
        df_recorridos = df_filtrado.groupby(["Traza", "Ruta", "Marca"], dropna=False).agg(
            Viajes=("KM_Recorr", "size"),
            Kilometros=("KM_Recorr", "sum"),
            Litros_Cargados=("Litros_Cargados_Total", "sum"),
        ).reset_index()
        df_recorridos = df_recorridos[df_recorridos["Kilometros"] > 0].copy()
        df_recorridos["Promedio_L_100km"] = df_recorridos["Litros_Cargados"] / df_recorridos["Kilometros"] * 100
        df_recorridos = df_recorridos.sort_values(["Traza", "Marca", "Ruta"])
        if df_recorridos.empty:
            st.info("No hay recorridos con kilómetros válidos para mostrar.")
        else:
            st.dataframe(
                df_recorridos.rename(columns={
                    "Traza": "Recorrido", "Ruta": "Tipo de ruta", "Marca": "Marca",
                    "Viajes": "Viajes cargados", "Kilometros": "Kilómetros",
                    "Litros_Cargados": "Litros cargados", "Promedio_L_100km": "Promedio (L/100 km)",
                })[["Recorrido", "Tipo de ruta", "Marca", "Viajes cargados", "Kilómetros", "Litros cargados", "Promedio (L/100 km)"]],
                use_container_width=True,
                hide_index=True,
            )

        st.divider()
        st.subheader("📊 Comparativa: Scania vs Mercedes por Ruta")
        df_comp = df_filtrado.groupby(["Ruta", "Marca"]).agg(
            Litros=("Litros_Cargados_Total", "sum"),
            Kilometros=("KM_Recorr", "sum"),
        ).reset_index()
        df_comp = df_comp[df_comp["Kilometros"] > 0].copy()
        df_comp["Consumo_L100"] = df_comp["Litros"] / df_comp["Kilometros"] * 100
        fig_comp = px.bar(df_comp, x="Ruta", y="Consumo_L100", color="Marca", barmode="group", text_auto='.1f', template="plotly_dark")
        st.plotly_chart(fig_comp, use_container_width=True)
    else:
        st.info("Todavía no hay registros para analizar.")

# --- TAB 2: HISTORIAL ---
with tabs[1]:
    if not df_h.empty:
        df_v = df_h.copy().sort_values("Fecha", ascending=False)
        # Aquí formateamos la fecha a DD/MM/YYYY para que no se vea la hora
        df_v['Fecha'] = df_v['Fecha'].dt.strftime('%d/%m/%Y')
        st.dataframe(df_v, use_container_width=True)
    else:
        st.info("Todavía no hay registros en el historial.")

# --- TAB 3: ANALÍTICA AVANZADA ---
with tabs[3]:
    st.subheader("📈 Analítica y Diagnóstico")
    if df_h.empty:
        st.info("Todavía no hay registros para mostrar. Agrega un registro en la pestaña Registro.")
    else:
        # Asegurar formato fecha para gráficos
        df_ana = df_h.copy()
        df_ana['Fecha'] = pd.to_datetime(df_ana['Fecha'], dayfirst=True)
        df_ana['Mes'] = df_ana['Fecha'].dt.to_period('M').astype(str)

        # 1. TENDENCIAS (Detectar desgaste mecánico)
        st.markdown("### 📉 Tendencia de Consumo vs. Promedio Flota")
        
        # Calcular promedio general de la flota por mes para tener una referencia
        df_promedio_flota = df_ana.groupby('Mes')['Consumo_L100'].mean().reset_index()
        df_promedio_flota.rename(columns={'Consumo_L100': 'Promedio_Flota'}, inplace=True)

        moviles_seleccionados = st.multiselect("Seleccionar Móviles para comparar", 
                                              options=sorted(df_ana['Movil'].unique()), 
                                              default=[df_ana['Movil'].iloc[0]])
        
        if moviles_seleccionados:
            df_tendencia = df_ana[df_ana['Movil'].isin(moviles_seleccionados)]
            df_tendencia = df_tendencia.groupby(['Mes', 'Movil'])['Consumo_L100'].mean().reset_index()
            
            # Crear gráfico base
            fig_line = px.line(df_tendencia, x="Mes", y="Consumo_L100", color="Movil", 
                               markers=True, template="plotly_dark",
                               labels={"Consumo_L100": "Consumo (L/100km)", "Mes": "Periodo"})
            
            # Añadir la línea de promedio de la flota (punteada y gris)
            fig_line.add_scatter(x=df_promedio_flota['Mes'], y=df_promedio_flota['Promedio_Flota'],
                                 mode='lines', name='Promedio Flota',
                                 line=dict(color='white', width=2, dash='dash'),
                                 hovertemplate="Promedio Flota: %{y:.1f} L/100")
            
            # Mejorar aspecto visual
            fig_line.update_layout(hovermode="x unified", legend_title="Unidad")
            
            st.plotly_chart(fig_line, use_container_width=True)
            
            st.info("💡 **Cómo leer esto:** La línea punteada blanca representa el promedio de toda tu flota. Si la línea de tu móvil está **arriba** de la blanca, está consumiendo más que el promedio. Si está **abajo**, es más eficiente.")
        else:
            st.warning("Selecciona al menos un móvil para ver la tendencia.")

        # 2. BENCHMARK (Marca/Modelo vs Ruta)
        st.markdown("### ⚖️ Benchmark: Marca vs Ruta")
        st.write("Comparativa de eficiencia según el tipo de terreno.")
        
        df_bench = df_ana.groupby(['Marca', 'Ruta'])['Consumo_L100'].mean().reset_index()
        fig_bar = px.bar(df_bench, x="Ruta", y="Consumo_L100", color="Marca", barmode="group", 
                         text_auto='.1f', template="plotly_dark", title="Consumo Promedio (L/100km)")
        st.plotly_chart(fig_bar, use_container_width=True)



