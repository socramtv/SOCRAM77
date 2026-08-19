from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from bs4 import BeautifulSoup
import cloudscraper
import os

app = FastAPI(title="Extractor de Enlaces")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ExtractorRequest(BaseModel):
    url: str

@app.get("/", response_class=HTMLResponse)
def cargar_interfaz():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Falta el archivo index.html</h1>"

@app.post("/extraer")
def extraer_enlaces(request: ExtractorRequest):
    try:
        # Usamos cloudscraper en lugar de requests normal para burlar protecciones antibot
        scraper = cloudscraper.create_scraper(browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        })
        
        response = scraper.get(request.url, timeout=15)
        response.raise_for_status()
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Bloqueo o error al acceder: {str(e)}")

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
