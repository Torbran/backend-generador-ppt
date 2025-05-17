
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import requests, tempfile, uuid, os
from pptx import Presentation

TEMPLATE_PATH = "PLANTILLA_MARCADORES_AUTOMATIZADA.pptx"

# ---------- Models ---------- #
class Camara(BaseModel):
    numero: int
    tipo: str
    ubicacion: str
    observaciones: str
    imagen_url: Optional[str] = None

class Proyecto(BaseModel):
    nombre: str
    ubicacion: str
    fecha: str
    csv: str
    mapa_url: str
    descripcion: str

class NVR(BaseModel):
    tipo: str
    direccion: str
    observaciones: Optional[str] = ""

class Carteles(BaseModel):
    barrio_protegido: int
    domiciliarios: int

class Cierre(BaseModel):
    circulo: str
    fecha_aprobacion: str

class InformeData(BaseModel):
    proyecto: Proyecto
    camaras: List[Camara]
    nvr: NVR
    carteles: Carteles
    cierre: Cierre

# ---------- Utils ---------- #
def replace_text(shape, placeholder, value):
    if shape.has_text_frame:
        if placeholder in shape.text_frame.text:
            shape.text_frame.text = shape.text_frame.text.replace(placeholder, value)

def download_image(url):
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(url)[-1])
        tmp.write(r.content)
        tmp.flush()
        return tmp.name
    except Exception as e:
        print(f"Error downloading image {url}: {e}")
        return None

# ---------- Main logic ---------- #
def generar_presentacion(data: InformeData) -> str:
    prs = Presentation(TEMPLATE_PATH)

    # --- Slide 0 y 1: encabezado y descripción ---
    for slide in prs.slides[0:2]:
        for shape in slide.shapes:
            replace_text(shape, "{{nombre_proyecto}}", data.proyecto.nombre)
            replace_text(shape, "{{ubicacion}}", data.proyecto.ubicacion)
            replace_text(shape, "{{fecha}}", data.proyecto.fecha)
            replace_text(shape, "{{nombre_csv}}", data.proyecto.csv)
            replace_text(shape, "{{calle_principal}}", data.proyecto.ubicacion)
            replace_text(shape, "{{descripcion}}", data.proyecto.descripcion)

    # --- Slide de cantidades ---
    for slide in prs.slides:
        for shape in slide.shapes:
            replace_text(shape, "{{carteles_bp}}", str(data.carteles.barrio_protegido))
            replace_text(shape, "{{carteles_dom}}", str(data.carteles.domiciliarios))
            replace_text(shape, "{{nvr_direccion}}", data.nvr.direccion)
            replace_text(shape, "{{observaciones_nvr}}", data.nvr.observaciones)

    # --- Generar slides por cámara ---
    # Buscar slide prototipo (que contiene {{detalle_camara}})
    proto = None
    for slide in prs.slides:
        for shape in slide.shapes:
            if "{{detalle_camara}}" in shape.text if shape.has_text_frame else False:
                proto = slide
                break
        if proto:
            break

    if proto:
        idx = prs.slides.index(proto)
        prs.slides.remove(proto)  # Quitamos prototipo para empezar limpio

        for cam in data.camaras:
            new_sl = prs.slides.add_slide(proto.slide_layout)
            # Copiar shapes del prototipo
            for s in proto.shapes:
                el = s.element
                new_sl.shapes._spTree.insert_element_before(el.clone(), 'p:extLst')

            # Rellenar texto
            for shape in new_sl.shapes:
                replace_text(shape, "{{detalle_camara}}", f"{cam.numero}. {cam.tipo.upper()}")
                replace_text(shape, "{{tipo_camara}}", cam.tipo)
                replace_text(shape, "{{ubicacion_camara}}", cam.ubicacion)
                replace_text(shape, "{{observaciones_camara}}", cam.observaciones)

            # TODO: insertar imagen en la mitad derecha (placeholder nombre img_camara)
            if cam.imagen_url:
                img_path = download_image(cam.imagen_url)
                if img_path:
                    # Insert as picture occupying whole white area; coordinates to tune
                    new_sl.shapes.add_picture(img_path, Inches(4), Inches(2), width=Inches(5))

    # Guardar
    out_path = f"/tmp/informe_{uuid.uuid4()}.pptx"
    prs.save(out_path)
    return out_path

# ---------- FastAPI ---------- #
app = FastAPI(title="Generador PPT Río de la Plata")

@app.post("/generar-ppt")
async def generar_ppt(data: InformeData):
    try:
        ppt_path = generar_presentacion(data)
        return FileResponse(ppt_path, filename="informe_generado.pptx")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
