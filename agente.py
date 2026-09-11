import os
import json
import re
import time
import urllib.parse
import feedparser
from google import genai

LOG_FILE = "cronologia.md"
PROCESSED_FILE = "urls.txt"
QUERIES = ['"Mexican wolf" "Executive Order"', '"lobo mexicano" "orden ejecutiva"']
PAUSA_ENTRE_LLAMADAS = 2  # segundos, para no saturar la API de Gemini


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
    """Consulta Google News RSS para cada término de búsqueda."""
    noticias, vistas = [], set()
    for q in QUERIES:
        url = (
            "https://news.google.com/rss/search?q="
            f"{urllib.parse.quote(q)}&hl=en-US&gl=US&ceid=US:en"
        )
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            print(f"Error consultando RSS para '{q}': {e}")
            continue

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


def extraer_json(texto):
    """Extrae el bloque JSON de la respuesta del modelo, sea cual sea el formato en que venga."""
    texto = texto.strip()
    # Quita cercas de código tipo ```json ... ``` o ``` ... ```
    match = re.search(r"\{.*\}", texto, re.DOTALL)
    if match:
        texto = match.group(0)
    return json.loads(texto)


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
            model="gemini-3.5-flash-lite",
            contents=prompt
        )
        return extraer_json(res.text)
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
            md = (
                f"## [{datos.get('fecha_evento', 'Fecha no especificada')}] - "
                f"{datos.get('actor', 'Entidad')}\n"
                f"* **Postura:** `{datos.get('postura', 'N/A')}`\n"
                f"* **Detalle:** {datos.get('detalle', '')}\n"
                f"* **Cita:** *\"{datos.get('cita', 'N/A')}\"*\n"
                f"* **Fuente:** [Noticia]({n['link']})\n\n---\n\n"
            )
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(md)
            nuevas += 1

        guardar_procesada(n["link"])
        procesadas.add(n["link"])
        time.sleep(PAUSA_ENTRE_LLAMADAS)

    print(f"Proceso finalizado. Nuevas entradas registradas: {nuevas}")


if __name__ == "__main__":
    main()
