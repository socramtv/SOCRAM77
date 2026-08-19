from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import requests
from bs4 import BeautifulSoup
import unicodedata
import re
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
    if not texto: return ""
    n = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn').lower()
    n = n.replace("movistar plus+", "mplus").replace("movistar plus", "mplus").replace("movistar+", "mplus").replace("m+", "mplus").replace("movistar", "mplus")
    for b in ["1080p", "720p", "1080", "720", "4k", "hd", "fhd", "uhd"]:
        n = n.replace(b, "")
    n = re.sub(r'[^a-z0-9]', '', n)
    return n

@app.get("/", response_class=HTMLResponse)
def cargar_interfaz():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Falta el archivo index.html</h1>"

@app.post("/extraer")
def extraer_programacion():
    # 1. Intentamos descargar tu lista de GitHub de forma segura
    lista_canales = []
    try:
        url_json = "https://raw.githubusercontent.com/socramtv/SOCRAM77/refs/heads/main/hashes.json"
        resp_json = requests.get(url_json, timeout=8)
        if resp_json.status_code == 200:
            lista_canales = resp_json.json()
    except Exception as e:
        print("Aviso: No se pudo cargar el JSON:", e)

    # 2. Descargamos la web de Marca
    url_marca = "https://www.marca.com/programacion-tv.html"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        response = requests.get(url_marca, headers=headers, timeout=12)
        response.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al acceder a Marca: {str(e)}")

    soup = BeautifulSoup(response.text, 'html.parser')
    eventos = []
    
    # 3. Método inteligente: Buscamos todos los bloques de días disponibles
    bloques_dia = soup.find_all('li', class_='content-item')
    
    if bloques_dia:
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

                    # Cruce de canales con GitHub
                    canal_limpio = simplificar_nombre(canal_marca)
                    hash_acestream, logo_canal = "", ""
                    
                    if canal_limpio and lista_canales:
                        for c in lista_canales:
                            titulo_json = simplificar_nombre(c.get("title", ""))
                            tvgid_json = simplificar_nombre(c.get("tvg_id", ""))
                            if canal_limpio == titulo_json or canal_limpio == tvgid_json or (len(canal_limpio) > 3 and (canal_limpio in titulo_json or canal_limpio in tvgid_json)):
                                hash_acestream = c.get("hash", "")
                                logo_canal = c.get("logo", "")
                                if "1080" in c.get("title", ""): break

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
    
    # 4. Plan de emergencia: Si por lo que sea los bloques de días fallan, cazamos todos los eventos sueltos de la web
    if not eventos:
        for evento in soup.find_all('li', class_='dailyevent'):
            try:
                deporte = evento.find('span', class_='dailyday').get_text(strip=True)
                hora = evento.find('strong', class_='dailyhour').get_text(strip=True)
                competicion = evento.find('span', class_='dailycompetition').get_text(strip=True)
                partido = evento.find('h4', class_='dailyteams').get_text(strip=True)
                canal_marca = evento.find('span', class_='dailychannel').get_text(strip=True)

                eventos.append({
                    "dia": "Próximos Eventos",
                    "deporte": deporte,
                    "hora": hora,
                    "competicion": competicion,
                    "partido": partido,
                    "canal": canal_marca,
                    "hash": "",
                    "logo": ""
                })
            except:
                continue

    return {"total": len(eventos), "eventos": eventos}
