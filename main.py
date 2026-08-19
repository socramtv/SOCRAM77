from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup
import os

app = FastAPI(title="Extractor de Enlaces")

# Evita bloqueos de seguridad al consultar la API desde el navegador
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ExtractorRequest(BaseModel):
    url: str

# Esta ruta carga tu interfaz visual (el archivo index.html)
@app.get("/", response_class=HTMLResponse)
def cargar_interfaz():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Falta el archivo index.html</h1>"

# Esta ruta es la que hace el trabajo de extraer los enlaces
@app.post("/extraer")
def extraer_enlaces(request: ExtractorRequest):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(request.url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=400, detail="No se pudo acceder a la web. Verifica el enlace.")

    soup = BeautifulSoup(response.text, 'html.parser')
    enlaces = []

    for a_tag in soup.find_all('a'):
        href = a_tag.get('href')
        if href and href.startswith(('http://', 'https://')):
            titulo = a_tag.get_text(strip=True)
            enlaces.append({
                "titulo": titulo if titulo else "Enlace sin nombre",
                "url": href
            })

    return {"total": len(enlaces), "enlaces": enlaces}
