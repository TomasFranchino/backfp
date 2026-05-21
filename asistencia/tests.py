from django.test import TestCase
from django.utils import timezone
from datetime import date, time, timedelta
from usuarios.models import Usuario, Docente
from academico.models import Materia, SlotHorario
from asignaciones.models import AsignacionDocente
from calendario.models import EventoCalendario
from asistencia.models import RegistroAsistencia, SolicitudEmergencia
from core.constants import TipoClase, EstadoSolicitud
from unittest.mock import patch

class MisMateriasStatsTests(TestCase):
    def setUp(self):
        # 1. Crear usuario y docente
        self.user = Usuario.objects.create_user(username="profesor1", password="password123")
        self.docente = Docente.objects.create(user=self.user, activo=True)
        
        # 2. Crear materia
        self.materia = Materia.objects.create(codigo_siu="MAT101", nombre="Matematica I", anio=2026)
        
        # 3. Crear slot horario (Lunes de 18:00 a 20:00)
        self.slot = SlotHorario.objects.create(
            materia=self.materia,
            dia_semana=0,
            hora_inicio=time(18, 0),
            hora_fin=time(20, 0)
        )
        
    def test_stats_calculo(self):
        # Caso 1: Sin registros de asistencia.
        # La asignación empezó el Lunes 11 de Mayo de 2026.
        # Hoy es Viernes 22 de Mayo de 2026.
        # Lunes en este rango: 11/05 y 18/05. Ambos deben ser faltas (Ausente).
        fecha_inicio = date(2026, 5, 11)
        asig = AsignacionDocente.objects.create(
            docente=self.docente,
            materia=self.materia,
            rol="titular",
            activa=True,
            fecha_inicio=fecha_inicio
        )
        
        self.client.force_login(self.user)
        
        with patch('django.utils.timezone.localdate', return_value=date(2026, 5, 22)), \
             patch('django.utils.timezone.localtime') as mock_localtime:
            mock_localtime.return_value = timezone.make_aware(timezone.datetime(2026, 5, 22, 12, 0, 0))
            
            response = self.client.get('/api/asistencia/mis_materias_stats')
            self.assertEqual(response.status_code, 200)
            data = response.json()
            
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]['materia_nombre'], "Matematica I")
            self.assertEqual(data[0]['asistencias'], 0)
            self.assertEqual(data[0]['asincronicas'], 0)
            self.assertEqual(data[0]['faltas'], 2)
            self.assertEqual(len(data[0]['historial']), 2)
            
            # Verificar orden descendente
            self.assertEqual(data[0]['historial'][0]['fecha'], "2026-05-18")
            self.assertEqual(data[0]['historial'][0]['estado'], "Ausente")
            self.assertEqual(data[0]['historial'][1]['fecha'], "2026-05-11")
            self.assertEqual(data[0]['historial'][1]['estado'], "Ausente")
            
        # Caso 2: Con 1 asistencia registrada (11/05) y 1 asincrónica declarada (18/05)
        RegistroAsistencia.objects.create(
            docente=self.docente,
            slot_horario=self.slot,
            fecha=date(2026, 5, 11),
            anio=2026,
            tipo_clase=TipoClase.PRESENCIAL,
            hora_entrada=timezone.make_aware(timezone.datetime(2026, 5, 11, 18, 5)),
            hora_salida=timezone.make_aware(timezone.datetime(2026, 5, 11, 20, 0)),
            ubicacion_validada=True
        )
        
        RegistroAsistencia.objects.create(
            docente=self.docente,
            slot_horario=self.slot,
            fecha=date(2026, 5, 18),
            anio=2026,
            tipo_clase=TipoClase.ASINCRONICA,
            hora_entrada=None,
            hora_salida=None,
            nota="Clase virtual dada por campus"
        )
        
        with patch('django.utils.timezone.localdate', return_value=date(2026, 5, 22)), \
             patch('django.utils.timezone.localtime') as mock_localtime:
            mock_localtime.return_value = timezone.make_aware(timezone.datetime(2026, 5, 22, 12, 0, 0))
            
            response = self.client.get('/api/asistencia/mis_materias_stats')
            self.assertEqual(response.status_code, 200)
            data = response.json()
            
            self.assertEqual(data[0]['asistencias'], 1)
            self.assertEqual(data[0]['asincronicas'], 1)
            self.assertEqual(data[0]['faltas'], 0)
            
            self.assertEqual(data[0]['historial'][0]['fecha'], "2026-05-18")
            self.assertEqual(data[0]['historial'][0]['estado'], "Presente (Asíncrona)")
            self.assertEqual(data[0]['historial'][1]['fecha'], "2026-05-11")
            self.assertEqual(data[0]['historial'][1]['estado'], "Presente")

        # Caso 3: Verificar que los feriados/días bloqueados se excluyan del cálculo
        RegistroAsistencia.objects.all().delete()
        EventoCalendario.objects.create(fecha=date(2026, 5, 18), descripcion="Feriado Nacional")
        
        with patch('django.utils.timezone.localdate', return_value=date(2026, 5, 22)), \
             patch('django.utils.timezone.localtime') as mock_localtime:
            mock_localtime.return_value = timezone.make_aware(timezone.datetime(2026, 5, 22, 12, 0, 0))
            
            response = self.client.get('/api/asistencia/mis_materias_stats')
            self.assertEqual(response.status_code, 200)
            data = response.json()
            
            # 18/05 es feriado, queda el 11/05 como falta.
            self.assertEqual(data[0]['asistencias'], 0)
            self.assertEqual(data[0]['faltas'], 1)
            self.assertEqual(len(data[0]['historial']), 1)
            self.assertEqual(data[0]['historial'][0]['fecha'], "2026-05-11")
            self.assertEqual(data[0]['historial'][0]['estado'], "Ausente")

