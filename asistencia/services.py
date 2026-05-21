from django.utils import timezone
from datetime import date
from ninja import Router
import asignaciones
from .validators import validar_ubicacion
from asignaciones.services import obtener_materia_vigente_para_escaneo
from configuracion.models import Configuracion
from core.constants import EstadoSolicitud, TipoClase
from .models import SolicitudEmergencia, RegistroAsistencia
from academico.models import SlotHorario


def registrar_entrada(docente_id: int, lat: float, lon: float, ip: str, tipo_clase: str):
    """
    Procesa un escaneo de ENTRADA. Valida horario y ubicación.
    """
    ahora = timezone.localtime()
    
    # 1. Obtener la clase actual del docente (Valida el margen horario)
    slot_vigente = obtener_materia_vigente_para_escaneo(
        docente_id=docente_id, 
        fecha_actual=ahora.date(), 
        hora_actual=ahora.time()
    )
    
    if not slot_vigente:
        return False, "No tienes ninguna clase programada para este horario."

    # 2. Validar que no haya fichado entrada ya
    registro_existente = RegistroAsistencia.objects.filter(
        docente_id=docente_id,
        slot_horario=slot_vigente,
        fecha=ahora.date()
    ).first()

    if registro_existente:
        return False, "Ya registraste tu entrada para esta clase hoy."

    # 3. Validar ubicación (Solo si es clase presencial)
    ubicacion_ok = None
    if tipo_clase == TipoClase.PRESENCIAL:
        config = Configuracion.objects.first() or Configuracion.objects.create(id=1)
        paso_validacion, msg_error = validar_ubicacion(lat, lon, ip, config)
        
        if not paso_validacion:
            return False, msg_error
        ubicacion_ok = True

    # 4. Registrar en la base de datos
    RegistroAsistencia.objects.create(
        docente_id=docente_id,
        slot_horario=slot_vigente,
        fecha=ahora.date(),
        anio=ahora.year,
        tipo_clase=tipo_clase,
        hora_entrada=ahora,
        ubicacion_validada=ubicacion_ok,
        latitud_registrada=lat,
        longitud_registrada=lon,
        ip_registrada=ip
    )

    return True, f"Entrada registrada exitosamente para {slot_vigente.materia.nombre}."


def registrar_salida(docente_id: int):
    """
    Procesa un escaneo de SALIDA.
    """
    ahora = timezone.localtime()
    
    # Buscamos el registro de hoy sin salida marcada
    registro_pendiente = RegistroAsistencia.objects.filter(
        docente_id=docente_id,
        fecha=ahora.date(),
        hora_salida__isnull=True
    ).order_by('-hora_entrada').first()

    if not registro_pendiente:
        return False, "No tienes ninguna entrada activa para registrar salida."

    # Actualizamos el registro con la hora de salida
    registro_pendiente.hora_salida = ahora
    registro_pendiente.save()

    return True, f"Salida registrada exitosamente para {registro_pendiente.slot_horario.materia.nombre}."


def procesar_solicitud_emergencia(docente_id: int, slot_id: int, nota: str):
    """
    Crea la alerta desde el celular del docente.
    """
    ahora = timezone.localtime()
    
    # Validamos que el slot exista si lo envió
    slot = SlotHorario.objects.filter(id=slot_id).first() if slot_id else None
    
    # Prevenimos spam: que no mande 20 alertas iguales
    if SolicitudEmergencia.objects.filter(docente_id=docente_id, fecha=ahora.date(), estado=EstadoSolicitud.PENDIENTE).exists():
        return False, "Ya tienes una solicitud pendiente de revisión para el día de hoy."

    SolicitudEmergencia.objects.create(
        docente_id=docente_id,
        slot_horario=slot,
        fecha=ahora.date(),
        nota_docente=nota,
        estado=EstadoSolicitud.PENDIENTE
    )
    return True, "Solicitud de emergencia enviada a Secretaría."

