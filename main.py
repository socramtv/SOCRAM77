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

# El nuevo "cerebro" que traduce los nombres de Marca a tu lista exacta de GitHub
MAPEO_CANALES = {
    "m+ vamos": ["vamos", "mvamos", "movistarvamos"],
    "m+ vamos 2": ["vamos2", "mvamos2", "movistarvamos2"],
    "m+ deportes": ["deportes", "mdeportes", "movistardeportes", "deportes1"],
    "m+ deportes 2": ["deportes2", "mdeportes2", "movistardeportes2"],
    "m+ deportes 3": ["deportes3", "mdeportes3", "movistardeportes3"],
    "movistar plus": ["movistarplus", "mplus", "plus"],
    "movistar+": ["movistarplus", "mplus", "plus"],
    "m+ liga de campeones": ["ligadecampeones", "mligadecampeones", "movistarligadecampeones", "lcampeones", "mlcampeones"],
    "m+ liga de campeones 2": ["ligadecampeones2", "mligadecampeones2", "movistarligadecampeones2", "lcampeones2", "mlcampeones2"],
    "m+ liga de campeones 3": ["ligadecampeones3", "mligadecampeones3", "movistarligadecampeones3", "lcampeones3", "mlcampeones3"],
    "m+ liga de campeones 4": ["ligadecampeones4", "mligadecampeones4", "movistarligadecampeones4", "lcampeones4", "mlcampeones4"],
    "m+ golf 2": ["golf2", "mgolf2", "movistargolf2"],
    "m+ golf": ["golf", "mgolf", "movistargolf"],
    "dazn laliga": ["daznlaliga"],
    "dazn laliga 2": ["daznlaliga2"],
    "laliga tv hypermotion": ["hypermotion", "laligatvhypermotion", "laligahypermotion"],
    "teledeporte": ["teledeporte", "tdp"],
    "teledeporte / la 2": ["teledeporte", "tdp", "la2"],
    "la 2": ["la2"],
    "tv3": ["tv3"],
    "dazn 1": ["dazn1"],
    "dazn 2": ["dazn2"],
    "dazn f1": ["daznf1"],
    "gol": ["gol", "golplay", "goltv"]
}

def limpiar_estricto(texto):
    if not texto: return ""
    n = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn').lower()
    # Limpieza absoluta de calidades y símbolos que rompen las coincidencias
    for b in ["1080p", "720p", "1080", "720", "4k", "hd", "fhd", "uhd", "*", " ", "-"]:
        n = n.replace(b, "")
    return re.sub(r'[^a-z0-9]', '', n)

def obtener_agenda_datos():
    lista_canales = []
    estado_json = "⚠️ Error leyendo tu GitHub"
    try:
        # He ajustado la URL a la ruta principal por seguridad contra errores 404
        url_json = "https://raw.githubusercontent.com/socramtv/SOCRAM77/main/hashes.json"
        resp_json = requests.get(url_json, timeout=10)
        if resp_json.status_code == 200:
            datos = resp_json.json()
            if isinstance(datos, list):
                lista_canales = [c for c in datos if isinstance(c, dict)]
                estado_json = "✅ Enlaces Acestream sincronizados"
    except Exception as e:
        print("Aviso JSON:", e)

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

            # --- CRUCE INFALIBLE CON GITHUB ---
            hash_acestream = ""
            logo_canal = ""
            
            if lista_canales:
                canal_key = canal_marca.lower().strip()
                # Consultamos el diccionario mágico
                claves_busqueda = MAPEO_CANALES.get(canal_key, [limpiar_estricto(canal_marca)])
                
                coincidencias = []
                for c in lista_canales:
                    if not isinstance(c, dict): continue
                    t_json = limpiar_estricto(c.get("title", ""))
                    tvg_json = limpiar_estricto(c.get("tvg_id", ""))
                    
                    # Coincidencia exacta
                    if t_json in claves_busqueda or tvg_json in claves_busqueda:
                        coincidencias.append(c)
                    else:
                        # Coincidencia parcial de seguridad (solo para canales raros)
                        for cb in claves_busqueda:
                            if len(cb) > 4 and (cb in t_json or cb in tvg_json):
                                coincidencias.append(c)
                
                if coincidencias:
                    mejor_opcion = coincidencias[0]
                    for op in coincidencias:
                        if "1080" in str(op.get("title", "")):
                            mejor_opcion = op
                            break
                    hash_acestream = mejor_opcion.get("hash", "")
                    logo_canal = mejor_opcion.get("logo", "")

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

    return eventos, estado_json

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
            enviar_mensaje_telegram(chat_id, "🔍 Consultando la programación y cruzando tus enlaces de Acestream...")
            
            eventos, estado_json = obtener_agenda_datos()
            if not eventos:
                enviar_mensaje_telegram(chat_id, "❌ No se pudieron extraer eventos en este momento.")
                return {"status": "ok"}

            mensaje = f"🏆 *AGENDA DEPORTIVA & ACESTREAM* 🏆\n_{estado_json}_\n\n"
            dia_actual = ""
            
            for ev in eventos[:30]:
                if ev["dia"] != dia_actual:
                    dia_actual = ev["dia"]
                    mensaje += f"\n📅 *{dia_actual}*\n" + "—" * 15 + "\n"
                
                emoji = "⚽" if "fútbol" in ev["deporte"].lower() else "🎾" if "tenis" in ev["deporte"].lower() else "🏎️" if "fórmula" in ev["deporte"].lower() else "🏅"
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
        print("Error webhook:", e)
        
    return {"status": "ok"}
