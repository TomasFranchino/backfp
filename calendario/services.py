from datetime import date
from .models import EventoCalendario

def is_fecha_bloqueada(fecha_consulta: date) -> bool:
    """
    Verifica si una fecha específica tiene un evento en el calendario 
    (feriado, asueto, mesa de examen global).
    Retorna True si la fecha está bloqueada (no se exige asistencia).
    """
    return EventoCalendario.objects.filter(fecha=fecha_consulta).exists()