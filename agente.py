import os, json, datetime, urllib.parse, feedparser
from google import genai
from google.genai import types

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
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(url)
        for entry in feed.entries:
            link = entry.get("link", "")
            if link and link not in vistas:
                vistas.add(link)
                noticias.append({"titulo": entry.get("title", ""), "link": link, "fecha": entry.get("published", ""), "resumen": entry.get("summary", "")})
    return noticias

def analizar(client, noticia):
    prompt = f"Analiza esta noticia del Lobo Mexicano:\nTítulo: {noticia['titulo']}\nFecha: {noticia['fecha']}\nTexto: {noticia['resumen']}\nURL: {noticia['link']}\n\nResponde SOLO en JSON con esta estructura:\n{{\n  \"es_relevante\": true/false,\n  \"fecha_evento\": \"AAAA-MM-DD\",\n  \"actor\": \"Nombre de la entidad\",\n  \"postura\": \"Pro-Desclasificación / Pro-Protección Federal / Neutral\",\n  \"detalle\": \"Resumen conciso (2 frases)\",\n  \"cita\": \"Frase textual o N/A\"\n}}"
    try:
        res = client.models.generate_content(model="gemini-2.5-flash", contents=prompt, config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1))
        return json.loads(res.text)
    except:
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
