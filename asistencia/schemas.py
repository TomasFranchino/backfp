from ninja import Schema
from typing import Optional
from datetime import date
class FichajeEntradaIn(Schema):
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    tipo_clase: str = 'presencial' # Puede enviar 'asincronica' o 'virtual_sincronica'

class FichajeOut(Schema):
    success: bool
    mensaje: str

class EstadoFichajeOut(Schema):
    tiene_entrada_activa: bool
    materia_actual: Optional[str] = None
    hora_entrada: Optional[str] = None

# --- EMERGENCIAS ---

class SolicitudEmergenciaIn(Schema):
    slot_horario_id: Optional[int] = None
    nota_docente: str

class SolicitudEmergenciaOut(Schema):
    id: int
    docente_nombre: str
    materia_nombre: str
    fecha: date
    estado: str
    nota_docente: str

class ResolverEmergenciaIn(Schema):
    aprobar: bool
    nota_secretaria: str

class ClaseDisponibleOut(Schema):
    slot_id: int
    materia_nombre: str
    hora_inicio: str
    hora_fin: str

class DeclaracionAsincronicaIn(Schema):
    slot_horario_id: int
    fecha_dictado: date  # El docente elige el día (generalmente "hoy")
    nota: str = ""       # Ej: "Dejé el TP en el campus virtual"

class HistorialClaseOut(Schema):
    fecha: str
    tipo: str
    estado: str
    detalle: str

class MateriaStatsOut(Schema):
    materia_id: int
    materia_nombre: str
    materia_anio: int
    dias_cursada: list[str]
    asistencias: int
    asincronicas: int
    faltas: int
    historial: list[HistorialClaseOut]