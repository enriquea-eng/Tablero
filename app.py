import streamlit as st
import streamlit.components.v1 as components
import plotly.express as px
import pandas as pd
import io
import html as html_lib
from datetime import datetime, date, timedelta, timezone
from data import get_shipping_data, get_entradas_por_hora, get_ordenes_pickup

st.set_page_config(page_title="Tablero de Envíos", layout="wide")

# --- Reportes imprimibles: cada uno se renderiza en su propio iframe, con su
# propio botón que llama a window.print() DENTRO de ese iframe. Un iframe solo
# puede imprimir su propio contenido, así que "Cierre de día" y "Vencidas"
# quedan naturalmente aislados uno del otro (no hace falta ningún truco de
# CSS ni depender de st.markdown, que interpretaba el HTML como bloque de
# código por la indentación). ---
def render_reporte_imprimible(cuerpo_html, altura=650):
    documento = f"""
    <html>
    <head>
    <style>
        /* color-scheme + fondo/color explícitos: sin esto, el navegador aplica su
        modo oscuro automático al iframe (heredado del tema oscuro de Streamlit)
        y el texto oscuro queda casi invisible sobre fondo oscuro. */
        html {{ color-scheme: light; }}
        body {{
            font-family: "Source Sans Pro", Arial, sans-serif;
            background-color: #ffffff; color: #222; margin: 0; padding: 0 1em 1em 1em;
        }}
        table {{ border-collapse: collapse; width: 100%; margin: 0.5em 0 1.2em 0; background-color: #ffffff; }}
        th, td {{ border: 1px solid #ccc; padding: 6px 10px; text-align: left; font-size: 0.9em; color: #222; }}
        th {{ background-color: #f0f0f0; }}
        td {{ background-color: #ffffff; }}
        button {{
            background-color: #FF4B4B; color: white; border: none;
            padding: 0.5em 1.2em; border-radius: 6px; font-size: 1em; cursor: pointer;
            margin: 0.8em 0;
        }}
        @media print {{ button {{ display: none; }} }}
    </style>
    </head>
    <body>
        <button onclick="window.print()">🖨️ Imprimir este reporte</button>
        {cuerpo_html}
    </body>
    </html>
    """
    components.html(documento, height=altura, scrolling=True)


def tabla_conteo_html(serie, nombre_columna):
    """Tabla HTML con el conteo por valor de una columna, más un total."""
    conteo = serie.value_counts()
    filas_html = "".join(
        f"<tr><td>{html_lib.escape(str(idx))}</td><td>{val}</td></tr>"
        for idx, val in conteo.items()
    )
    return f"""
    <table>
        <thead><tr><th>{nombre_columna}</th><th>Cantidad</th></tr></thead>
        <tbody>
            {filas_html}
            <tr><td><b>Total</b></td><td><b>{len(serie)}</b></td></tr>
        </tbody>
    </table>
    """


def _formatear_horas_locales(df, columnas=("hora_creacion", "hora_limite", "hora_despacho")):
    """Convierte columnas de datetime con zona horaria mixta (una por fila,
    según el país de la orden) a texto legible en SU hora local.

    Streamlit/pyarrow no soportan una columna con offsets de zona horaria
    distintos por fila: al serializarla para mostrarla, le pegan a todas las
    filas el offset de la primera que encuentran (una orden de México puede
    terminar mostrando "-05:00" de Colombia). El valor de fondo sigue siendo
    el instante correcto; solo la etiqueta se ve mal. Por eso, justo antes
    de mostrar o exportar, se convierte cada celda a texto ya en su propia
    hora local — así no hay ambigüedad de zona horaria que serializar.
    """
    df = df.copy()
    for col in columnas:
        if col in df.columns:
            df[col] = df[col].apply(lambda t: t.strftime("%Y-%m-%d %H:%M") if pd.notna(t) else None)
    return df


