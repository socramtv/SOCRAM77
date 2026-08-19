from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import requests
from bs4 import BeautifulSoup
import unicodedata
import os

app = FastAPI(title="Extractor de TV y Acestream")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def simplificar_nombre(texto):
    """Limpia los nombres para poder comparar Marca con el JSON de GitHub"""
    if not texto: return ""
    # Quita acentos y pasa a minúsculas
    n = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn').lower()
    # Estandariza formatos
    n = n.replace("m+", "movistar").replace("hd", "").replace("1080p", "").replace("720p", "").replace("*", "")
    return n.strip()

@app.get("/", response_class=HTMLResponse)
def cargar_interfaz():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Falta el archivo index.html</h1>"

@app.post("/extraer")
def extraer_programacion():
    # 1. Descargamos tu lista de canales de GitHub
    url_json = "https://raw.githubusercontent.com/socramtv/SOCRAM77/main/hashes.json"
    try:
        resp_json = requests.get(url_json, timeout=5)
        lista_canales = resp_json.json()
    except:
        lista_canales = [] # Si falla GitHub, continuamos sin hashes

    # 2. Descargamos la web de Marca
    url_marca = "https://www.marca.com/programacion-tv.html"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        response = requests.get(url_marca, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException:
        raise HTTPException(status_code=400, detail="Error al acceder a Marca.")

    soup = BeautifulSoup(response.text, 'html.parser')
    eventos = []
    
    lista_dias = soup.find('ol', class_='daylist')
    if not lista_dias: return {"total": 0, "eventos": []}

    for bloque_dia in lista_dias.find_all('li', class_='content-item', recursive=False):
        nodo_titulo = bloque_dia.find('span', class_='title-section-widget')
        if not nodo_titulo: continue
            
        dia_semana = nodo_titulo.find('strong').get_text(strip=True) if nodo_titulo.find('strong') else ""
        fecha_resto = nodo_titulo.get_text(strip=True).replace(dia_semana, "", 1).strip()
        dia_completo = f"{dia_semana} {fecha_resto}"

        for evento in bloque_dia.find_all('li', class_='dailyevent'):
            try:
                deporte = evento.find('span', class_='dailyday').get_text(strip=True)
                hora = evento.find('strong', class_='dailyhour').get_text(strip=True)
                competicion = evento.find('span', class_='dailycompetition').get_text(strip=True)
                partido = evento.find('h4', class_='dailyteams').get_text(strip=True)
                canal_marca = evento.find('span', class_='dailychannel').get_text(strip=True)

                # --- LÓGICA DE CRUCE CON GITHUB ---
                canal_limpio = simplificar_nombre(canal_marca)
                coincidencias = []
                
                for c in lista_canales:
                    titulo_json = simplificar_nombre(c.get("title", ""))
                    tvgid_json = simplificar_nombre(c.get("tvg_id", ""))
                    
                    if canal_limpio and (canal_limpio in titulo_json or canal_limpio in tvgid_json or titulo_json in canal_limpio):
                        coincidencias.append(c)

                hash_acestream = ""
                logo_canal = ""

                if coincidencias:
                    # Buscamos la mejor calidad posible (priorizamos 1080p)
                    mejor_opcion = coincidencias[0]
                    for op in coincidencias:
                        if "1080" in op.get("title", ""):
                            mejor_opcion = op
                            break
                        elif "720" in op.get("title", "") and "1080" not in mejor_opcion.get("title", ""):
                            mejor_opcion = op
                    
                    hash_acestream = mejor_opcion.get("hash", "")
                    logo_canal = mejor_opcion.get("logo", "")

                eventos.append({
                    "dia": dia_completo,
                    "deporte": deporte,
                    "hora": hora,
                    "competicion": competicion,
                    "partido": partido,
                    "canal": canal_marca,
                    "hash": hash_acestream,
                    "logo": logo_canal
                })
            except AttributeError:
                continue

    return {"total": len(eventos), "eventos": eventos}
