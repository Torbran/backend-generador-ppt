
# Backend FastAPI v2 - Generador PPT Río de la Plata

Este backend recibe un JSON con la estructura definida y genera una presentación 
PowerPoint basada en la plantilla `PLANTILLA_MARCADORES_AUTOMATIZADA.pptx`, 
creando tantas diapositivas como cámaras existan y rellenando los marcadores de texto.

## Ejecutar local
```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Luego visita `http://127.0.0.1:8000/docs` para probar.

## Despliegue en Render (gratuito)
1. Sube este repo a GitHub.
2. En Render, crea *New Web Service*.
3. Configura:
   - Runtime: Python 3.10+
   - Start command: `uvicorn main:app --host 0.0.0.0 --port 10000`
4. Deploy y listo.

**Nota**: Esta versión maneja inserción básica de imágenes; 
ajusta coordenadas/tamaños según tu plantilla.
