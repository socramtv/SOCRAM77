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
        # Petición estándar, Marca no nos bloqueará
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=400, detail="Error al acceder a Marca.")

    soup = BeautifulSoup(response.text, 'html.parser')
    eventos = []

    # Buscamos elementos que contengan la programación (listas o contenedores)
    # Marca suele estructurarlo en listas (<li>) con la hora, el deporte y el canal
    patron_hora = re.compile(r'\b\d{2}:\d{2}\b') 
    
    for item in soup.find_all(['li', 'div']):
        texto = item.get_text(separator=" | ", strip=True)
        
        # Si el texto contiene una hora (ej. 21:00) y tiene cierta longitud, es un evento
        if patron_hora.search(texto) and 10 < len(texto) < 150:
            # Evitamos duplicados
            if not any(e['titulo'] == texto for e in eventos):
                eventos.append({
                    "titulo": texto,
                    "url": "Info extraída de Marca TV"
                })

    return {"total": len(eventos), "enlaces": eventos}
