import sys
# === PRIMER MENSAJE DE DEBUG ===
print("DEBUG: === Inicio del script main.py ===", file=sys.stderr)

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import requests, tempfile, uuid, os
from pptx import Presentation # Potencial punto de fallo si la librería tiene problemas de entorno
import traceback
from pptx.util import Inches # Potencial punto de fallo

# === DEBUG después de importaciones ===
print("DEBUG: === Todas las importaciones completadas ===", file=sys.stderr)

# Obtener la ruta del directorio donde se encuentra este script (main.py)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_FILENAME = "PLANTILLA_MARCADORES_AUTOMATIZADA.pptx"
# Construir la ruta completa al archivo de plantilla usando la ruta base
TEMPLATE_PATH = os.path.join(BASE_DIR, TEMPLATE_FILENAME)

# === DEBUG después de definir ruta de plantilla ===
print(f"DEBUG: === Ruta de plantilla construida: {TEMPLATE_PATH} ===", file=sys.stderr)


# ---------- Models ---------- #
# Define la estructura de los datos que esperas recibir
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

# === DEBUG después de definir modelos ===
print("DEBUG: === Modelos Pydantic definidos ===", file=sys.stderr)


# ---------- Utils ---------- #
# Función para reemplazar texto en las formas de la presentación
def replace_text(shape, placeholder, value):
    if shape.has_text_frame:
        if placeholder in shape.text_frame.text:
            shape.text_frame.text = shape.text_frame.text.replace(placeholder, str(value))

