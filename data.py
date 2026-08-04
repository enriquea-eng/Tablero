"""
Módulo de acceso a datos.

Por ahora get_shipping_data() regresa datos de prueba (mock).
Cuando tengas los datos de conexión de tu base de datos, esta es la
ÚNICA función que necesitas modificar. El resto del tablero (app.py)
no cambia, porque siempre espera un DataFrame con estas columnas:

    paquete_id          -> identificador único del paquete
    pais                -> país del CEDI (ej. 'México')
    cedi                -> bodega/almacén (ej. 'CEDI CDMX #1')
    metodo_envio        -> 'Mismo día', 'Siguiente día', 'Estándar',
                            'Marketplace', 'Pickup', 'B2B Estándar',
                            'B2B Envío agendado'
    marketplace_nombre  -> solo aplica si metodo_envio == 'Marketplace'
                            (ej. 'Amazon', 'Mercado Libre'). None si no aplica.
    seller              -> vendedor/seller de la orden (aplica sobre todo a
                            marketplace). None si no aplica.
    transportadora      -> DHL, Estafeta, FedEx, etc. None si aún no se asigna.
    ubicacion           -> 'Pendiente', 'Sorting', 'Estiba', 'Despachado'
    fecha_salida        -> fecha en que debe salir el paquete
    hora_creacion       -> fecha y hora en que se creó/recibió la orden
    hora_limite         -> fecha y hora límite en que el paquete debe salir,
                            según su método de envío (SLA)
    hora_despacho       -> fecha y hora en que el paquete fue despachado.
                            None si todavía no se ha despachado.

IMPORTANTE: los filtros de País, Cedi, Seller y Marketplace en app.py se
arman automáticamente a partir de los valores ÚNICOS que existan en estas
columnas (df["cedi"].unique(), etc). Esto significa que cuando conectes tu
base de datos real, NO tienes que tocar los filtros ni el resto de app.py:
en cuanto aparezca un CEDI, seller o marketplace nuevo en tus datos, el
filtro correspondiente lo va a mostrar automáticamente.

Cuando conectes tu base de datos real, reemplaza el cuerpo de esta
función por algo como:

    import pyodbc  # o mysql-connector-python, psycopg2, etc.

    def get_shipping_data():
        conn = pyodbc.connect(
            "DRIVER={ODBC Driver 17 for SQL Server};"
            "SERVER=tu_servidor;"
            "DATABASE=tu_base;"
            "UID=tu_usuario;"
            "PWD=tu_password;"
        )
        query = '''
            SELECT paquete_id, pais, cedi, metodo_envio, marketplace_nombre,
                   seller, transportadora, ubicacion, fecha_salida,
                   hora_creacion, hora_limite, hora_despacho
            FROM envios
            WHERE fecha_salida = CAST(GETDATE() AS DATE)
        '''
        df = pd.read_sql(query, conn)
        conn.close()
        return df
"""

import pandas as pd
import random
from datetime import date, datetime, time, timedelta

METODOS = [
    "Mismo día", "Siguiente día", "Estándar", "Marketplace", "Pickup",
    "B2B Estándar", "B2B Envío agendado",
]
MARKETPLACES = ["Amazon", "Mercado Libre", "Walmart", "Shein"]
SELLERS = ["Tienda Propia", "Distribuidora ABC", "Comercializadora XYZ", "Vendedor Norte"]
TRANSPORTADORAS = ["FedEx", "Estafeta", "DHL", "ampm", "imile", "J&T"]
UBICACIONES = ["Pendiente", "Sorting", "Estiba", "Despachado"]
CEDIS = ["CEDI CDMX #1", "CEDI CDMX #2"]  # <-- renombra aquí cuando tengas los nombres reales

# Hora límite (SLA) por método de envío. Ajusta a los cortes reales de tu operación.
HORA_LIMITE_METODO = {
    "Mismo día": time(14, 0),
    "Marketplace": time(16, 0),
    "Siguiente día": time(18, 0),
    "B2B Envío agendado": time(17, 0),
    "Pickup": time(19, 0),
    "Estándar": time(20, 0),
    "B2B Estándar": time(21, 0),
}


def get_shipping_data() -> pd.DataFrame:
    """Regresa los paquetes programados para salir hoy (datos de prueba)."""

    filas = []
    for i in range(1, 251):  # 250 paquetes de ejemplo
        metodo = random.choices(
            METODOS, weights=[0.18, 0.18, 0.28, 0.13, 0.08, 0.09, 0.06]
        )[0]

        marketplace_nombre = random.choice(MARKETPLACES) if metodo == "Marketplace" else None
        seller = random.choice(SELLERS) if metodo == "Marketplace" else None

        ubicacion = random.choices(
            UBICACIONES, weights=[0.15, 0.15, 0.15, 0.55]
        )[0]

        if ubicacion in ("Pendiente", "Estiba"):
            transportadora = random.choice([None, None, *TRANSPORTADORAS])
        else:
            transportadora = random.choice(TRANSPORTADORAS)

        # --- Hora de creación: cuándo entró la orden al sistema (00:00-23:59) ---
        hora_creacion = datetime.combine(
            date.today(), time(random.randint(0, 23), random.randint(0, 59))
        )

        # --- Hora límite: cuándo debe salir según su método de envío (SLA) ---
        hora_limite = datetime.combine(date.today(), HORA_LIMITE_METODO[metodo])

        # --- Hora de despacho: solo si ya se despachó. A veces cae después de
        # la hora límite a propósito, para simular órdenes despachadas tarde. ---
        hora_despacho = None
        if ubicacion == "Despachado":
            hora_despacho = hora_creacion + timedelta(minutes=random.randint(20, 600))
            tope_dia = datetime.combine(date.today(), time(23, 59))
            if hora_despacho > tope_dia:
                hora_despacho = tope_dia

        filas.append({
            "paquete_id": f"PKG-{i:04d}",
            "pais": "México",
            "cedi": random.choice(CEDIS),
            "metodo_envio": metodo,
            "marketplace_nombre": marketplace_nombre,
            "seller": seller,
            "transportadora": transportadora,
            "ubicacion": ubicacion,
            "fecha_salida": date.today(),
            "hora_creacion": hora_creacion,
            "hora_limite": hora_limite,
            "hora_despacho": hora_despacho,
        })

    return pd.DataFrame(filas)
