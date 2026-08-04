import streamlit as st
import streamlit.components.v1 as components
import plotly.express as px
from datetime import datetime
from data import get_shipping_data

st.set_page_config(page_title="Tablero de Envíos", layout="wide")


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

# --- Botón de imprimir ---
components.html(
    """
    <button onclick="window.parent.print()" style="
        background-color:#FF4B4B; color:white; border:none;
        padding:0.5em 1.2em; border-radius:6px; font-size:1em;
        cursor:pointer;">
        🖨️ Imprimir reporte
    </button>
    """,
    height=50,
)

st.divider()

# =========================================================
# FILTROS
# =========================================================
f1, f2, f3, f4 = st.columns(4)

paises = ["Todos"] + sorted(df["pais"].dropna().unique().tolist())
cedis = ["Todos"] + sorted(df["cedi"].dropna().unique().tolist())
sellers = ["Todos"] + sorted(df["seller"].dropna().unique().tolist())

pais_sel = f1.selectbox("País", paises)
cedi_sel = f2.selectbox("Cedi", cedis)
seller_sel = f3.selectbox("Seller", sellers)

with f4:
    st.write("")
    if st.button("✕ Limpiar filtros", use_container_width=True):
        st.rerun()

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

# =========================================================
# INDICADOR GENERAL
# =========================================================
st.header("Resumen general")
st.metric("Órdenes para despachar hoy (todos los métodos)", len(pendientes))

st.divider()

# =========================================================
# POR MÉTODO DE ENVÍO
# =========================================================
st.header("Por método de envío")

c1, c2, c3, c4, c5 = st.columns(5)

mismo_dia = pendientes[pendientes["metodo_envio"] == "Mismo día"]
siguiente_dia = pendientes[pendientes["metodo_envio"] == "Siguiente día"]
estandar = pendientes[pendientes["metodo_envio"] == "Estándar"]
marketplace = pendientes[pendientes["metodo_envio"] == "Marketplace"]
pickup = pendientes[pendientes["metodo_envio"] == "Pickup"]

c1.metric("Mismo día", len(mismo_dia))
c2.metric("Siguiente día", len(siguiente_dia))
c3.metric("Estándar", len(estandar))
c4.metric("Marketplace (externo)", len(marketplace))
c5.metric("Pickup (recolección)", len(pickup))

if len(estandar) > 0:
    with st.expander("Desglose Estándar por transportadora", expanded=True):
        barra_horizontal(estandar["transportadora"])

if len(marketplace) > 0:
    with st.expander("Desglose por marketplace", expanded=True):
        barra_horizontal(marketplace["marketplace_nombre"], color="#26C6DA")

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
# YA DESPACHADO / ENVIADO
# =========================================================
st.header("✅ Ya despachado / enviado")
st.metric("Total despachado hoy", len(despachados))
st.dataframe(despachados, use_container_width=True)
