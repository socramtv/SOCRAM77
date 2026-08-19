from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import requests
from bs4 import BeautifulSoup
import os

app = FastAPI(title="Extractor de TV Marca")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
def cargar_interfaz():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Falta el archivo index.html</h1>"

@app.post("/extraer")
def extraer_programacion():
    url = "https://www.marca.com/programacion-tv.html"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=400, detail="Error al acceder a Marca.")

    soup = BeautifulSoup(response.text, 'html.parser')
    eventos = []

    # 1. Buscamos el contenedor principal exacto que aloja los días
    lista_dias = soup.find('ol', class_='daylist')
    
    if not lista_dias:
        return {"total": 0, "eventos": []}

    # 2. Iteramos solo por los bloques de los días (<li class="content-item">)
    for bloque_dia in lista_dias.find_all('li', class_='content-item', recursive=False):
        
        # Extraemos el título del día (Ej: Miércoles 19 de Agosto de 2026)
        nodo_titulo = bloque_dia.find('span', class_='title-section-widget')
        if not nodo_titulo:
            continue
            
        dia_semana = nodo_titulo.find('strong').get_text(strip=True) if nodo_titulo.find('strong') else ""
        fecha_resto = nodo_titulo.get_text(strip=True).replace(dia_semana, "", 1).strip()
        dia_completo = f"{dia_semana} {fecha_resto}"

        # 3. Iteramos exactamente por cada evento de ese día (<li class="dailyevent">)
        for evento in bloque_dia.find_all('li', class_='dailyevent'):
            try:
                # Vamos directamente a por la clase exacta de cada dato
                deporte = evento.find('span', class_='dailyday').get_text(strip=True)
                hora = evento.find('strong', class_='dailyhour').get_text(strip=True)
                competicion = evento.find('span', class_='dailycompetition').get_text(strip=True)
                partido = evento.find('h4', class_='dailyteams').get_text(strip=True)
                canal = evento.find('span', class_='dailychannel').get_text(strip=True)

                eventos.append({
                    "dia": dia_completo,
                    "deporte": deporte,
                    "hora": hora,
                    "competicion": competicion,
                    "partido": partido,
                    "canal": canal
                })
            except AttributeError:
                # Si a Marca se le olvida poner la hora o el canal en un evento raro, 
                # lo ignoramos silenciosamente para que la app no se cuelgue
                continue

    return {"total": len(eventos), "eventos": eventos}
