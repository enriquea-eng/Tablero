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
                            'Marketplace', 'Pickup'
    marketplace_nombre  -> solo aplica si metodo_envio == 'Marketplace'
                            (ej. 'Amazon', 'Mercado Libre'). None si no aplica.
    seller              -> vendedor/seller de la orden (aplica sobre todo a
                            marketplace). None si no aplica.
    transportadora      -> DHL, Estafeta, FedEx, etc. None si aún no se asigna.
    ubicacion           -> 'Pendiente', 'Sorting', 'Estiba', 'Despachado'
    fecha_salida        -> fecha en que debe salir el paquete

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
                   seller, transportadora, ubicacion, fecha_salida
            FROM envios
            WHERE fecha_salida = CAST(GETDATE() AS DATE)
        '''
        df = pd.read_sql(query, conn)
        conn.close()
        return df
"""

import pandas as pd
import random
from datetime import date

METODOS = ["Mismo día", "Siguiente día", "Estándar", "Marketplace", "Pickup"]
MARKETPLACES = ["Amazon", "Mercado Libre", "Walmart", "Shein"]
SELLERS = ["Tienda Propia", "Distribuidora ABC", "Comercializadora XYZ", "Vendedor Norte"]
TRANSPORTADORAS = ["FedEx", "Estafeta", "DHL", "ampm", "imile", "J&T"]
UBICACIONES = ["Pendiente", "Sorting", "Estiba", "Despachado"]
CEDIS = ["CEDI CDMX #1", "CEDI CDMX #2"]  # <-- renombra aquí cuando tengas los nombres reales


def get_shipping_data() -> pd.DataFrame:
    """Regresa los paquetes programados para salir hoy (datos de prueba)."""
    random.seed(42)  # datos consistentes mientras diseñas el tablero

    filas = []
    for i in range(1, 251):  # 250 paquetes de ejemplo
        metodo = random.choices(
            METODOS, weights=[0.2, 0.2, 0.35, 0.15, 0.1]
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
        })

    return pd.DataFrame(filas)
