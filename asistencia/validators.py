import math
from core.constants import MetodoValidacion


def calcular_distancia_metros(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcula la distancia en metros entre dos coordenadas usando Haversine."""
    R = 6371000 # Radio de la Tierra en metros
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2.0) ** 2
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def validar_ubicacion(lat_docente: float, lon_docente: float, ip_registrada: str, config) -> tuple[bool, str]:
    """
    Evalúa la ubicación del docente contra las reglas configuradas en el sistema.
    Retorna (True, "Mensaje de éxito") o (False, "Motivo del rechazo").
    """
    metodo = config.metodo_validacion_ubicacion
    
    # 1. Chequeo por WiFi (usamos la IP pública o rango de red interna)
    # Nota: Acá asumimos que config.red_wifi_campus guarda la IP estática de salida de ICES
    en_wifi_institucional = (ip_registrada == config.red_wifi_campus) if config.red_wifi_campus else False

    # 2. Chequeo por GPS (coordenadas y radio desde configuración global)
    en_radio_gps = False
    if lat_docente and lon_docente:
        lat_campus = float(config.latitud_campus)
        lon_campus = float(config.longitud_campus)
        radio_metros = int(config.radio_gps_metros)
        distancia = calcular_distancia_metros(lat_campus, lon_campus, lat_docente, lon_docente)
        en_radio_gps = distancia <= radio_metros

    # 3. Aplicar la regla de negocio estricta
    if metodo == MetodoValidacion.SOLO_WIFI:
        if not en_wifi_institucional:
            return False, "Debes estar conectado a la red WiFi de la institución."
            
    elif metodo == MetodoValidacion.SOLO_GPS:
        if not en_radio_gps:
            return False, "Estás fuera del radio geográfico permitido por la institución."
            
    elif metodo == MetodoValidacion.GPS_O_WIFI:
        if not en_wifi_institucional and not en_radio_gps:
            return False, "Debes estar en el campus (Conectado al WiFi o dentro del radio GPS)."

    return True, "Ubicación validada correctamente."