def _sin_zona_horaria(valor):
    """Excel no soporta datetimes con zona horaria; quitamos el tzinfo justo
    antes de exportar (las horas ya están en la hora local correcta, solo
    se pierde la etiqueta de zona)."""
    if isinstance(valor, pd.Timestamp) and valor.tzinfo is not None:
        return valor.tz_localize(None)
    return valor


def construir_excel(detalle_df, columnas_detalle, incluir_metodo=True):
    """Arma un Excel con el detalle y los desgloses solicitados."""
    detalle_df = detalle_df.copy()
    for col in ("hora_creacion", "hora_limite", "hora_despacho"):
        if col in detalle_df.columns:
            detalle_df[col] = detalle_df[col].map(_sin_zona_horaria)

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        detalle_df[columnas_detalle].to_excel(writer, sheet_name="Detalle", index=False)
        if incluir_metodo:
            detalle_df["metodo_envio"].value_counts().rename("cantidad").to_frame().to_excel(
                writer, sheet_name="Por metodo de envio"
            )
        detalle_df["transportadora"].fillna("Sin transportadora").value_counts().rename(
            "cantidad"
        ).to_frame().to_excel(writer, sheet_name="Por transportadora")
    buffer.seek(0)
    return buffer


def barra_horizontal(serie, color="#7C4DFF"):
    """Grafica una serie (value_counts) como barras horizontales tipo relleno."""
    conteo = serie.value_counts().sort_values(ascending=True)
    fig = px.bar(
        conteo,
        x=conteo.values,
        y=conteo.index,
        orientation="h",
        text=conteo.values,
        color_discrete_sequence=[color],
    )
    fig.update_traces(
        textposition="inside",
        insidetextanchor="middle",
        textfont=dict(color="white", size=14),
        marker=dict(line=dict(width=0)),
    )
    fig.update_layout(
        showlegend=False,
        xaxis_visible=False,
        yaxis_title=None,
        xaxis_title=None,
        margin=dict(l=0, r=0, t=10, b=0),
        height=45 * len(conteo) + 20,
        bargap=0.35,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_yaxes(tickfont=dict(size=14))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

if "data" not in st.session_state:
    with st.spinner("Cargando datos..."):
        st.session_state.data = get_shipping_data()
        st.session_state.entradas = get_entradas_por_hora()
        st.session_state.pickup = get_ordenes_pickup()
    st.session_state.ultima_actualizacion = datetime.now()

df = st.session_state.data
entradas = st.session_state.entradas
pickup = st.session_state.pickup

# =========================================================
# ENCABEZADO
# =========================================================
col_titulo, col_fecha, col_boton = st.columns([3, 1.3, 1])

with col_titulo:
    st.title("📦 Tablero de Envíos por Despachar")

with col_fecha:
    st.write("")  # separación vertical
    st.write(f"🕒 {st.session_state.ultima_actualizacion.strftime('%d/%m/%Y · %H:%M:%S')}")

with col_boton:
    st.write("")  # separación vertical
    if st.button("🔄 Actualizar", use_container_width=True):
        # Sin más código después de esto (nada de st.rerun()): un clic de
        # botón ya provoca su propia vuelta completa del script. Si se corta
        # la ejecución aquí con st.rerun(), el script nunca llega a crear los
        # selectbox de filtros más abajo en ESTA vuelta, y Streamlit borra el
        # estado de cualquier widget con key que no se haya instanciado —
        # así es como los filtros (filtro_pais/cedi/seller) se resetean solos.
        with st.spinner("Actualizando..."):
            st.session_state.data = get_shipping_data()
            st.session_state.entradas = get_entradas_por_hora()
            st.session_state.pickup = get_ordenes_pickup()
        st.session_state.ultima_actualizacion = datetime.now()

st.divider()

# =========================================================
# FILTROS
# =========================================================
f1, f2, f3, f4 = st.columns(4)

paises = ["Todos"] + sorted(df["pais"].dropna().unique().tolist())
cedis = ["Todos"] + sorted(df["cedi"].dropna().unique().tolist())
sellers = ["Todos"] + sorted(df["seller"].dropna().unique().tolist())


def limpiar_filtros():
    st.session_state.filtro_pais = "Todos"
    st.session_state.filtro_cedi = "Todos"
    st.session_state.filtro_seller = "Todos"


pais_sel = f1.selectbox("País", paises, key="filtro_pais")
cedi_sel = f2.selectbox("Cedi", cedis, key="filtro_cedi")
seller_sel = f3.selectbox("Seller", sellers, key="filtro_seller")

with f4:
    st.write("")
    st.button("✕ Limpiar filtros", use_container_width=True, on_click=limpiar_filtros)

# --- Aplicar filtros ---
df_filtrado = df.copy()
entradas_filtrado = entradas.copy()
pickup_filtrado = pickup.copy()
if pais_sel != "Todos":
    df_filtrado = df_filtrado[df_filtrado["pais"] == pais_sel]
    entradas_filtrado = entradas_filtrado[entradas_filtrado["pais"] == pais_sel]
    pickup_filtrado = pickup_filtrado[pickup_filtrado["pais"] == pais_sel]
if cedi_sel != "Todos":
    df_filtrado = df_filtrado[df_filtrado["cedi"] == cedi_sel]
    entradas_filtrado = entradas_filtrado[entradas_filtrado["cedi"] == cedi_sel]
    pickup_filtrado = pickup_filtrado[pickup_filtrado["cedi"] == cedi_sel]
if seller_sel != "Todos":
    df_filtrado = df_filtrado[df_filtrado["seller"] == seller_sel]
    entradas_filtrado = entradas_filtrado[entradas_filtrado["seller"] == seller_sel]
    pickup_filtrado = pickup_filtrado[pickup_filtrado["seller"] == seller_sel]

st.divider()

# --- Todo lo que NO se ha despachado todavía ---
pendientes = df_filtrado[df_filtrado["ubicacion"] != "Despachado"]
despachados = df_filtrado[df_filtrado["ubicacion"] == "Despachado"]

# --- Cálculos de cumplimiento / SLA, usados en varias secciones ---
# hora_limite/hora_despacho vienen de data.py ya con zona horaria (tz-aware,
# en la hora local de cada bodega: México, Colombia y Chile no comparten
# huso horario). "ahora" tiene que ser tz-aware también -si fuera
# datetime.now() a secas, pandas comparar naive contra aware truena, y si
# se comparara mal el desfase sería de 3 a 6 horas según el país.
ahora = datetime.now(timezone.utc)
ventana_urgente = timedelta(hours=2)

total_programadas = len(df_filtrado)
total_despachadas = len(despachados)
total_pendientes = len(pendientes)
pct_despachadas = (total_despachadas / total_programadas * 100) if total_programadas else 0
pct_pendientes = 100 - pct_despachadas if total_programadas else 0

vencidas = pendientes[pendientes["hora_limite"] < ahora].copy()
urgentes = pendientes[
    (pendientes["hora_limite"] >= ahora) & (pendientes["hora_limite"] <= ahora + ventana_urgente)
].copy()
despachadas_tarde = despachados[despachados["hora_despacho"] > despachados["hora_limite"]].copy()

if len(vencidas) > 0:
    vencidas["motivo"] = "Sigue sin despachar (vencida)"
if len(despachadas_tarde) > 0:
    despachadas_tarde["motivo"] = "Se despachó fuera de tiempo"
incumplidas = pd.concat([vencidas, despachadas_tarde], ignore_index=True)

# --- A partir de aquí ya no se hace ningún cálculo con estas horas, solo se
# muestran/exportan: se convierten a texto en su propia hora local (ver
# _formatear_horas_locales). ---
df_filtrado = _formatear_horas_locales(df_filtrado)
pendientes = _formatear_horas_locales(pendientes)
despachados = _formatear_horas_locales(despachados)
vencidas = _formatear_horas_locales(vencidas)
urgentes = _formatear_horas_locales(urgentes)
incumplidas = _formatear_horas_locales(incumplidas)

# =========================================================
# ALERTAS
# =========================================================
st.header("🔔 Alertas")

columnas_alerta = [
    "paquete_id", "cedi", "seller", "metodo_envio", "transportadora", "ubicacion", "ubicacion_fisica", "hora_limite",
]

if len(vencidas) > 0:
    st.error(f"🚨 {len(vencidas)} órdenes VENCIDAS: ya debieron salir y siguen sin despachar")
    with st.expander("Ver órdenes vencidas", expanded=True):
        st.dataframe(vencidas[columnas_alerta], use_container_width=True)

if len(urgentes) > 0:
    horas_ventana = int(ventana_urgente.total_seconds() // 3600)
    st.warning(f"⚠️ {len(urgentes)} órdenes deben salir sí o sí en las próximas {horas_ventana} horas")
    with st.expander("Ver órdenes urgentes", expanded=True):
        st.dataframe(urgentes[columnas_alerta], use_container_width=True)

if len(vencidas) == 0 and len(urgentes) == 0:
    st.success("✅ Sin alertas: no hay órdenes vencidas ni próximas a vencer")

st.divider()

# =========================================================
# INDICADOR GENERAL
# =========================================================
st.header("Resumen general")

st.caption("Por paquete físico — una orden con varios paquetes cuenta una vez por cada paquete")
r1, r2, r3 = st.columns(3)
r1.metric("Paquetes programados hoy", total_programadas)
r2.metric("Despachados", f"{total_despachadas} ({pct_despachadas:.1f}%)")
r3.metric("Pendientes por despachar", f"{total_pendientes} ({pct_pendientes:.1f}%)")

# --- Mismo resumen pero contando ÓRDENES únicas (sell_order.id) en vez de
# paquetes físicos: una orden con 3 paquetes cuenta 1 vez aquí, no 3. ---
total_ordenes_programadas = df_filtrado["orden_id"].nunique()
total_ordenes_despachadas = despachados["orden_id"].nunique()
total_ordenes_pendientes = pendientes["orden_id"].nunique()
pct_ordenes_despachadas = (
    total_ordenes_despachadas / total_ordenes_programadas * 100 if total_ordenes_programadas else 0
)
pct_ordenes_pendientes = 100 - pct_ordenes_despachadas if total_ordenes_programadas else 0

st.caption("Por orden — una orden con varios paquetes cuenta una sola vez")
r4, r5, r6 = st.columns(3)
r4.metric("Órdenes programadas hoy", total_ordenes_programadas)
r5.metric("Despachadas", f"{total_ordenes_despachadas} ({pct_ordenes_despachadas:.1f}%)")
r6.metric("Pendientes por despachar", f"{total_ordenes_pendientes} ({pct_ordenes_pendientes:.1f}%)")

st.divider()

# =========================================================
# POR MÉTODO DE ENVÍO
# =========================================================
st.header("Por método de envío")

if len(pendientes) > 0:
    barra_horizontal(pendientes["metodo_envio"])

marketplace = pendientes[pendientes["marketplace_nombre"].notna()]
if len(marketplace) > 0:
    with st.expander("Desglose por marketplace", expanded=True):
        barra_horizontal(marketplace["marketplace_nombre"], color="#26C6DA")

transportadora_asignada = pendientes[pendientes["transportadora"].notna()]
if len(transportadora_asignada) > 0:
    with st.expander("Desglose por transportadora", expanded=True):
        barra_horizontal(transportadora_asignada["transportadora"])

st.divider()

# =========================================================
# ENTRADAS POR HORA - MISMO DÍA / SIGUIENTE DÍA (por país)
# =========================================================
st.header("📈 Entradas por hora – Mismo día vs Siguiente día")
st.caption(
    "Cada país usa su propio nombre de método (ej. 'Mismo día hábil local MX' vs "
    "'... COL' vs '... CL', y variantes como 'Siguiente día hábil local mediano' en "
    "Tultitlán) — por eso se separa por país en vez de mezclar todo en un solo total."
)

COLOR_MISMO_DIA = "#7C4DFF"
COLOR_SIGUIENTE_DIA = "#FF9800"

mismo_dia_todas = entradas_filtrado[
    entradas_filtrado["metodo_envio"].str.contains("mismo día", case=False, na=False)
]
siguiente_dia_todas = entradas_filtrado[
    entradas_filtrado["metodo_envio"].str.contains("siguiente día", case=False, na=False)
]

paises_presentes = sorted(entradas_filtrado["pais"].dropna().unique().tolist())
columnas_pais = st.columns(len(paises_presentes)) if paises_presentes else []
for col, pais_actual in zip(columnas_pais, paises_presentes):
    mismo_dia_pais = (mismo_dia_todas["pais"] == pais_actual).sum()
    siguiente_dia_pais = (siguiente_dia_todas["pais"] == pais_actual).sum()
    col.metric(f"{pais_actual} — Mismo día", mismo_dia_pais)
    col.metric(f"{pais_actual} — Siguiente día", siguiente_dia_pais)

horas_texto = [f"{h:02d}:00" for h in range(24)]
bloques = []
for pais_actual in paises_presentes:
    conteo_mismo_dia = (
        mismo_dia_todas.loc[mismo_dia_todas["pais"] == pais_actual, "hora_creacion_hora_local"]
        .value_counts().reindex(range(24), fill_value=0).sort_index()
    )
    conteo_siguiente_dia = (
        siguiente_dia_todas.loc[siguiente_dia_todas["pais"] == pais_actual, "hora_creacion_hora_local"]
        .value_counts().reindex(range(24), fill_value=0).sort_index()
    )
    bloques.append(pd.DataFrame({
        "hora": horas_texto * 2,
        "pais": pais_actual,
        "metodo": ["Mismo día"] * 24 + ["Siguiente día"] * 24,
        "ordenes": list(conteo_mismo_dia.values) + list(conteo_siguiente_dia.values),
    }))
datos_horas = pd.concat(bloques, ignore_index=True) if bloques else pd.DataFrame(
    columns=["hora", "pais", "metodo", "ordenes"]
)

if len(datos_horas) > 0:
    fig_horas = px.bar(
        datos_horas,
        x="hora",
        y="ordenes",
        color="metodo",
        barmode="group",
        facet_col="pais",
        text="ordenes",
        color_discrete_map={"Mismo día": COLOR_MISMO_DIA, "Siguiente día": COLOR_SIGUIENTE_DIA},
    )
    fig_horas.update_traces(textposition="outside")
    fig_horas.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
    fig_horas.update_layout(
        xaxis_title=None,
        yaxis_title="Órdenes",
        legend_title=None,
        margin=dict(l=0, r=0, t=30, b=0),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_horas, use_container_width=True, config={"displayModeBar": False})

columnas_entradas_detalle = [
    "orden_numero", "pais", "cedi", "seller", "metodo_envio", "estado", "hora_creacion",
]
mismo_dia_detalle = _formatear_horas_locales(mismo_dia_todas, columnas=("hora_creacion",))
siguiente_dia_detalle = _formatear_horas_locales(siguiente_dia_todas, columnas=("hora_creacion",))

with st.expander(f"Ver detalle — Mismo día ({len(mismo_dia_detalle)})"):
    st.dataframe(
        mismo_dia_detalle[columnas_entradas_detalle].sort_values("hora_creacion"),
        use_container_width=True,
    )
with st.expander(f"Ver detalle — Siguiente día ({len(siguiente_dia_detalle)})"):
    st.dataframe(
        siguiente_dia_detalle[columnas_entradas_detalle].sort_values("hora_creacion"),
        use_container_width=True,
    )

st.divider()

# =========================================================
# POR UBICACIÓN
# =========================================================
st.header("Por ubicación")
st.caption(
    "Basado en la ubicación física real del paquete (bin/posición en la bodega), "
    "no en el estado de la orden."
)

u1, u2, u3 = st.columns(3)

sorting = pendientes[pendientes["ubicacion_fisica"].str.contains("SORTER", case=False, na=False)]
en_pendiente = pendientes[
    pendientes["ubicacion_fisica"].str.contains("PEN", case=False, na=False)
    & pendientes["transportadora"].isna()
]
en_estiba = pendientes[
    pendientes["ubicacion_fisica"].str.contains("ESTIBA", case=False, na=False)
    & pendientes["transportadora"].isna()
]

u1.metric("SORTER", len(sorting))
u2.metric("Pendiente (sin transportadora)", len(en_pendiente))
u3.metric("Estiba (sin transportadora)", len(en_estiba))

with st.expander("Ver detalle"):
    columnas_ubicacion = ["paquete_id", "cedi", "seller", "metodo_envio", "ubicacion_fisica", "transportadora"]
    st.write("**SORTER**")
    st.dataframe(sorting[columnas_ubicacion], use_container_width=True)
    st.write("**Pendiente (sin transportadora)**")
    st.dataframe(en_pendiente[columnas_ubicacion], use_container_width=True)
    st.write("**Estiba (sin transportadora)**")
    st.dataframe(en_estiba[columnas_ubicacion], use_container_width=True)

st.divider()

# =========================================================
# DETALLE COMPLETO DE PENDIENTES
# =========================================================
with st.expander("Ver detalle completo de órdenes por despachar"):
    st.dataframe(pendientes, use_container_width=True)

st.divider()

# =========================================================
# ÓRDENES INCUMPLIDAS
# =========================================================
st.header("❌ Órdenes incumplidas")

st.metric("Total de órdenes incumplidas", len(incumplidas))

if len(incumplidas) > 0:
    columnas_incumplidas = [
        "paquete_id", "cedi", "seller", "metodo_envio", "transportadora",
        "ubicacion", "ubicacion_fisica", "hora_limite", "hora_despacho", "motivo",
    ]
    st.dataframe(incumplidas[columnas_incumplidas], use_container_width=True)
else:
    st.success("No hay órdenes incumplidas por ahora 🎉")

st.divider()

# =========================================================
# ÓRDENES PICKUP (recogida en tienda/CEDI)
# =========================================================
st.header("📦 Órdenes Pickup")
st.caption(
    "Todos los métodos de envío 'Recogida...' (Express, Masiva, B2B, etc.), sin importar cuándo "
    "se crearon — el objetivo es detectar las que llevan mucho tiempo sin que el cliente pase por ellas."
)

pickup_detalle = _formatear_horas_locales(
    pickup_filtrado, columnas=("hora_creacion", "hora_limite_recogida", "hora_recogida")
)

# --- La vista principal es por ORDEN (una orden puede tener muchos
# paquetes/cajas físicas — no tiene sentido repetir la misma orden 150
# veces solo porque se dividió en 150 cajas). El detalle por caja se deja
# solo en el Excel descargable. ---
pickup_ordenes = pickup_detalle.groupby("orden_id", as_index=False).agg(
    orden_numero=("orden_numero", "first"),
    pais=("pais", "first"),
    cedi=("cedi", "first"),
    seller=("seller", "first"),
    metodo_envio=("metodo_envio", "first"),
    hora_limite_recogida=("hora_limite_recogida", "first"),
    hora_recogida=("hora_recogida", "first"),
    dias_vencido_pickup=("dias_vencido_pickup", "first"),
    debe_cancelarse=("debe_cancelarse", "first"),
    cajas=("paquete_id", "count"),
)
columnas_pickup_orden = [
    "orden_numero", "cedi", "seller", "metodo_envio",
    "hora_limite_recogida", "hora_recogida", "dias_vencido_pickup", "cajas",
]
columnas_pickup_cajas = [
    "paquete_id", "orden_numero", "cedi", "seller", "metodo_envio",
    "hora_limite_recogida", "hora_recogida", "dias_vencido_pickup",
]

vencidas_pickup = pickup_ordenes[pickup_ordenes["debe_cancelarse"]]

p1, p2 = st.columns(2)
p1.metric("Órdenes pickup pendientes", len(pickup_ordenes))
p2.metric("Vencidas (+15 días, deben cancelarse)", len(vencidas_pickup))

if len(vencidas_pickup) > 0:
    st.error(
        f"🚨 {len(vencidas_pickup)} órdenes pickup tienen más de 15 días desde su fecha límite de "
        "recogida y el cliente no ha pasado por ellas — deben cancelarse por espacio."
    )
    with st.expander("Ver órdenes pickup vencidas (+15 días)", expanded=True):
        st.dataframe(vencidas_pickup[columnas_pickup_orden], use_container_width=True)
else:
    st.success("✅ Ninguna orden pickup lleva más de 15 días esperando.")

with st.expander(f"Ver todas las órdenes pickup pendientes ({len(pickup_ordenes)})"):
    st.dataframe(pickup_ordenes[columnas_pickup_orden], use_container_width=True)

pickup_excel_buffer = io.BytesIO()
with pd.ExcelWriter(pickup_excel_buffer, engine="openpyxl") as writer:
    pickup_ordenes[columnas_pickup_orden].to_excel(writer, sheet_name="Ordenes pickup", index=False)
    pickup_detalle[columnas_pickup_cajas].to_excel(writer, sheet_name="Cajas por orden", index=False)
pickup_excel_buffer.seek(0)
st.download_button(
    "⬇️ Descargar Excel — Órdenes Pickup",
    data=pickup_excel_buffer,
    file_name=f"ordenes_pickup_{date.today().strftime('%Y%m%d')}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

st.divider()

# =========================================================
# CIERRE DE DÍA (printable) — todo lo que ya despachamos
# =========================================================
st.header("📋 Cierre de día")

columnas_cierre = [
    "paquete_id", "cedi", "seller", "transportadora", "hora_despacho",
]

st.download_button(
    "⬇️ Descargar Excel — Cierre de día",
    data=construir_excel(despachados, columnas_cierre, incluir_metodo=False),
    file_name=f"cierre_de_dia_{date.today().strftime('%Y%m%d')}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

cuerpo_cierre = f"""
<p><i>Reporte del {date.today().strftime('%d/%m/%Y')}</i></p>
<p><b>Total despachado hoy:</b> {total_despachadas} de {total_programadas} programadas ({pct_despachadas:.1f}%)</p>
<h3>Por transportadora</h3>
{tabla_conteo_html(despachados["transportadora"], "Transportadora")}
"""
render_reporte_imprimible(cuerpo_cierre, altura=420)

st.divider()

# =========================================================
# ÓRDENES VENCIDAS (printable) — lo que se venció y no se despachó
# =========================================================
st.header("🚫 Vencidas")

columnas_vencidas = [
    "paquete_id", "cedi", "seller", "metodo_envio", "transportadora", "ubicacion", "ubicacion_fisica", "hora_limite",
]

st.download_button(
    "⬇️ Descargar Excel — Vencidas",
    data=construir_excel(vencidas, columnas_vencidas),
    file_name=f"vencidas_{date.today().strftime('%Y%m%d')}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

cuerpo_vencidas = f"""
<p><i>Reporte del {date.today().strftime('%d/%m/%Y')}</i></p>
<p><b>Total de órdenes vencidas:</b> {len(vencidas)} de {total_programadas} programadas</p>
<h3>Por método de envío</h3>
{tabla_conteo_html(vencidas["metodo_envio"], "Método de envío")}
<h3>Por transportadora</h3>
{tabla_conteo_html(vencidas["transportadora"].fillna("Sin transportadora"), "Transportadora")}
"""
render_reporte_imprimible(cuerpo_vencidas, altura=420)