# Función para descargar una imagen desde una URL a un archivo temporal
def download_image(url):
    try:
        print(f"DEBUG: Intentando descargar imagen desde URL: {url}", file=sys.stderr)
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(url)[-1], dir='/tmp')
        tmp.write(r.content)
        tmp.close()
        print(f"DEBUG: Imagen descargada exitosamente a temporal: {tmp.name}", file=sys.stderr)
        return tmp.name
    except requests.exceptions.RequestException as req_e:
        print(f"ERROR: Error de red o HTTP al descargar imagen desde {url}: {req_e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return None
    except Exception as e:
        print(f"ERROR: Error inesperado al descargar imagen desde {url}: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return None

# === DEBUG después de definir funciones de utilidad ===
print("DEBUG: === Funciones de utilidad definidas ===", file=sys.stderr)


# ---------- Main logic ---------- #
# Función principal para generar la presentación
def generar_presentacion(data: InformeData) -> str:
    print(f"DEBUG: Verificando si el archivo de plantilla existe en la ruta: {TEMPLATE_PATH}", file=sys.stderr)
    if not os.path.exists(TEMPLATE_PATH):
        print(f"ERROR: Archivo de plantilla NO encontrado en la ruta esperada: {TEMPLATE_PATH}", file=sys.stderr)
        raise FileNotFoundError(f"El archivo de plantilla '{TEMPLATE_FILENAME}' no se encontró en la ruta del servidor: {TEMPLATE_PATH}")

    try:
        print(f"DEBUG: Archivo de plantilla encontrado. Procediendo a cargar la presentación desde {TEMPLATE_PATH}", file=sys.stderr)
        prs = Presentation(TEMPLATE_PATH)
        print(f"DEBUG: Plantilla cargada exitosamente.", file=sys.stderr)


        # --- Procesar Slides Iniciales (0 y 1) ---
        print("DEBUG: Rellenando campos en slides iniciales (0 y 1)...", file=sys.stderr)
        for slide in prs.slides[0:2]:
            for shape in slide.shapes:
                replace_text(shape, "{{nombre_proyecto}}", data.proyecto.nombre)
                replace_text(shape, "{{ubicacion}}", data.proyecto.ubicacion)
                replace_text(shape, "{{fecha}}", data.proyecto.fecha)
                replace_text(shape, "{{nombre_csv}}", data.proyecto.csv)
                replace_text(shape, "{{calle_principal}}", data.proyecto.ubicacion)
                replace_text(shape, "{{descripcion}}", data.proyecto.descripcion)
        print("DEBUG: Campos de slides iniciales rellenados.", file=sys.stderr)

        # --- Procesar Slides de Cantidades/NVR ---
        print("DEBUG: Rellenando campos de cantidades/NVR en todos los slides...", file=sys.stderr)
        for slide in prs.slides:
             for shape in slide.shapes:
                replace_text(shape, "{{carteles_bp}}", str(data.carteles.barrio_protegido))
                replace_text(shape, "{{carteles_dom}}", str(data.carteles.domiciliarios))
                replace_text(shape, "{{nvr_tipo}}", data.nvr.tipo)
                replace_text(shape, "{{nvr_direccion}}", data.nvr.direccion)
                replace_text(shape, "{{observaciones_nvr}}", data.nvr.observaciones)
        print("DEBUG: Campos de cantidades/NVR rellenados.", file=sys.stderr)


        # --- Generar slides para cada Cámara ---
        proto = None
        proto_idx = -1
        print("DEBUG: Buscando slide prototipo con '{{detalle_camara}}' para clonar...", file=sys.stderr)
        for i, slide in enumerate(prs.slides):
            for shape in slide.shapes:
                if shape.has_text_frame:
                    if "{{detalle_camara}}" in shape.text:
                        proto = slide
                        proto_idx = i
                        print(f"DEBUG: Prototipo encontrado en slide con índice: {proto_idx}", file=sys.stderr)
                        break
            if proto:
                break

        if proto:
            prs.slides.remove(proto)
            print(f"DEBUG: Slide prototipo (índice {proto_idx}) removido de la presentación.", file=sys.stderr)

            print(f"DEBUG: Procesando datos de {len(data.camaras)} cámara(s) para generar slides...", file=sys.stderr)
            for i, cam in enumerate(data.camaras):
                print(f"DEBUG: ---> Procesando Cámara {i+1}/{len(data.camaras)} (Número: {cam.numero})...", file=sys.stderr)

                new_sl = prs.slides.add_slide(proto.slide_layout)
                print(f"DEBUG: Slide nuevo creado con el layout del prototipo.", file=sys.stderr)

                try:
                     print(f"DEBUG: Copiando formas del prototipo al nuevo slide para cámara {cam.numero}...", file=sys.stderr)
                     for s in proto.shapes:
                        el = s.element
                        new_sl.shapes._spTree.insert_element_before(el.clone(), 'p:extLst')
                     print(f"DEBUG: Formas del prototipo copiadas exitosamente.", file=sys.stderr)
                except Exception as copy_e:
                     print(f"ERROR: Error crítico al copiar formas del prototipo para cámara {cam.numero}: {copy_e}", file=sys.stderr)
                     traceback.print_exc(file=sys.stderr)


                print(f"DEBUG: Rellenando texto en el nuevo slide para cámara {cam.numero}...", file=sys.stderr)
                for shape in new_sl.shapes:
                    replace_text(shape, "{{detalle_camara}}", f"{cam.numero}. {cam.tipo.upper()}")
                    replace_text(shape, "{{tipo_camara}}", cam.tipo)
                    replace_text(shape, "{{ubicacion_camara}}", cam.ubicacion)
                    replace_text(shape, "{{observaciones_camara}}", cam.observaciones)
                print(f"DEBUG: Texto rellenado para cámara {cam.numero}.", file=sys.stderr)


                print(f"DEBUG: Procesando imagen para cámara {cam.numero}. URL proporcionada: {cam.imagen_url}", file=sys.stderr)
                if cam.imagen_url:
                    img_path = download_image(cam.imagen_url)
                    if img_path:
                        try:
                            print(f"DEBUG: Intentando insertar imagen desde {img_path} en slide de cámara {cam.numero}...", file=sys.stderr)
                            left = Inches(4)
                            top = Inches(2)
                            width = Inches(5)

                            new_sl.shapes.add_picture(img_path, left, top, width=width)
                            print(f"DEBUG: Imagen insertada exitosamente en slide de cámara {cam.numero}.", file=sys.stderr)

                            try:
                                os.remove(img_path)
                                print(f"DEBUG: Archivo temporal de imagen eliminado: {img_path}", file=sys.stderr)
                            except Exception as rm_e:
                                print(f"WARNING: No se pudo eliminar archivo temporal {img_path} después de insertarlo: {rm_e}", file=sys.stderr)
                        except Exception as img_e:
                            print(f"ERROR: Error al insertar imagen {img_path} en el slide de cámara {cam.numero}: {img_e}", file=sys.stderr)
                            traceback.print_exc(file=sys.stderr)
                    else:
                        print(f"WARNING: No se pudo descargar la imagen desde {cam.imagen_url}. No se insertará imagen en slide {cam.numero}.", file=sys.stderr)
                else:
                    print(f"DEBUG: No hay URL de imagen proporcionada para cámara {cam.numero}. Saltando inserción de imagen.", file=sys.stderr)

        else:
            print("WARNING: No se encontró ningún slide prototipo con '{{detalle_camara}}'. No se generarán slides individuales para cámaras.", file=sys.stderr)


        # TODO: Lógica para insertar Mapa si aplica
        # print("DEBUG: Procesando mapa (si aplica)...", file=sys.stderr)
        # ... (tu lógica para el mapa) ...


        # TODO: Lógica para procesar el slide de Cierre si aplica
        # print("DEBUG: Rellenando campos del slide de cierre (si aplica)...", file=sys.stderr)
        # ... (tu lógica para el cierre) ...


        print("DEBUG: Lógica de generación de presentación completada. Procediendo a guardar el archivo final...", file=sys.stderr)

        out_filename = f"informe_generado_{uuid.uuid4().hex[:8]}.pptx"
        out_path = os.path.join("/tmp", out_filename)
        try:
            print(f"DEBUG: Intentando guardar presentación final en: {out_path}", file=sys.stderr)
            prs.save(out_path)
            print(f"DEBUG: Presentación guardada exitosamente en: {out_path}", file=sys.stderr)
            return out_path
        except Exception as save_e:
            print(f"ERROR: Error crítico al guardar el archivo de presentación en {out_path}: {save_e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            raise save_e

    except FileNotFoundError as fnf_e:
         print(f"ERROR: FileNotFoundError capturado en generar_presentacion: {fnf_e}", file=sys.stderr)
         raise fnf_e

    except Exception as e:
        print(f"ERROR: Excepción inesperada durante la generación de la presentación: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        raise e


# === DEBUG antes de inicializar FastAPI ===
print("DEBUG: === A punto de inicializar la aplicación FastAPI ===", file=sys.stderr)
# ---------- FastAPI ---------- #
app = FastAPI(title="Generador PPT Río de la Plata", description="API para generar presentaciones PowerPoint de forma automatizada a partir de datos JSON.")
# === DEBUG después de inicializar FastAPI ===
print("DEBUG: === Aplicación FastAPI inicializada ===", file=sys.stderr)


# Define el endpoint HTTP POST para generar la presentación
# === DEBUG antes de definir el endpoint ===
print("DEBUG: === A punto de definir el endpoint /generar-ppt ===", file=sys.stderr)
@app.post("/generar-ppt")
async def generar_ppt(data: InformeData):
    print("\n" + "="*50, file=sys.stderr)
    print("DEBUG: Recibida petición POST en el endpoint /generar-ppt", file=sys.stderr)
    # Puedes descomentar la siguiente línea si quieres ver los datos JSON recibidos (puede ser verborrágico)
    # print("DEBUG: Datos recibidos:", data.model_dump_json(indent=2), file=sys.stderr)

    try:
        print("DEBUG: Llamando a generar_presentacion...", file=sys.stderr)
        ppt_path = generar_presentacion(data)
        print("DEBUG: generar_presentacion finalizada.", file=sys.stderr)


        print(f"DEBUG: Presentación generada exitosamente. Devolviendo archivo desde {ppt_path}", file=sys.stderr)

        return FileResponse(path=ppt_path, filename="informe_generado.pptx", media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation")

    except FileNotFoundError as fnf_e:
         print(f"ERROR en el endpoint /generar-ppt: Archivo de plantilla no encontrado: {fnf_e}", file=sys.stderr)
         raise HTTPException(
             status_code=500,
             detail=f"Error del servidor al generar el PPT: Archivo de plantilla no encontrado en Render. Verifique que '{TEMPLATE_FILENAME}' esté en la raíz del repositorio. Detalle: {fnf_e}"
         )

    except Exception as e:
        print(f"ERROR en el endpoint /generar-ppt: Excepción inesperada: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr) # Imprimir rastreo en el log del endpoint también por si acaso
        raise HTTPException(
            status_code=500,
            detail=f"Error interno del servidor al generar el PPT. Consulte los logs de Render para más detalles sobre la excepción: {e}"
        )
    finally:
        print(f"DEBUG: Petición a /generar-ppt finalizada.", file=sys.stderr)
        print("="*50 + "\n", file=sys.stderr)


# === DEBUG después de definir el endpoint ===
print("DEBUG: === Endpoint /generar-ppt definido ===", file=sys.stderr)


# Opcional: Añadir un endpoint raíz simple para verificar que el servicio responde algo en /
# Puedes descomentar esto si quieres que la URL principal '/' no dé 404
# @app.get("/")
# def read_root():
#     print("DEBUG: Recibida petición GET en el endpoint /", file=sys.stderr)
#     return {"message": "API Generador PPT funcionando. Vea /docs para la documentación interactiva."}


# === DEBUG al final del script ===
print("DEBUG: === Fin del script main.py (definiciones completadas) ===", file=sys.stderr)
# @app.get("/")
# def read_root():
#     return {"message": "API Generador PPT funcionando. Vea /docs para la documentación interactiva."}
