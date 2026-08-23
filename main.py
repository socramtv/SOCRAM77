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

def limpiar_extremo(texto):
    if not texto: return ""
    n = ''.join(c for c in unicodedata.normalize('NFD', str(texto)) if unicodedata.category(c) != 'Mn').lower()
    n = n.replace("movistar plus+", "mplus").replace("movistar+", "mplus")
    n = n.replace("movistar ", "mplus").replace("movistar", "mplus")
    n = n.replace("m+ ", "mplus").replace("m+", "mplus")
    
    basura = ["1080p", "1080", "720p", "720", "4k", "hd", "fhd", "uhd", "tv", " ", "-", "*", "+", "/", "|", ".", ","]
    for b in basura:
        n = n.replace(b, "")
    return re.sub(r'[^a-z0-9]', '', n)

def obtener_agenda_datos():
    lista_canales = []
    estado_json = "⚠️ Iniciando carga..."
    
    try:
        url_json = "https://raw.githubusercontent.com/socramtv/SOCRAM77/refs/heads/main/hashes.json"
        resp = requests.get(url_json, timeout=10)
        if resp.status_code == 200:
            datos = resp.json()
            if isinstance(datos, list):
                lista_canales = [c for c in datos if isinstance(c, dict)]
            elif isinstance(datos, dict):
                for k, v in datos.items():
                    if isinstance(v, list):
                        lista_canales = [c for c in v if isinstance(c, dict)]
                        break
            
            if not lista_canales:
                estado_json = "⚠️ JSON cargado pero sin canales"
            else:
                estado_json = f"✅ {len(lista_canales)} enlaces Acestream sincronizados"
        else:
            estado_json = f"⚠️ Error HTTP {resp.status_code} al bajar JSON"
    except Exception as e:
        estado_json = "⚠️ Error de conexión con JSON"
        print("Error JSON:", e)

    url_marca = "https://www.marca.com/programacion-tv.html"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        response = requests.get(url_marca, headers=headers, timeout=12)
        response.raise_for_status()
    except Exception as e:
        return [], estado_json

    soup = BeautifulSoup(response.text, 'html.parser')
    eventos = []
    
    for evento in soup.find_all('li', class_='dailyevent'):
        try:
            nodo_titulo = evento.find_previous('span', class_='title-section-widget')
            if nodo_titulo:
                dia_semana = nodo_titulo.find('strong').get_text(strip=True) if nodo_titulo.find('strong') else ""
                fecha_resto = nodo_titulo.get_text(strip=True).replace(dia_semana, "", 1).strip()
                dia_completo = f"{dia_semana} {fecha_resto}".strip()
            else:
                dia_completo = "Agenda Deportiva"

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

            if len(partido) < 3 or "resultados" in partido.lower():
                continue

            hash_acestream = ""
            
            if lista_canales:
                c_marca = limpiar_extremo(canal_marca)
                coincidencias = []
                
                for c in lista_canales:
                    if not isinstance(c, dict): continue
                    
                    c_json = limpiar_extremo(c.get("title", ""))
                    tvg_json = limpiar_extremo(c.get("tvg_id", ""))
                    
                    es_match = False
                    if c_marca == c_json or c_marca == tvg_json:
                        es_match = True
                    elif len(c_marca) >= 3 and len(c_json) >= 3 and (c_json in c_marca or c_marca in c_json):
                        es_match = True
                    elif len(c_marca) >= 3 and len(tvg_json) >= 3 and (tvg_json in c_marca or c_marca in tvg_json):
                        es_match = True
                        
                    if es_match:
                        coincidencias.append(c)
                
                if coincidencias:
                    mejor_opcion = coincidencias[0]
                    for op in coincidencias:
                        if "1080" in str(op.get("title", "")):
                            mejor_opcion = op
                            break
                    hash_acestream = mejor_opcion.get("hash", "")

            evento_obj = {
                "dia": dia_completo,
                "deporte": deporte,
                "hora": hora,
                "competicion": competicion,
                "partido": partido,
                "canal": canal_marca,
                "hash": hash_acestream
            }
            
            if evento_obj not in eventos:
                eventos.append(evento_obj)

        except Exception as e:
            continue

    return eventos, estado_json

def enviar_mensaje_telegram(chat_id, texto):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    # Volvemos a Markdown y usamos disable_web_page_preview para que no salgan previsualizaciones enormes
    requests.post(url, json={"chat_id": chat_id, "text": texto, "parse_mode": "Markdown", "disable_web_page_preview": True})

@app.get("/", response_class=HTMLResponse)
def cargar_interfaz():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Falta el archivo index.html</h1>"

@app.post("/extraer")
def extraer_programacion():
    eventos, estado = obtener_agenda_datos()
    return {"total": len(eventos), "estado_json": estado, "eventos": eventos}

@app.get("/test-scraping")
def test_scraping():
    eventos, estado = obtener_agenda_datos()
    return {"total_procesados": len(eventos), "estado_json": estado, "muestra": eventos[:5]}

@app.post("/webhook")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        message = data.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "")
        
        if text.strip() == "/agenda" and chat_id:
            enviar_mensaje_telegram(chat_id, "🔍 Consultando la programación y sincronizando tus enlaces de Acestream...")
            
            eventos, estado_json = obtener_agenda_datos()
            if not eventos:
                enviar_mensaje_telegram(chat_id, f"❌ No se pudieron extraer eventos.\nInfo: {estado_json}")
                return {"status": "ok"}

            mensaje = f"🏆 *AGENDA DEPORTIVA & ACESTREAM* 🏆\n_{estado_json}_\n\n"
            dia_actual = ""
            
            for ev in eventos[:30]:
                if ev["dia"] != dia_actual:
                    dia_actual = ev["dia"]
                    mensaje += f"\n📅 *{dia_actual}*\n" + "—" * 15 + "\n"
                
                d_low = ev["deporte"].lower()
                if "fútbol" in d_low: emoji = "⚽"
                elif "tenis" in d_low: emoji = "🎾"
                elif "fórmula" in d_low or "motor" in d_low or "motogp" in d_low: emoji = "🏎️"
                elif "baloncesto" in d_low or "basket" in d_low: emoji = "🏀"
                elif "balonmano" in d_low: emoji = "🤾"
                elif "voleibol" in d_low or "voley" in d_low: emoji = "🏐"
                elif "ciclismo" in d_low: emoji = "🚴"
                elif "vela" in d_low: emoji = "⛵"
                elif "golf" in d_low: emoji = "⛳"
                else: emoji = "🏅"

                mensaje += f"{emoji} *{ev['deporte']} - {ev['hora']}*\n"
                
                if ev["competicion"]:
                    mensaje += f"🏆 {ev['competicion']}\n"
                    
                mensaje += f"🆚 {ev['partido']}\n"
                mensaje += f"📺 {ev['canal']}\n"
                
                # ¡Aplicamos el formato URL que has pedido!
                if ev["hash"]:
                    enlace_local = f"http://127.0.0.1:6878/ace/manifest.m3u8?id={ev['hash']}"
                    mensaje += f"🔗 [Abrir en reproductor]({enlace_local})\n"
                
                mensaje += "\n"
                
                if len(mensaje) > 3500:
                    enviar_mensaje_telegram(chat_id, mensaje)
                    mensaje = ""

            if mensaje.strip():
                enviar_mensaje_telegram(chat_id, mensaje)
                
    except Exception as e:
        print("Error webhook:", e)
        
    return {"status": "ok"}
