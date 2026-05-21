from ninja import Router, File
from ninja.files import UploadedFile
from core.security import secretario_auth
from .schemas import ResumenImportacionOut
from .services import procesar_archivo_siu

router = Router(tags=["Importación SIU"], auth=secretario_auth)

@router.post("/siu", response={200: ResumenImportacionOut, 400: dict})
def subir_archivo_siu(request, file: UploadedFile = File(...)):
    """
    Recibe un archivo Excel (.xlsx) exportado del SIU y lo procesa para poblar la base de datos
    con Materias, Docentes y Asignaciones de forma masiva.
    """
    # Validar que sea un archivo Excel
    if not file.name.endswith(('.xlsx', '.xls')):
        return 400, {"success": False, "mensaje": "El archivo debe ser un Excel (.xlsx o .xls)"}

    # Procesar el archivo pasándole el objeto en memoria y el usuario logueado
    try:
        resultados = procesar_archivo_siu(file.file, request.user)
        return 200, resultados
    except Exception as e:
        return 400, {"success": False, "mensaje": f"Error crítico al leer el archivo: {str(e)}"}