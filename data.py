"""
Módulo de acceso a datos.

get_shipping_data() consulta la base de datos real de Melonn (MySQL) y
regresa un DataFrame con estas columnas, que es lo único que espera app.py:

    paquete_id          -> identificador del paquete (orden-paquete)
    orden_id            -> id numérico de la orden (sell_order.id). Varios
                            paquetes pueden compartir el mismo orden_id
                            cuando una orden se divide en más de un paquete
                            físico — sirve para contar por ORDEN en vez de
                            por PAQUETE.
    pais                -> país del CEDI asignado a la orden
    cedi                -> bodega/almacén asignado
    metodo_envio        -> nombre real del shipping_method de la orden
    marketplace_nombre  -> nombre del marketplace (Mercado Libre, Amazon,
                            Walmart, Liverpool, Coppel, Rappi, TikTok).
                            None si la orden viene de tienda propia (Shopify,
                            WooCommerce, VTEX, etc.) o de otro canal.
    seller              -> nombre del seller (tabla `seller`)
    transportadora      -> nombre de la courier_company asignada. None si
                            todavía no se asigna transportadora.
    ubicacion           -> 'Pendiente', 'Sorting', 'Estiba' o 'Despachado',
                            derivado del estado real de la orden
                            (sell_order_state) y de si ya tiene
                            ship_timestamp registrado.
    ubicacion_fisica    -> nombre real del bin/posición física donde está
                            el paquete ahora mismo (ej. 'SORTER-8',
                            'TINA-09', 'ESTIBA-01'), de
                            sell_order_warehouse_location -> warehouse_bin.
                            None si la orden no tiene una ubicación física
                            registrada — OJO: esto solo cubre una fracción
                            chica de las órdenes activas (la tabla
                            sell_order_warehouse_location es chica, ~8,400
                            filas en total), así que la mayoría va a salir
                            en None. Cuando hay más de una ubicación
                            registrada para la misma orden (se movió de
                            bin), se toma la más reciente (MAX(id)).
    fecha_salida         -> fecha de la promesa de despacho (ship_promise_max)
    hora_creacion        -> sell_order.creation_date
    hora_limite           -> ship_promise_max del intento vigente (SLA)
    hora_despacho          -> ship_timestamp del intento vigente. None si
                            todavía no se ha despachado.
    hora_creacion_hora_local -> hora del día (0-23) de hora_creacion ya en
                            hora local de la bodega, para el gráfico de
                            "Entradas por hora".

hora_creacion, hora_limite y hora_despacho quedan en la hora LOCAL de la
bodega de cada orden (no UTC), cada una como datetime con zona horaria
(tz-aware). Como México, Colombia y Chile tienen zonas distintas, la
columna combinada queda con "zona horaria mixta por fila" (dtype object en
vez de datetime64 uniforme) — las comparaciones (<, >, ==) funcionan bien
igual, pero el accessor .dt de pandas no aplica sobre ella.

IMPORTANTE: los filtros de País, Cedi, Seller y Marketplace en app.py se
arman automáticamente a partir de los valores ÚNICOS que existan en estas
columnas. La sección "Por método de envío" también se arma dinámicamente a
partir de los métodos reales que devuelva la base de datos (son ~65 métodos
distintos, no las 7 categorías genéricas que se usaban con datos de prueba).

Credenciales: se leen de un archivo .env en la raíz del proyecto (no se
sube a git, ver .gitignore). Debe tener DB_HOST, DB_PORT, DB_NAME, DB_USER,
DB_PASS.

Alcance de "hoy": una orden se considera "de hoy" cuando su fecha máxima de
despacho (ship_promise_max del intento vigente) cae en el día de hoy. Esto
es una decisión de negocio confirmada con Julián: si una orden vencida de
un día anterior sigue sin despacharse, deja de aparecer en el tablero al
día siguiente porque su fecha máxima ya no es "hoy".

ZONA HORARIA: todas las columnas de fecha/hora en MySQL están en UTC (el
servidor corre con time_zone=SYSTEM=UTC). "Hoy" y "vencida" tienen que
evaluarse en la hora LOCAL de cada bodega (México, Colombia y Chile no
comparten zona horaria), así que:
  1. La consulta SQL trae un margen amplio en UTC (un día antes y dos
     después de CURDATE()) para no cortar por accidente el "hoy" local de
     ningún país cerca de la medianoche UTC.
  2. En Python, cada timestamp se localiza primero como UTC y luego se
     convierte a la zona horaria de `warehouse.timezone_code` de esa
     orden (America/Mexico_City, America/Bogota, America/Santiago).
  3. El filtro final de "hoy" compara la fecha ya convertida a hora local
     contra la fecha de hoy en ESA misma zona horaria (no la fecha de hoy
     del servidor).
Por esto mismo, en app.py la comparación de "ahora" contra hora_limite
también debe hacerse con un datetime con zona horaria (aware), no con
datetime.now() a secas — de lo contrario se compara UTC contra hora local
del sistema y las alertas de vencidas/urgentes salen mal por 3 a 6 horas
según el país.

Estados (confirmado con Julián): un paquete cuenta como "activo hoy" si
CUALQUIERA de estas dos cosas es cierta:
  (a) su estado actual es uno de los 8 que representan trabajo activo sin
      despachar todavía — All items reserved - ready for fulfillment,
      Picking, Picked, Ready For Packing, Packing, Packed,
      Prepared for dispatch, Selected for dispatch preparation; o
  (b) ya tiene ship_timestamp (ya se despachó), SIN IMPORTAR a qué estado
      haya avanzado después (Shipped - in transit, Delivered to buyer,
      Picked-up by buyer, Delivery not posible, etc.).
Lo que NO cuenta nunca: estados "atorados/bloqueados" que preceden al
despacho — on stand by (sin stock / condición externa / restricción SM /
promesa vencida), Processing Requested, Received - valid sin reservar,
Received - invalid fixable, Fixed & valid - to be processed, Error, All
items reserved - fulfillment on hold (las 2 variantes) — y Canceled.

IMPORTANTE (bug real que motivó este diseño): antes "Despachado" SOLO
contaba el estado "Shipped - in transit". En cuanto una orden avanzaba el
MISMO DÍA a "Delivered to buyer" o "Picked-up by buyer" (común en entregas
locales/mismo día), desaparecía del tablero por completo — se encontró con
la ruta R0000548259, donde 14 de 15 órdenes ya estaban "Delivered to
buyer" y ninguna aparecía como despachada. Por eso "Despachado" ahora se
basa PURAMENTE en ship_timestamp, sin filtrar por estado.

Mapeo de estado real -> ubicación (confirmado con Julián; solo aplica si
TODAVÍA no tiene ship_timestamp — si ya lo tiene, es "Despachado" pase lo
que pase con el estado):
    Pendiente  -> All items reserved - ready for fulfillment
    Sorting    -> Picking, Picked, Ready For Packing, Packing, Packed
    Estiba     -> Prepared for dispatch, Selected for dispatch preparation
    Despachado -> ship_timestamp IS NOT NULL (no depende del estado).

Cada paquete se cuenta UNA sola vez: se toma el estado ACTUAL de la orden
(so.sell_order_state_id), no su historial, así que no hay riesgo de contar
el mismo paquete dos veces al pasar de un estado a otro.

"Hoy" significa cosas distintas según si el paquete ya se despachó o no
(confirmado con Julián):
  - Si ya tiene hora_despacho (ship_timestamp): cuenta como "de hoy" (y por
    lo tanto como Despachado) solo si ese despacho ocurrió HOY, en la hora
    local de la bodega — sin importar cuál era su fecha límite prometida.
    Si se despachó otro día, no se cuenta (así "Despachadas" refleja lo que
    de verdad salió hoy, no una mezcla de días).
  - Si todavía no se despacha: cuenta como "de hoy" si su fecha límite
    (ship_promise_max) cae hoy, en la hora local de la bodega.
"""

