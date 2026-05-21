from datetime import date, time, datetime, timedelta
from django.db.models import Q
from .models import AsignacionDocente
from academico.models import SlotHorario

def obtener_materia_vigente_para_escaneo(docente_id: int, fecha_actual: date, hora_actual: time):
    """
    Busca qué clase le toca dar al docente en este momento exacto.
    Retorna el objeto SlotHorario si encuentra una coincidencia, sino None.
    """
    # 1. ¿Qué día de la semana es hoy? (0 = Lunes, 6 = Domingo)
    dia_semana_actual = fecha_actual.weekday()
    
    # 2. Buscar materias asignadas activas para este docente en la fecha actual
    asignaciones_activas = AsignacionDocente.objects.filter(
        docente_id=docente_id,
        activa=True,
        fecha_inicio__lte=fecha_actual
    ).filter(
        Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=fecha_actual)
    )
    
    # Extraemos los IDs de las materias que dicta
    materias_ids = asignaciones_activas.values_list('materia_id', flat=True)
    
    if not materias_ids:
        return None # No dicta nada hoy (o ya no está activo)

    # 3. Buscar los slots horarios de esas materias para el día de hoy
    slots_del_dia = SlotHorario.objects.filter(
        materia_id__in=materias_ids,
        dia_semana=dia_semana_actual
    )
    
    # 4. Encontrar el slot que coincida con la hora actual (con tolerancia)
    # Convertimos hora_actual a un objeto datetime dummy para poder sumar/restar minutos
    dummy_date = datetime.today()
    dt_actual = datetime.combine(dummy_date, hora_actual)
    
    MARGEN_MINUTOS = 60 # Aceptamos escaneos 60 min antes o 60 min después
    
    for slot in slots_del_dia:
        dt_inicio = datetime.combine(dummy_date, slot.hora_inicio)
        dt_fin = datetime.combine(dummy_date, slot.hora_fin)
        
        # Ampliamos la ventana permitida con el margen
        ventana_inicio = dt_inicio - timedelta(minutes=MARGEN_MINUTOS)
        ventana_fin = dt_fin + timedelta(minutes=MARGEN_MINUTOS)
        
        # Si la hora del escaneo cae dentro de esta ventana, ¡encontramos la clase!
        if ventana_inicio <= dt_actual <= ventana_fin:
            return slot
            
    return None