def resolver_emergencia(solicitud_id: int, aprobar: bool, nota_secretaria: str, usuario_admin):
    """
    La Secretaría aprueba o rechaza. Si aprueba, genera la asistencia perfecta automáticamente.
    """
    solicitud = SolicitudEmergencia.objects.filter(id=solicitud_id, estado=EstadoSolicitud.PENDIENTE).first()
    
    if not solicitud:
        return False, "La solicitud no existe o ya fue resuelta."

    ahora = timezone.localtime()

    if aprobar:
        solicitud.estado = EstadoSolicitud.APROBADA
        
        # --- LA GENERACIÓN MÁGICA DE ASISTENCIA ---
        # Si el profesor no sabía qué slot era, necesitamos que la Secretaría lo asigne antes (acá asumimos que ya está)
        if solicitud.slot_horario:
            RegistroAsistencia.objects.create(
                docente_id=solicitud.docente_id,
                slot_horario=solicitud.slot_horario,
                fecha=solicitud.fecha,
                anio=solicitud.fecha.year,
                tipo_clase=TipoClase.PRESENCIAL, # Asumimos presencial porque por asincrónica no hay emergencia de QR
                
                # Simulamos que entró y salió a la hora perfecta del slot
                hora_entrada=timezone.datetime.combine(solicitud.fecha, solicitud.slot_horario.hora_inicio),
                hora_salida=timezone.datetime.combine(solicitud.fecha, solicitud.slot_horario.hora_fin),
                
                ubicacion_validada=True, # Secretaría avala
                solicitud_emergencia=solicitud, # Vinculamos el registro con la emergencia para auditoría
                nota=f"Fichaje manual por emergencia (Autorizado por: {usuario_admin.get_full_name()})"
            )
    else:
        solicitud.estado = EstadoSolicitud.RECHAZADA

    # Guardamos los datos de auditoría
    solicitud.nota_secretaria = nota_secretaria
    solicitud.revisado_por = usuario_admin.secretario
    solicitud.revisado_en = ahora
    solicitud.save()

    return True, f"Solicitud {'aprobada' if aprobar else 'rechazada'} exitosamente."

def declarar_clase_asincronica(docente_id: int, slot_id: int, fecha_dictado: date, nota: str):
    """
    Registra una clase asincrónica basada en la presunción de verdad del docente.
    """
    # 1. Evitar declaraciones futuras (Opcional, según política de ICES)
    if fecha_dictado > timezone.localdate():
        return False, "No puedes declarar asistencia para fechas futuras."

    # 2. Validar que el slot exista y coincida con el día de la semana
    slot = SlotHorario.objects.filter(id=slot_id).select_related('materia').first()
    if not slot:
        return False, "El horario seleccionado no existe."

    if slot.dia_semana != fecha_dictado.weekday():
        return False, "El día de la semana seleccionado no coincide con la cursada oficial de la materia."

    # 3. Validar que el docente esté asignado a esa materia en esa fecha
    asignacion_activa = asignaciones.models.AsignacionDocente.objects.filter(
        docente_id=docente_id,
        materia_id=slot.materia_id,
        activa=True,
        fecha_inicio__lte=fecha_dictado
    ).first()

    if not asignacion_activa:
        return False, "No tienes una asignación activa para esta materia en la fecha indicada."

    # 4. Validar duplicados (Que no haya fichado presencial o asincrónico antes ese mismo día)
    if RegistroAsistencia.objects.filter(docente_id=docente_id, slot_horario_id=slot_id, fecha=fecha_dictado).exists():
        return False, "Ya existe un registro de asistencia para esta materia en la fecha indicada."

    # 5. Generar el registro directo (RN-03: Asistencia automática sin validación manual)
    RegistroAsistencia.objects.create(
        docente_id=docente_id,
        slot_horario_id=slot_id,
        fecha=fecha_dictado,
        anio=fecha_dictado.year,
        tipo_clase=TipoClase.ASINCRONICA,
        # Nulos porque no hay presencia física:
        hora_entrada=None, 
        hora_salida=None,
        ubicacion_validada=None,
        nota=f"Modalidad Asincrónica declarada vía web. Nota: {nota}"
    )

    return True, f"Clase asincrónica declarada exitosamente para {slot.materia.nombre}."