import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pymysql
from dotenv import load_dotenv

load_dotenv()

MARKETPLACES = {"meli": "Mercado Libre", "amazon": "Amazon", "walmart": "Walmart",
                 "liverpool": "Liverpool", "coppel": "Coppel", "rappi": "Rappi",
                 "tiktok": "TikTok"}

# Criterio único de "orden activa por despachar hoy", usado en TODO el
# tablero (Resumen general, Alertas, Por método de envío, Entradas por
# hora, todo) — confirmado con Julián: cuenta lo que está avanzando en el
# flujo del almacén (incluyendo "lista para empacar"), NO cuenta lo
# atorado/bloqueado (sin stock, en espera por condición externa, error,
# etc.) aunque técnicamente esté "activo".
ESTADOS_PENDIENTE = (2,)              # All items reserved - ready for fulfillment
ESTADOS_SORTING = (3, 4, 28, 22, 5)   # Picking, Picked, Ready For Packing, Packing, Packed
ESTADOS_ESTIBA = (24, 25)             # Prepared for dispatch, Selected for dispatch preparation

# Estados que representan el paquete AÚN sin despachar. Se usan para
# clasificar "ubicacion" (Pendiente/Sorting/Estiba) en Python, y también
# como parte del filtro SQL (ver ESTADOS_BLOQUEADOS más abajo).
ESTADOS_SIN_DESPACHAR = ESTADOS_PENDIENTE + ESTADOS_SORTING + ESTADOS_ESTIBA

