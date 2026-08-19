from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import requests
from bs4 import BeautifulSoup
import re
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
    patron_hora = re.compile(r'\b\d{2}:\d{2}\b') 
    
    textos_vistos = set()

    # Buscamos las etiquetas <li> que es donde Marca guarda cada fila
    for item in soup.find_all('li'):
        texto_crudo = item.get_text(separator="|", strip=True)
        texto_crudo = re.sub(r'\|+', '|', texto_crudo) # Limpia barras dobles
        partes = [p.strip() for p in texto_crudo.split('|') if p.strip()]
        
        # Filtro: Un evento real tiene al menos 4 partes. Si tiene menos (ej. "Fútbol | 00:00"), lo ignoramos.
        if patron_hora.search(texto_crudo) and len(partes) >= 4:
            if texto_crudo not in textos_vistos:
                textos_vistos.add(texto_crudo)
                
                deporte = partes[0]
                hora = partes[1]
                
                # Asignamos las partes según la estructura de Marca
                if len(partes) >= 5:
                    competicion = partes[2]
                    partido = partes[3]
                    canal = partes[-1]
                else:
                    competicion = ""
                    partido = partes[2]
                    canal = partes[-1]

                eventos.append({
                    "deporte": deporte,
                    "hora": hora,
                    "competicion": competicion,
                    "partido": partido,
                    "canal": canal
                })

    return {"total": len(eventos), "eventos": eventos}
