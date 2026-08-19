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

# Token configurado automáticamente
TELEGRAM_TOKEN = "8899732413:AAE7wHYoHYhvePxlxuKCzndeVRdqkOTaCFo"

def simplificar_nombre(texto):
    if not texto: return ""
    n = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn').lower()
    n = n.replace("movistar plus+", "mplus").replace("movistar plus", "mplus").replace("movistar+", "mplus").replace("m+", "mplus").replace("movistar", "mplus")
    for b in ["1080p", "720p", "1080", "720", "4k", "hd", "fhd", "uhd"]:
        n = n.replace(b, "")
    n = re.sub(r'[^a-z0-9]', '', n)
    return n

def obtener_agenda_datos():
    lista_canales = []
    try:
        url_json = "https://raw.githubusercontent.com/socramtv/SOCRAM77/refs/heads/main/hashes.json"
        resp_json = requests.get(url_json, timeout=8)
        if resp_json.status_code == 200:
            lista_canales = resp_json.json()
    except Exception as e:
        print("Aviso: No se pudo cargar el JSON:", e)

    url_marca = "https://www.marca.com/programacion-tv.html"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        response = requests.get(url_marca, headers=headers, timeout=12)
        response.raise_for_status()
    except Exception as e:
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    eventos = []
    
    bloques_dia = soup.find_all('li', class_='content-item')
    
    for bloque_dia in bloques_dia:
        nodo_titulo = bloque_dia.find('span', class_='title-section-widget')
        dia_completo = nodo_titulo.get_text(strip=True) if nodo_titulo else "Programación"

        for evento in bloque_dia.find_all('li', class_='dailyevent'):
            try:
                deporte = evento.find('span', class_='dailyday').get_text(strip=True)
                hora = evento.find('strong', class_='dailyhour').get_text(strip=True)
                competicion = evento.find('span', class_='dailycompetition').get_text(strip=True)
                partido = evento.find('h4', class_='dailyteams').get_text(strip=True)
                canal_marca = evento.find('span', class_='dailychannel').get_text(strip=True)

                canal_limpio = simplificar_nombre(canal_marca)
                hash_acestream = ""
                
                if canal_limpio and lista_canales:
                    for c in lista_canales:
                        titulo_json = simplificar_nombre(c.get("title", ""))
                        tvgid_json = simplificar_nombre(c.get("tvg_id", ""))
                        if canal_limpio == titulo_json or canal_limpio == tvgid_json or (len(canal_limpio) > 3 and (canal_limpio in titulo_json or canal_limpio in tvgid_json)):
                            hash_acestream = c.get("hash", "")
                            if "1080" in c.get("title", ""): break

                eventos.append({
                    "dia": dia_completo,
                    "deporte": deporte,
                    "hora": hora,
                    "competicion": competicion,
                    "partido": partido,
                    "canal": canal_marca,
                    "hash": hash_acestream
                })
            except AttributeError:
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


@app.get("/test-scraping")
def test_scraping():
    # Comprobamos si Marca responde
    url_marca = "https://www.marca.com/programacion-tv.html"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        r = requests.get(url_marca, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        eventos_raw = soup.find_all('li', class_='dailyevent')
        return {
            "estado_marca": r.status_code,
            "eventos_encontrados_en_bruto": len(eventos_raw)
        }
    except Exception as e:
        return {"error": str(e)}



@app.post("/extraer")
def extraer_programacion():
    eventos = obtener_agenda_datos()
    return {"total": len(eventos), "eventos": eventos}

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
            
            for ev in eventos:
                if ev["dia"] != dia_actual:
                    dia_actual = ev["dia"]
                    mensaje += f"\n📅 *{dia_actual}*\n" + "—" * 15 + "\n"
                
                emoji = "⚽" if "fútbol" in ev["deporte"].lower() else "🎾" if "tenis" in ev["deporte"].lower() else "🏅"
                mensaje += f"{emoji} *{ev['deporte']} - {ev['hora']}*\n"
                if ev["competicion"]:
                    mensaje += f"🏆 {ev['competicion']}\n"
                mensaje += f"🆚 {ev['partido']}\n"
                mensaje += f"📺 {ev['canal']}\n"
                
                if ev["hash"]:
                    mensaje += f"🔗 `acestream://{ev['hash']}`\n"
                mensaje += "\n"
                
                if len(mensaje) > 3500:
                    enviar_mensaje_telegram(chat_id, mensaje)
                    mensaje = ""

            if mensaje.strip():
                enviar_mensaje_telegram(chat_id, mensaje)
                
    except Exception as e:
        print("Error procesando mensaje de Telegram:", e)
        
    return {"status": "ok"}