# Se mantiene el nombre ESTADOS_INCLUIDOS por compatibilidad con el resto
# del código/documentación que lo referencia como "el criterio de estados".
ESTADOS_INCLUIDOS = ESTADOS_SIN_DESPACHAR

# Estados que preceden al despacho y representan trabajo ATORADO/BLOQUEADO
# (no avanzando) — estos SÍ se excluyen siempre de la consulta SQL, porque
# por definición nunca tienen ship_timestamp (no pueden haberse despachado
# sin pasar antes por los estados de ESTADOS_SIN_DESPACHAR). Todo lo demás
# (incluyendo Shipped - in transit, Delivered to buyer, Picked-up by
# buyer, Delivery not posible, procesos de cancelación después de
# despachar) SÍ se deja pasar el filtro SQL, porque "Despachado" se decide
# después en Python únicamente por ship_timestamp IS NOT NULL — no por
# estado. Antes el filtro SQL solo dejaba pasar "Shipped - in transit"
# como único estado "despachado", y una orden que avanzaba el MISMO DÍA a
# "Delivered to buyer" o "Picked-up by buyer" (común en entregas locales)
# desaparecía del tablero por completo aunque sí se hubiera despachado hoy
# — bug real encontrado con la ruta R0000548259 (14 de 15 órdenes ya
# estaban "Delivered to buyer" y ninguna aparecía como despachada).
# Estados posteriores al despacho — cuentan como "Despachado" en Python
# (por ship_timestamp), sin importar cuál de estos sea el estado actual.
ESTADOS_YA_DESPACHADOS = (
    6,   # Picked-up by buyer
    7,   # Shipped - in transit
    8,   # Delivered to buyer
    17,  # On Cancelation Process - to be unpacked & relocated
    18,  # On Cancelation Process - to be received from courier
    19,  # In transit - Cancelation requested
    20,  # Delivery not posible
)

# Subconjunto de ESTADOS_YA_DESPACHADOS que ya "terminó su viaje" con
# éxito (nadie tiene que seguir haciendo nada con ellas). get_shipping_data()
# SÍ las cuenta como "Despachado" (por ship_timestamp, no por estado — ver
# arriba), pero get_entradas_por_hora() las excluye a propósito: confirmado
# con Julián que en el detalle de "Entradas por hora" (Mismo día/Siguiente
# día) solo deben verse las que siguen en proceso, aunque ya se hayan
# despachado hoy — ver una orden "Delivered to buyer" ahí generaba confusión.
ESTADOS_CONCLUIDOS = (6, 8)  # Picked-up by buyer, Delivered to buyer

