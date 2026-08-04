# Tablero de Envíos

Tablero para saber cuántos paquetes hay que sacar hoy, por método de envío
y por transportadora.

## Cómo correrlo (con VS Code)

1. Abre esta carpeta en VS Code (`File → Open Folder...`).
2. Abre una terminal dentro de VS Code (`Ctrl + ñ` o `Terminal → New Terminal`).
3. Crea un entorno virtual (opcional pero recomendado):
   ```bash
   python -m venv venv
   venv\Scripts\activate   # en Windows
   source venv/bin/activate  # en Mac/Linux
   ```
4. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```
5. Corre el tablero:
   ```bash
   streamlit run app.py
   ```
6. Se abrirá automáticamente en tu navegador (normalmente en `http://localhost:8501`).

## Estado actual

Ahora mismo el tablero usa **datos de prueba** generados en `data.py`
(función `get_shipping_data()`), para que puedas diseñar y ajustar el
tablero sin depender todavía del acceso a la base de datos real.

## Cuándo tengas los datos de tu base de datos

Solo necesitas modificar `data.py`. No toques `app.py`: mientras la función
`get_shipping_data()` siga regresando un DataFrame con las mismas columnas
(`paquete_id`, `metodo_envio`, `transportadora`, `fecha_salida`, `estado`),
el resto del tablero sigue funcionando igual.

Dependiendo del motor de base de datos que uses, instalarás una librería
distinta:

| Motor          | Librería               |
|----------------|-------------------------|
| SQL Server     | `pyodbc`                |
| MySQL/MariaDB  | `mysql-connector-python`|
| PostgreSQL     | `psycopg2`               |

Dentro de `data.py` ya dejé un ejemplo comentado de cómo se vería la
conexión con SQL Server, como referencia.
