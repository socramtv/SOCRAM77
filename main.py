from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import requests
from bs4 import BeautifulSoup
import unicodedata
import re
import os

app = FastAPI(title="Agenda TV & Bot de Telegram")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TELEGRAM_TOKEN = "8899732413:AAE7wHYoHYhvePxlxuKCzndeVRdqkOTaCFo"

# Diccionario ampliado con los canales de tu captura
MAPEO_CANALES = {
    "m+ vamos": "vamos",
    "m+ vamos 2": "vamos",
    "m+ deportes": "deportes",
    "movistar plus": "movistar plus",
    "movistar+": "movistar plus",
    "m+ liga de campeones": "ligadecampeones",
    "m+ liga de campeones 2": "ligadecampeones2",
    "m+ liga de campeones 3": "ligadecampeones3",
    "m+ liga de campeones 4": "ligadecampeones4",
    "dazn laliga": "daznlaliga",
    "laliga tv hypermotion": "hypermotion",
    "teledeporte": "teledeporte",
    "teledeporte / la 2": "teledeporte",
    "la 2": "la2",
    "m+ golf 2": "golf",
    "tv3": "tv3",
    "dazn 1": "dazn1",
    "dazn 2": "dazn2",
    "dazn f1": "daznf1",
    "gol": "gol"
}

def limpiar(texto):
    if not texto: return ""
    n = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn').lower()
    for b in ["1080p", "720p", "1080", "720", "4k", "hd", "fhd", "uhd", "*"]:
        n = n.replace(b, "")
    return re.sub(r'[^a-z0-9]', '', n)

def obtener_agenda_datos():
    lista_canales = []
    try:
        url_json = "https://raw.githubusercontent.com/socramtv/SOCRAM77/refs/heads/main/hashes.json"
        resp_json = requests.get(url_json, timeout=8)
        if resp_json.status_code == 200:
            datos = resp_json.json()
            if isinstance(datos, list):
                lista_canales = [c for c in datos if isinstance(c, dict)]
    except Exception as e:
        print("Aviso JSON:", e)

    url_marca = "https://www.marca.com/programacion-tv.html"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        response = requests.get(url_marca, headers=headers, timeout=12)
        response.raise_for_status()
    except Exception as e:
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    eventos = []
    
    # Vamos directos a cazar la clase exacta de los eventos
    for evento in soup.find_all('li', class_='dailyevent'):
        try:
            # 1. Recuperamos el día mirando hacia atrás en el HTML
            nodo_titulo = evento.find_previous('span', class_='title-section-widget')
            if nodo_titulo:
                dia_semana = nodo_titulo.find('strong').get_text(strip=True) if nodo_titulo.find('strong') else ""
                fecha_resto = nodo_titulo.get_text(strip=True).replace(dia_semana, "", 1).strip()
                dia_completo = f"{dia_semana} {fecha_resto}".strip()
            else:
                dia_completo = "Agenda Deportiva"

            # 2. Recuperamos TODOS los datos, incluyendo la competición
            deporte_tag = evento.find(class_='dailyday')
            deporte = deporte_tag.get_text(strip=True) if deporte_tag else "Deporte"

            hora_tag = evento.find(class_='dailyhour')
            hora = hora_tag.get_text(strip=True) if hora_tag else "00:00"

            comp_tag = evento.find(class_='dailycompetition')
            competicion = comp_tag.get_text(strip=True) if comp_tag else ""

            partido_tag = evento.find(class_='dailyteams')
            partido = partido_tag.get_text(strip=True) if partido_tag else "Evento deportivo"

            canal_tag = evento.find(class_='dailychannel')
            canal_marca = canal_tag.get_text(strip=True) if canal_tag else "TV"

            # Filtro antibasura
            if len(partido) < 3 or "resultados" in partido.lower():
                continue

            # 3. Cruce Inteligente con tus enlaces de GitHub
            hash_acestream = ""
            logo_canal = ""
            
            if lista_canales:
                canal_key = canal_marca.lower().strip()
                clave_busqueda = MAPEO_CANALES.get(canal_key, limpiar(canal_marca))
                
                for c in lista_canales:
                    if not isinstance(c, dict): continue
                    t_json = limpiar(c.get("title", ""))
                    tvg_json = limpiar(c.get("tvg_id", ""))
                    
                    if clave_busqueda and (clave_busqueda in t_json or clave_busqueda in tvg_json or t_json in clave_busqueda):
                        hash_acestream = c.get("hash", "")
                        logo_canal = c.get("logo", "")
                        # Priorizamos el 1080p
                        if "1080" in c.get("title", ""):
                            break

            evento_obj = {
                "dia": dia_completo,
                "deporte": deporte,
                "hora": hora,
                "competicion": competicion,
                "partido": partido,
                "canal": canal_marca,
                "hash": hash_acestream,
                "logo": logo_canal
            }
            
            if evento_obj not in eventos:
                eventos.append(evento_obj)

        except Exception as e:
            continue

    return eventos

def enviar_mensaje_telegram(chat_id, texto):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": texto, "parse_mode": "Markdown"})

@app.get("/", response_class=HTMLResponse)
def cargar_interfaz():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Falta el archivo index.html</h1>"

@app.post("/extraer")
def extraer_programacion():
    eventos = obtener_agenda_datos()
    return {"total": len(eventos), "eventos": eventos}

@app.get("/test-scraping")
def test_scraping():
    eventos = obtener_agenda_datos()
    return {"total_procesados": len(eventos), "muestra": eventos[:3]}

@app.post("/webhook")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        message = data.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "")
        
        if text.strip() == "/agenda" and chat_id:
            enviar_mensaje_telegram(chat_id, "🔍 Consultando la programación y cruzando tus enlaces de Acestream...")
            
            eventos = obtener_agenda_datos()
            if not eventos:
                enviar_mensaje_telegram(chat_id, "❌ No se pudieron extraer eventos en este momento.")
                return {"status": "ok"}

            mensaje = "🏆 *AGENDA DEPORTIVA & ACESTREAM* 🏆\n\n"
            dia_actual = ""
            
            # Mostramos un máximo de 30 eventos para no saturar el bot
            for ev in eventos[:30]:
                if ev["dia"] != dia_actual:
                    dia_actual = ev["dia"]
                    mensaje += f"\n📅 *{dia_actual}*\n" + "—" * 15 + "\n"
                
                emoji = "⚽" if "fútbol" in ev["deporte"].lower() else "🎾" if "tenis" in ev["deporte"].lower() else "🏅"
                mensaje += f"{emoji} *{ev['deporte']} - {ev['hora']}*\n"
                
                # ¡Aquí recuperamos la competición para que salga en Telegram!
                if ev["competicion"]:
                    mensaje += f"🏆 {ev['competicion']}\n"
                    
                mensaje += f"🆚 {ev['partido']}\n"
                mensaje += f"📺 {ev['canal']}\n"
                
                if ev["hash"]:
                    mensaje += f"🔗 `acestream://{ev['hash']}`\n"
                mensaje += "\n"
                
                # Si el mensaje es muy largo, lo cortamos y lo enviamos en varias partes
                if len(mensaje) > 3500:
                    enviar_mensaje_telegram(chat_id, mensaje)
                    mensaje = ""

            if mensaje.strip():
                enviar_mensaje_telegram(chat_id, mensaje)
                
    except Exception as e:
        print("Error webhook:", e)
        
    return {"status": "ok"}