# NOTA DE RENDIMIENTO: sell_order_attempt.ship_timestamp no tiene índice
# propio, así que la rama "ya despachadas" no puede acotarse tan agresivo
# por fecha de creación como la rama "sin despachar" (que sí aprovecha el
# índice compuesto por estado+fecha). Se usa una ventana más angosta (14
# días) solo para esa rama — se probó contra la ventana completa de 45
# días y la diferencia es de ~0.8% de filas (casi todo lo que se despacha
# hoy se creó en los últimos 14 días), a cambio de pasar de ~10s a ~0.6s.
DIAS_ATRAS_SIN_DESPACHAR = 45
DIAS_ATRAS_YA_DESPACHADO = 14


def _conexion(intentos=3, espera_segundos=2):
    """Reintenta la conexión: en algunas redes la resolución DNS del host
    de RDS falla de forma intermitente (no es un problema de la base de
    datos ni del query, se ha visto fallar así con dominios como
    google.com también), y suele resolver sola unos segundos después."""
    ultimo_error = None
    for intento in range(1, intentos + 1):
        try:
            return pymysql.connect(
                host=os.environ["DB_HOST"],
                port=int(os.environ["DB_PORT"]),
                user=os.environ["DB_USER"],
                password=os.environ["DB_PASS"],
                database=os.environ["DB_NAME"],
                charset="utf8mb4",
                connect_timeout=15,
            )
        except pymysql.err.OperationalError as e:
            ultimo_error = e
            if intento < intentos:
                time.sleep(espera_segundos)
    raise ultimo_error


