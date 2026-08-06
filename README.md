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
5. Crea un archivo `.env` en la raíz del proyecto (nunca se sube a git)
   con las credenciales de la base de datos:
   ```
   DB_HOST=...
   DB_PORT=3306
   DB_NAME=...
   DB_USER=...
   DB_PASS=...
   ```
6. Corre el tablero:
   ```bash
   streamlit run app.py
   ```
7. Se abrirá automáticamente en tu navegador (normalmente en `http://localhost:8501`).

## Estado actual

El tablero se conecta a la base de datos real de Melonn (MySQL) a través
de `get_shipping_data()` en `data.py`. Consulta los paquetes cuya fecha
máxima de despacho (`ship_promise_max`) es hoy, agrupa los estados reales
de la orden en Pendiente/Sorting/Estiba/Despachado, y arma la sección
"Por método de envío" dinámicamente a partir de los métodos reales que
existan (no hay una lista fija de categorías). El detalle de las
decisiones de mapeo está documentado en el docstring de `data.py`.

Sin `.env`, el tablero no puede correr — no hay modo de datos de prueba
activo actualmente.
