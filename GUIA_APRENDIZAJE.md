# Guía de Construcción y Funcionamiento: Agente Monitoreador del Lobo Mexicano

Este documento contiene la explicación técnica y la estructura del agente automatizado para el seguimiento de noticias sobre el *Canis lupus baileyi*.

---

## 1. Arquitectura General del Agente

El sistema opera bajo un flujo automatizado de tres fases:

1. **Extracción (Scraper RSS):** Consulta las fuentes RSS públicas de Google News mediante términos de búsqueda clave relacionados con la Orden Ejecutiva y la Ley de Especies en Peligro de Extinción (ESA).
2. **Procesamiento e Inteligencia (LLM Gemini):** Envía los fragmentos extraídos a la API de Gemini (`gemini-2.5-flash`) mediante una instrucción (*prompt*) estructurada para determinar la relevancia, identificar la entidad/actor, clasificar la postura y extraer la cita clave.
3. **Persistencia (GitHub Actions):** Registra los eventos nuevos en el archivo `cronologia.md` y actualiza la lista de enlaces procesados en `urls.txt` mediante commits automáticos.

---

## 2. Código del Agente (`agente.py`)

```python
import os, json, datetime, urllib.parse, feedparser
from google import genai

LOG_FILE = "cronologia.md"
PROCESSED_FILE = "urls.txt"
QUERIES = ['"Mexican wolf" "Executive Order"', '"lobo mexicano" "orden ejecutiva"']

def cargar_procesadas():
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def guardar_procesada(url):
    with open(PROCESSED_FILE, "a", encoding="utf-8") as f:
        f.write(f"{url}\n")

def inicializar_log():
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write("# Cronología de Posturas: Lobo Mexicano\n\n---\n\n")

def obtener_noticias():
    noticias, vistas = [], set()
    for q in QUERIES:
        url = f"[https://news.google.com/rss/search?q=](https://news.google.com/rss/search?q=){urllib.parse.quote(q)}&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(url)
        for entry in feed.entries:
            link = entry.get("link", "")
            if link and link not in vistas:
                vistas.add(link)
                noticias.append({
                    "titulo": entry.get("title", ""),
                    "link": link,
                    "fecha": entry.get("published", ""),
                    "resumen": entry.get("summary", "")
                })
    return noticias

def analizar(client, noticia):
    prompt = f"""Analiza esta noticia sobre el Lobo Mexicano:
Título: {noticia['titulo']}
Fecha: {noticia['fecha']}
Texto: {noticia['resumen']}
URL: {noticia['link']}

Responde SOLO en formato JSON válido con estas claves:
{{
  "es_relevante": true,
  "fecha_evento": "AAAA-MM-DD",
  "actor": "Nombre de la entidad",
  "postura": "Pro-Desclasificación / Pro-Protección Federal / Neutral",
  "detalle": "Resumen conciso de 2 oraciones",
  "cita": "Frase relevante o N/A"
}}"""
    try:
        res = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        texto = res.text.strip()
        if texto.startswith("```json"):
            texto = texto[7:]
        if texto.startswith("```"):
            texto = texto[3:]
        if texto.endswith("```"):
            texto = texto[:-3]
        return json.loads(texto.strip())
    except Exception as e:
        print(f"Error analizando {noticia['link']}: {e}")
        return None

def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: No se encontró la clave GEMINI_API_KEY")
        return
    client = genai.Client(api_key=api_key)
    procesadas = cargar_procesadas()
    inicializar_log()
    
    print("Iniciando rastreo de noticias...")
    noticias = obtener_noticias()
    print(f"Se encontraron {len(noticias)} noticias en Google News.")

    nuevas = 0
    for n in noticias:
        if n["link"] in procesadas:
            continue
        print(f"Analizando: {n['titulo'][:50]}...")
        datos = analizar(client, n)
        if datos and datos.get("es_relevante"):
            md = f"## [{datos.get('fecha_evento', 'Fecha no especificada')}] - {datos.get('actor', 'Entidad')}\n* **Postura:** `{datos.get('postura', 'N/A')}`\n* **Detalle:** {datos.get('detalle', '')}\n* **Cita:** *\"{datos.get('cita', 'N/A')}\"*\n* **Fuente:** [Noticia]({n['link']})\n\n---\n\n"
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(md)
            nuevas += 1
        guardar_procesada(n["link"])
        procesadas.add(n["link"])

    print(f"Proceso finalizado. Nuevas entradas registradas: {nuevas}")

if __name__ == "__main__":
    main()
fin

3. Configuración del Automatizador (.github/workflows/automatizacion.yml)
name: Agente Lobo Mexicano

on:
  schedule:
    - cron: '0 12 * * *'
  workflow_dispatch:

jobs:
  ejecutar:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - run: pip install feedparser google-genai

      - run: python agente.py
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}

      - name: Guardar cambios
        uses: stefanzweifel/git-auto-commit-action@v5
        with:
          commit_message: "Actualización de cronología"
          file_pattern: "cronologia.md urls.txt"
Fin
4. Conceptos Clave para Aprender
feedparser: Biblioteca en Python encargada de leer fuentes RSS e interpretar etiquetas XML/Atom de noticias sin necesidad de hacer web scraping directo sobre la interfaz gráfica.
google-genai: SDK oficial para interactuar con los modelos Gemini de Google.
secrets.GEMINI_API_KEY: Mecanismo de seguridad de GitHub para inyectar claves privadas dentro del entorno de ejecución virtual sin exponer el texto plano en el código.
git-auto-commit-action: Acción reutilizable que verifica las diferencias (diff) en el sistema de archivos local de la máquina virtual y realiza el commit/push automático hacia la rama principal si detecta modificaciones.

5. Ve al final de la pantalla y presiona **Commit changes...**.

---

### Paso 2: Lectura cómoda desde tu teléfono

Una vez guardado:
* Puedes leer el documento perfectamente formateado entrando a tu repositorio desde el navegador de tu celular o instalando la aplicación oficial de **GitHub** disponible en la Play Store.
* Cuando quieras repasar cómo funciona la llamada a la API, la estructura del prompt o el manejo de archivos en Python, solo abres `GUIA_APRENDIZAJE.md` y tendrás todo el material de estudio organizado y respaldado en la nube.