# NOTA DE RENDIMIENTO: sell_order_attempt.ship_promise_max/ship_timestamp
# no tienen índice propio, y sell_order_attempt tiene ~9.5M filas — filtrar
# por esas columnas directamente fuerza un table scan completo. sell_order
# sí tiene índices compuestos por (sell_order_state_id, creation_date), así
# que la consulta se divide en DOS ramas (unidas por OR), cada una con su
# propia lista de estados + ventana de creation_date, para que MySQL pueda
# usar ese índice en ambas por separado en vez de un NOT IN amplio (que
# resultó en table scan — probado con EXPLAIN):
#   - Rama "sin despachar" (ESTADOS_SIN_DESPACHAR): ventana de 45 días,
#     para cubrir B2B agendado con bastante anticipación.
#   - Rama "ya despachadas" (ESTADOS_YA_DESPACHADOS): ventana de solo 14
#     días — no se puede acotar más por el estado (son pocos valores, ~7,
#     con mucho volumen histórico), así que se acota más por fecha. Se
#     verificó que la diferencia contra 45 días es de ~0.8% de filas.
#
# STRAIGHT_JOIN: sin esto, al agregar los joins de ubicación física
# (sell_order_warehouse_location/warehouse_bin) el optimizador de MySQL
# empezó a elegir mal la tabla por la que arranca el plan — escaneaba
# COMPLETA sell_order_attempt (9.5M filas) en vez de arrancar por sell_order
# y unir soa después por índice. STRAIGHT_JOIN obliga a MySQL a respetar el
# orden de las tablas tal como están escritas abajo (so -> soa -> sop -> ...),
# que es el orden correcto. Verificado con EXPLAIN: sin esto la fila de soa
# sale con type=ALL; con esto sale type=ref usando el índice.
_QUERY = f"""
    SELECT STRAIGHT_JOIN
        sop.id                          AS paquete_id_num,
        so.id                            AS orden_id,
        so.internal_order_number        AS orden_numero,
        w.country                       AS pais,
        w.name                          AS cedi,
        w.timezone_code                 AS zona_horaria,
        sm.name                         AS metodo_envio,
        ep.name                         AS ecommerce_platform,
        sel.name                        AS seller,
        cc.name                         AS transportadora,
        so.sell_order_state_id          AS estado_id,
        soa.ship_promise_max            AS hora_limite,
        soa.ship_timestamp              AS hora_despacho,
        so.creation_date                AS hora_creacion,
        wb.name                          AS ubicacion_fisica
    FROM sell_order so
    JOIN sell_order_attempt soa
        ON soa.sell_order_id = so.id
        AND soa.current = 1
    JOIN sell_order_package sop
        ON sop.sell_order_id = so.id
    LEFT JOIN (
        SELECT sell_order_id, MAX(id) AS ubicacion_id
        FROM sell_order_warehouse_location
        GROUP BY sell_order_id
    ) sowl_ultima ON sowl_ultima.sell_order_id = so.id
    LEFT JOIN sell_order_warehouse_location sowl
        ON sowl.id = sowl_ultima.ubicacion_id
    LEFT JOIN warehouse_bin wb
        ON wb.id = sowl.warehouse_bin_id
    LEFT JOIN warehouse w
        ON w.id = so.assigned_warehouse_id
    LEFT JOIN shipping_method sm
        ON sm.id = so.shipping_method_id
    LEFT JOIN seller sel
        ON sel.id = so.seller_id
    LEFT JOIN seller_ecommerce_store ses
        ON ses.id = so.seller_ecommerce_store_id
    LEFT JOIN ecommerce_platform ep
        ON ep.id = ses.ecommerce_platform_id
    LEFT JOIN delivery_service ds
        ON ds.sell_order_attempt_id = soa.id
    LEFT JOIN transport_service ts
        ON ts.id = ds.transport_service_id
    LEFT JOIN courier_company cc
        ON cc.id = ts.courier_company_id
    WHERE (
        (so.sell_order_state_id IN %(estados_sin_despachar)s
         AND so.creation_date >= CURDATE() - INTERVAL {DIAS_ATRAS_SIN_DESPACHAR} DAY
         AND soa.ship_promise_max >= CURDATE() - INTERVAL 1 DAY
         AND soa.ship_promise_max < CURDATE() + INTERVAL 2 DAY)
        OR
        (so.sell_order_state_id IN %(estados_ya_despachados)s
         AND so.creation_date >= CURDATE() - INTERVAL {DIAS_ATRAS_YA_DESPACHADO} DAY
         AND soa.ship_timestamp >= CURDATE() - INTERVAL 1 DAY
         AND soa.ship_timestamp < CURDATE() + INTERVAL 2 DAY)
    )
"""
# El filtro de fechas de arriba es solo un pre-filtro amplio en UTC (para
# aprovechar la ausencia de índice lo menos posible; el estado ya narrows
# muchísimo antes de llegar aquí). Trae por ship_promise_max (para las que
# siguen pendientes) O por ship_timestamp (para las que ya se despacharon),
# porque "hoy" se define distinto según el caso (ver docstring). El filtro
# exacto ya con cada fecha convertida a hora local se aplica después (ver
# _es_hoy_local).


def _ubicacion(estado_id, hora_despacho):
    if pd.notna(hora_despacho):
        return "Despachado"
    if estado_id in ESTADOS_PENDIENTE:
        return "Pendiente"
    if estado_id in ESTADOS_SORTING:
        return "Sorting"
    if estado_id in ESTADOS_ESTIBA:
        return "Estiba"
    return "Pendiente"


def _localizar_por_zona(df, columnas):
    """MySQL regresa estas columnas naive pero en UTC real (session
    time_zone=SYSTEM=UTC). Las convertimos a tz-aware en la zona horaria de
    la bodega de cada fila, agrupando por zona (solo 3 valores distintos)
    para que sea vectorizado en vez de fila por fila."""
    for col in columnas:
        convertido = pd.Series(index=df.index, dtype=object)
        for tz, grupo in df.groupby("zona_horaria"):
            convertido.loc[grupo.index] = grupo[col].dt.tz_localize("UTC").dt.tz_convert(ZoneInfo(tz))
        df[col] = convertido
    return df


