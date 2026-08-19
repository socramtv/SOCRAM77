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
    
    dia_actual = "Hoy"
    dias_semana = ['lunes', 'martes', 'miércoles', 'miercoles', 'jueves', 'viernes', 'sábado', 'sabado', 'domingo']

    for item in soup.find_all(['li', 'h2', 'div']):
        texto_crudo = item.get_text(separator="|", strip=True)
        texto_crudo = re.sub(r'\|+', '|', texto_crudo)
        partes = [p.strip() for p in texto_crudo.split('|') if p.strip()]

        if not partes: continue

        # Buscar exactamente la posición de la hora (formato HH:MM)
        indice_hora = -1
        for i, p in enumerate(partes):
            if re.match(r'^\d{2}:\d{2}$', p):
                indice_hora = i
                break
        
        # 1. Si no hay hora, comprobamos si es un separador de día puro
        if indice_hora == -1:
            texto_junto = " ".join(partes).lower()
            if any(d in texto_junto for d in dias_semana) and len(partes) <= 2 and "programación" not in texto_junto:
                dia_actual = partes[0].replace('-', '').strip().capitalize()
            continue

        # 2. Si hay hora, procesamos y extraemos el evento real
        if indice_hora > 0:
            deporte = partes[indice_hora - 1]
            hora = partes[indice_hora]
            
            # Si hay texto antes del deporte, Marca ha colado la fecha en la misma línea
            if indice_hora >= 2:
                posible_dia = partes[0].replace('-', '').strip().capitalize()
                if any(d in posible_dia.lower() for d in dias_semana):
                    dia_actual = posible_dia
            
            resto = partes[indice_hora + 1:]
            
            if len(resto) >= 3:
                competicion = resto[0]
                partido = resto[1]
                canal = resto[-1]
            elif len(resto) == 2:
                competicion = ""
                partido = resto[0]
                canal = resto[1]
            elif len(resto) == 1:
                competicion = ""
                partido = resto[0]
                canal = ""
            else:
                continue # Faltan datos críticos, lo ignoramos

            evento_obj = {
                "dia": dia_actual,
                "deporte": deporte,
                "hora": hora,
                "competicion": competicion,
                "partido": partido,
                "canal": canal
            }
            
            if evento_obj not in eventos:
                eventos.append(evento_obj)

    return {"total": len(eventos), "eventos": eventos}
