import streamlit as st
import streamlit.components.v1 as components
import plotly.express as px
import pandas as pd
import io
import html as html_lib
from datetime import datetime, date, timedelta
from data import get_shipping_data

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


def construir_excel(detalle_df, columnas_detalle):
    """Arma un Excel con el detalle y los desgloses por método y transportadora."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        detalle_df[columnas_detalle].to_excel(writer, sheet_name="Detalle", index=False)
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
    st.session_state.data = get_shipping_data()
    st.session_state.ultima_actualizacion = datetime.now()

df = st.session_state.data

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
        st.session_state.data = get_shipping_data()
        st.session_state.ultima_actualizacion = datetime.now()
        st.rerun()

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
if pais_sel != "Todos":
    df_filtrado = df_filtrado[df_filtrado["pais"] == pais_sel]
if cedi_sel != "Todos":
    df_filtrado = df_filtrado[df_filtrado["cedi"] == cedi_sel]
if seller_sel != "Todos":
    df_filtrado = df_filtrado[df_filtrado["seller"] == seller_sel]

st.divider()

# --- Todo lo que NO se ha despachado todavía ---
pendientes = df_filtrado[df_filtrado["ubicacion"] != "Despachado"]
despachados = df_filtrado[df_filtrado["ubicacion"] == "Despachado"]

# --- Cálculos de cumplimiento / SLA, usados en varias secciones ---
ahora = datetime.now()
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

# =========================================================
# ALERTAS
# =========================================================
st.header("🔔 Alertas")

columnas_alerta = ["paquete_id", "cedi", "metodo_envio", "transportadora", "ubicacion", "hora_limite"]

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

r1, r2, r3 = st.columns(3)
r1.metric("Órdenes programadas hoy", total_programadas)
r2.metric("Despachadas", f"{total_despachadas} ({pct_despachadas:.1f}%)")
r3.metric("Pendientes por despachar", f"{total_pendientes} ({pct_pendientes:.1f}%)")

st.divider()

# =========================================================
# POR MÉTODO DE ENVÍO
# =========================================================
st.header("Por método de envío")

c1, c2, c3, c4 = st.columns(4)

mismo_dia = pendientes[pendientes["metodo_envio"] == "Mismo día"]
siguiente_dia = pendientes[pendientes["metodo_envio"] == "Siguiente día"]
estandar = pendientes[pendientes["metodo_envio"] == "Estándar"]
marketplace = pendientes[pendientes["metodo_envio"] == "Marketplace"]

c1.metric("Mismo día", len(mismo_dia))
c2.metric("Siguiente día", len(siguiente_dia))
c3.metric("Estándar", len(estandar))
c4.metric("Marketplace (externo)", len(marketplace))

c5, c6, c7 = st.columns(3)

pickup = pendientes[pendientes["metodo_envio"] == "Pickup"]
b2b_estandar = pendientes[pendientes["metodo_envio"] == "B2B Estándar"]
b2b_agendado = pendientes[pendientes["metodo_envio"] == "B2B Envío agendado"]

c5.metric("Pickup (recolección)", len(pickup))
c6.metric("B2B Estándar", len(b2b_estandar))
c7.metric("B2B Envío agendado", len(b2b_agendado))

if len(estandar) > 0:
    with st.expander("Desglose Estándar por transportadora", expanded=True):
        barra_horizontal(estandar["transportadora"])

if len(marketplace) > 0:
    with st.expander("Desglose por marketplace", expanded=True):
        barra_horizontal(marketplace["marketplace_nombre"], color="#26C6DA")

st.divider()

# =========================================================
# ENTRADAS POR HORA - MISMO DÍA
# =========================================================
st.header("📈 Entradas por hora – Mismo día")

mismo_dia_todas = df_filtrado[df_filtrado["metodo_envio"] == "Mismo día"]
conteo_horas = (
    mismo_dia_todas["hora_creacion"].dt.hour.value_counts().reindex(range(24), fill_value=0).sort_index()
)

fig_horas = px.bar(
    x=[f"{h:02d}:00" for h in conteo_horas.index],
    y=conteo_horas.values,
    text=conteo_horas.values,
)
fig_horas.update_traces(marker_color="#7C4DFF", textposition="outside")
fig_horas.update_layout(
    xaxis_title=None,
    yaxis_title="Órdenes",
    margin=dict(l=0, r=0, t=10, b=0),
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
)
st.plotly_chart(fig_horas, use_container_width=True, config={"displayModeBar": False})

st.divider()

# =========================================================
# POR UBICACIÓN
# =========================================================
st.header("Por ubicación")

u1, u2, u3 = st.columns(3)

sorting = pendientes[pendientes["ubicacion"] == "Sorting"]
en_pendiente = pendientes[
    (pendientes["ubicacion"] == "Pendiente") & (pendientes["transportadora"].isna())
]
en_estiba = pendientes[
    (pendientes["ubicacion"] == "Estiba") & (pendientes["transportadora"].isna())
]

u1.metric("Sorting", len(sorting))
u2.metric("Pendiente (sin transportadora)", len(en_pendiente))
u3.metric("Estiba (sin transportadora)", len(en_estiba))

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
        "paquete_id", "cedi", "metodo_envio", "transportadora",
        "ubicacion", "hora_limite", "hora_despacho", "motivo",
    ]
    st.dataframe(incumplidas[columnas_incumplidas], use_container_width=True)
else:
    st.success("No hay órdenes incumplidas por ahora 🎉")

st.divider()

# =========================================================
# CIERRE DE DÍA (printable) — todo lo que ya despachamos
# =========================================================
st.header("📋 Cierre de día")

columnas_cierre = ["paquete_id", "cedi", "metodo_envio", "marketplace_nombre", "transportadora", "hora_despacho"]

st.download_button(
    "⬇️ Descargar Excel — Cierre de día",
    data=construir_excel(despachados, columnas_cierre),
    file_name=f"cierre_de_dia_{date.today().strftime('%Y%m%d')}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

cuerpo_cierre = f"""
<p><i>Reporte del {date.today().strftime('%d/%m/%Y')}</i></p>
<p><b>Total despachado hoy:</b> {total_despachadas} de {total_programadas} programadas ({pct_despachadas:.1f}%)</p>
<h3>Por método de envío</h3>
{tabla_conteo_html(despachados["metodo_envio"], "Método de envío")}
<h3>Por transportadora</h3>
{tabla_conteo_html(despachados["transportadora"], "Transportadora")}
"""
render_reporte_imprimible(cuerpo_cierre, altura=420)

st.divider()

# =========================================================
# ÓRDENES VENCIDAS (printable) — lo que se venció y no se despachó
# =========================================================
st.header("🚫 Vencidas")

columnas_vencidas = ["paquete_id", "cedi", "metodo_envio", "transportadora", "ubicacion", "hora_limite"]

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