def _es_hoy_local(df):
    """"Hoy" se define distinto según si el paquete ya se despachó o no
    (confirmado con Julián): si ya tiene hora_despacho, "hoy" es cuando ESE
    despacho ocurrió; si no, "hoy" es cuando vence su promesa. Ambas
    comparaciones se hacen en la hora local de la bodega de cada fila, no
    contra la fecha de hoy del servidor."""
    es_hoy = pd.Series(False, index=df.index)
    for tz, grupo in df.groupby("zona_horaria"):
        hoy_en_esa_zona = datetime.now(ZoneInfo(tz)).date()
        ya_despachado = grupo["hora_despacho"].notna()
        fecha_relevante = grupo["hora_despacho"].where(ya_despachado, grupo["hora_limite"])
        es_hoy.loc[grupo.index] = fecha_relevante.apply(lambda t: t.date() == hoy_en_esa_zona)
    return es_hoy


def get_shipping_data() -> pd.DataFrame:
    """Regresa los paquetes cuya fecha máxima de despacho es hoy, evaluada
    en la hora local de cada bodega."""

    conn = _conexion()
    try:
        df = pd.read_sql(_QUERY, conn, params={
            "estados_sin_despachar": ESTADOS_SIN_DESPACHAR,
            "estados_ya_despachados": ESTADOS_YA_DESPACHADOS,
        })
    finally:
        conn.close()

    # Sin bodega asignada no hay zona horaria con la cual ubicar "hoy" localmente.
    df = df.dropna(subset=["zona_horaria"]).copy()
    df = _localizar_por_zona(df, ["hora_creacion", "hora_limite", "hora_despacho"])
    df = df[_es_hoy_local(df)].copy()

    df["paquete_id"] = df["orden_numero"].fillna("SO").astype(str) + "-" + df["paquete_id_num"].astype(str)
    df["marketplace_nombre"] = df["ecommerce_platform"].map(
        lambda p: MARKETPLACES.get(str(p).lower()) if pd.notna(p) else None
    )
    df["ubicacion"] = df.apply(
        lambda r: _ubicacion(r["estado_id"], r["hora_despacho"]), axis=1
    )
    df["fecha_salida"] = df["hora_limite"].apply(lambda t: t.date())
    # hora_creacion queda con zona horaria mixta por fila (cada una en la
    # suya), así que .dt.hour no aplica: se calcula aparte para el gráfico
    # de "Entradas por hora".
    df["hora_creacion_hora_local"] = df["hora_creacion"].apply(lambda t: t.hour)

    columnas = [
        "paquete_id", "orden_id", "pais", "cedi", "metodo_envio", "marketplace_nombre",
        "seller", "transportadora", "ubicacion", "ubicacion_fisica", "fecha_salida",
        "hora_creacion", "hora_limite", "hora_despacho", "hora_creacion_hora_local",
    ]
    return df[columnas]


