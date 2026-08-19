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
    
    items = soup.find_all(['li', 'div'], class_=re.compile('event|item|row|match|schedule', re.I))
    if not items:
        items = soup.find_all('li')

    palabras_prohibidas = ["ver más", "actualizado", "resultados", "programación deportiva", "lunes", "martes", "miércoles", "miercoles", "jueves", "viernes", "sábado", "sabado", "domingo"]

    for item in items:
        texto_completo = item.get_text(separator="|", strip=True)
        texto_lower = texto_completo.lower()

        if any(p in texto_lower for p in palabras_prohibidas):
            continue

        match_hora = re.search(r'\b\d{2}:\d{2}\b', texto_completo)
        
        if match_hora:
            hora = match_hora.group(0)
            partes = [p.strip() for p in texto_completo.split('|') if p.strip()]
            
            if len(partes) >= 3:
                deporte = partes[0] if len(partes[0]) < 15 else "Fútbol"
                partido = partes[-2] if len(partes) >= 4 else partes[1]
                canal_marca = partes[-1]
                
                if len(partido) < 3 or "resultados" in partido.lower():
                    continue

                # --- BÚSQUEDA FLEXIBLE DE HASH EN GITHUB ---
                hash_acestream = ""
                logo_canal = ""
                
                if lista_canales:
                    canal_limpio = limpiar(canal_marca)
                    
                    # 1. Búsqueda exacta o contenida en tu JSON
                    for c in lista_canales:
                        if not isinstance(c, dict): continue
                        t_json = limpiar(c.get("title", ""))
                        tvg_json = limpiar(c.get("tvg_id", ""))
                        
                        if canal_limpio in t_json or canal_limpio in tvg_json or t_json in canal_limpio:
                            hash_acestream = c.get("hash", "")
                            logo_canal = c.get("logo", "")
                            # Si encuentra una versión en 1080p, prioriza esa
                            if "1080" in c.get("title", ""):
                                break

                evento_obj = {
                    "dia": "Próximos Partidos",
                    "deporte": deporte,
                    "hora": hora,
                    "competicion": "",
                    "partido": partido,
                    "canal": canal_marca,
                    "hash": hash_acestream,
                    "logo": logo_canal
                }
                
                if evento_obj not in eventos:
                    eventos.append(evento_obj)

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
                enviar_mensaje_telegram(chat_id, "❌ No se pudieron extraer eventos.")
                return {"status": "ok"}

            mensaje = "🏆 *AGENDA DEPORTIVA & ACESTREAM* 🏆\n\n"
            for ev in eventos[:15]:
                emoji = "⚽" if "fútbol" in ev["deporte"].lower() else "🎾" if "tenis" in ev["deporte"].lower() else "🏅"
                mensaje += f"{emoji} *{ev['deporte']} - {ev['hora']}*\n"
                mensaje += f"🆚 {ev['partido']}\n"
                mensaje += f"📺 {ev['canal']}\n"
                if ev["hash"]:
                    mensaje += f"🔗 `acestream://{ev['hash']}`\n"
                mensaje += "\n"

            enviar_mensaje_telegram(chat_id, mensaje)
                
    except Exception as e:
        print("Error webhook:", e)
        
    return {"status": "ok"}