# get_shipping_data() solo trae lo que hay que DESPACHAR hoy (fecha límite
# hoy, o ya despachada hoy). Una orden "Siguiente día" creada hoy casi
# siempre tiene fecha límite de MAÑANA, así que nunca aparece ahí — pero sí
# "entró" hoy. Por eso "Entradas por hora" necesita su propia consulta,
# basada en creation_date en vez de ship_promise_max/ship_timestamp. Usa el
# MISMO criterio de estados (ESTADOS_BLOQUEADOS) que el resto del tablero,
# para que los números sean consistentes en todas partes.
#
# NOTA DE RENDIMIENTO: creation_date no tiene un índice propio (solo existe
# combinada con otras columnas, ej. (sell_order_state_id, creation_date)),
# así que filtrar solo por fecha fuerza un table scan de sell_order
# completo (~9.8M filas). El filtro de estado, además de ser necesario,
# permite aprovechar ese índice compuesto.
_QUERY_ENTRADAS = """
    SELECT
        so.internal_order_number AS orden_numero,
        so.creation_date         AS hora_creacion,
        sm.name                  AS metodo_envio,
        w.country                AS pais,
        w.name                   AS cedi,
        w.timezone_code          AS zona_horaria,
        sel.name                 AS seller,
        ss.name                  AS estado
    FROM sell_order so
    LEFT JOIN warehouse w
        ON w.id = so.assigned_warehouse_id
    LEFT JOIN shipping_method sm
        ON sm.id = so.shipping_method_id
    LEFT JOIN seller sel
        ON sel.id = so.seller_id
    LEFT JOIN sell_order_state ss
        ON ss.id = so.sell_order_state_id
    WHERE so.sell_order_state_id IN %(estados_activos)s
      AND so.creation_date >= CURDATE() - INTERVAL 1 DAY
      AND so.creation_date < CURDATE() + INTERVAL 2 DAY
"""


def get_entradas_por_hora() -> pd.DataFrame:
    """Regresa todas las órdenes CREADAS hoy (hora local de su bodega) que
    siguen en proceso — ESTADOS_SIN_DESPACHAR + ESTADOS_YA_DESPACHADOS menos
    ESTADOS_CONCLUIDOS (Picked-up/Delivered to buyer se excluyen a propósito
    aquí, ver ESTADOS_CONCLUIDOS) —, sin importar su fecha límite de
    despacho. Es la fuente de datos de la gráfica "Entradas por hora" —
    deliberadamente separada de get_shipping_data() por la fecha
    (creation_date vs ship_promise_max/ship_timestamp). Aquí sí se puede
    usar una sola lista de estados (a diferencia de get_shipping_data): la
    ventana de creation_date ya es angosta de por sí (~3 días), así que no
    hace falta partirla en dos ramas por rendimiento."""

    estados_activos = tuple(
        e for e in ESTADOS_SIN_DESPACHAR + ESTADOS_YA_DESPACHADOS if e not in ESTADOS_CONCLUIDOS
    )
    conn = _conexion()
    try:
        df = pd.read_sql(_QUERY_ENTRADAS, conn, params={"estados_activos": estados_activos})
    finally:
        conn.close()

    df = df.dropna(subset=["zona_horaria"]).copy()
    df = _localizar_por_zona(df, ["hora_creacion"])

    es_hoy = pd.Series(False, index=df.index)
    for tz, grupo in df.groupby("zona_horaria"):
        hoy_en_esa_zona = datetime.now(ZoneInfo(tz)).date()
        es_hoy.loc[grupo.index] = grupo["hora_creacion"].apply(lambda t: t.date() == hoy_en_esa_zona)
    df = df[es_hoy].copy()

    df["hora_creacion_hora_local"] = df["hora_creacion"].apply(lambda t: t.hour)
    return df[[
        "orden_numero", "pais", "cedi", "seller", "metodo_envio", "estado",
        "hora_creacion", "hora_creacion_hora_local",
    ]]


# --- Órdenes Pickup (recogida en tienda/CEDI) ---------------------------
#
# Todos los métodos de envío reales cuyo nombre contiene "Recogida"
# (confirmado: cubre Recogida, Recogida Express, Recogida Masiva,
# Recogida Mega-Masivo, Recogida Alternativa, Recogida B2B y sus variantes
# — cualquier método nuevo que empiece con "Recogida" se incluye solo con
# hacer match por texto, iguql que "mismo día"/"siguiente día").
METODOS_PICKUP_IDS = (13, 20, 26, 27, 44, 45, 46, 53, 54, 74)

# Regla de negocio (confirmada con Julián): el cliente tiene 15 días desde
# la promesa máxima de recogida (pickup_promise_max) para recoger su
# paquete; pasados esos 15 días sin recogerlo, la orden debe cancelarse
# (por espacio en el CEDI).
DIAS_LIMITE_PICKUP_SIN_RECOGER = 15

# Estados que representan una recogida ya resuelta (recogida, cancelada,
# etc.) — se excluyen porque ya no hay nada que esperar.
ESTADOS_PICKUP_RESUELTOS = (6, 7, 8, 15, 17, 18, 19, 20)

_QUERY_PICKUP = """
    SELECT STRAIGHT_JOIN
        sop.id                          AS paquete_id_num,
        so.id                            AS orden_id,
        so.internal_order_number        AS orden_numero,
        w.country                       AS pais,
        w.name                          AS cedi,
        w.timezone_code                 AS zona_horaria,
        sm.name                         AS metodo_envio,
        sel.name                        AS seller,
        soa.pickup_promise_max          AS hora_limite_recogida,
        soa.pickup_timestamp            AS hora_recogida,
        so.creation_date                AS hora_creacion
    FROM sell_order so
    JOIN sell_order_attempt soa
        ON soa.sell_order_id = so.id
        AND soa.current = 1
    JOIN sell_order_package sop
        ON sop.sell_order_id = so.id
    LEFT JOIN warehouse w
        ON w.id = so.assigned_warehouse_id
    LEFT JOIN shipping_method sm
        ON sm.id = so.shipping_method_id
    LEFT JOIN seller sel
        ON sel.id = so.seller_id
    WHERE so.shipping_method_id IN %(metodos_pickup)s
      AND so.sell_order_state_id NOT IN %(estados_resueltos)s
"""


def get_ordenes_pickup() -> pd.DataFrame:
    """Regresa todas las órdenes de recogida (cualquier método "Recogida...")
    que todavía no se resuelven (no recogidas, no canceladas), sin importar
    cuándo se crearon — a propósito, porque el objetivo de esta sección es
    detectar las que llevan MUCHO tiempo esperando (más de
    DIAS_LIMITE_PICKUP_SIN_RECOGER días desde su pickup_promise_max)."""

    conn = _conexion()
    try:
        df = pd.read_sql(_QUERY_PICKUP, conn, params={
            "metodos_pickup": METODOS_PICKUP_IDS,
            "estados_resueltos": ESTADOS_PICKUP_RESUELTOS,
        })
    finally:
        conn.close()

    df = df.dropna(subset=["zona_horaria"]).copy()
    # Si una de estas columnas viene completamente vacía de MySQL (ej. nadie
    # ha recogido nada todavía hoy), pandas la trae dtype "object" en vez de
    # datetime, y el accessor .dt de _localizar_por_zona truena — se fuerza
    # el tipo primero.
    for col in ("hora_creacion", "hora_limite_recogida", "hora_recogida"):
        df[col] = pd.to_datetime(df[col])
    df = _localizar_por_zona(df, ["hora_creacion", "hora_limite_recogida", "hora_recogida"])

    df["paquete_id"] = df["orden_numero"].fillna("SO").astype(str) + "-" + df["paquete_id_num"].astype(str)

    def _dias_vencidos(row):
        if pd.notna(row["hora_recogida"]) or pd.isna(row["hora_limite_recogida"]):
            return 0
        hoy_en_esa_zona = datetime.now(ZoneInfo(row["zona_horaria"])).date()
        return (hoy_en_esa_zona - row["hora_limite_recogida"].date()).days

    df["dias_vencido_pickup"] = df.apply(_dias_vencidos, axis=1)
    df["debe_cancelarse"] = df["dias_vencido_pickup"] > DIAS_LIMITE_PICKUP_SIN_RECOGER

    columnas = [
        "paquete_id", "orden_id", "orden_numero", "pais", "cedi", "metodo_envio", "seller",
        "hora_creacion", "hora_limite_recogida", "hora_recogida",
        "dias_vencido_pickup", "debe_cancelarse",
    ]
    return df[columnas]
