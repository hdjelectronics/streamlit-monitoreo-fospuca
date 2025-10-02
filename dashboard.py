# --- IMPORTACIONES ---
import streamlit as st
import requests
import json
import pandas as pd
import time
import numpy as np
from typing import List, Dict, Any
import base64
import os
from datetime import datetime, timedelta, timezone


# --- CONFIGURACIÓN DE ZONA HORARIA Y LÓGICA DE TIEMPO ---

# Definir la zona horaria de Venezuela (VET = UTC-4)
VENEZUELA_TZ = timezone(timedelta(hours=-4))
# Formato de fecha y hora requerido para parsear 'LastReportTime': 'Sep 30 2025 12:57PM'
TIME_FORMAT = '%b %d %Y %I:%M%p'
COLOR_FALLA_GPS = "#AAAAAA" # Gris para Falla GPS

# --- 🔒 CONSTANTE DE CONTRASEÑA 🔒 ---
CONFIG_PASSWORD = "admin" # <-- ¡CÁMBIALA AQUÍ!
# -------------------------------------

# --- 🚨 NUEVAS CONSTANTES DE COLOR PARA UBICACIONES DINÁMICAS 🚨 ---
PROXIMIDAD_KM = 0.1 # Distancia de la sede (PARA ASUMIR EN SEDE/VERTEDERO)

COLOR_RESGUARDO_SECUNDARIO = "#191452" 
COLOR_VERTEDERO = "#FCC6BB" # ¡COLOR ACTUALIZADO SEGÚN SOLICITUD!
# ----------------------------------------------------------------------


def obtener_hora_venezuela() -> datetime:
    """Retorna el objeto datetime con la hora actual en la Zona Horaria de Venezuela (VET)."""
    return datetime.now(VENEZUELA_TZ)

# 🚨 FUNCIÓN OPTIMIZADA 🚨
def verificar_falla_gps(unidad_data: Dict[str, Any], hora_venezuela: datetime, 
                        minutos_encendida: int, minutos_apagada: int) -> Dict[str, Any]:
    """
    Evalúa si la unidad debe cambiar a estado 'Falla GPS' y actualiza el diccionario de datos.
    """
    last_report_str = unidad_data.get('LastReportTime')
    ignicion_raw = unidad_data.get("ignition", "false").lower()
    estado_ignicion = ignicion_raw == "true"
    
    if not last_report_str:
        return unidad_data

    try:
        last_report_dt = datetime.strptime(last_report_str, TIME_FORMAT).replace(tzinfo=VENEZUELA_TZ)
    except ValueError:
        return unidad_data 

    # 1. Calcular la diferencia de tiempo
    diferencia_tiempo: timedelta = hora_venezuela - last_report_dt
    minutos_sin_reportar = diferencia_tiempo.total_seconds() / 60.0
    
    # 2. Definir los umbrales de tiempo
    UMBRAL_ENCENDIDA = timedelta(minutes=minutos_encendida)
    UMBRAL_APAGADA = timedelta(minutes=minutos_apagada)
    
    es_falla_gps = False
    motivo_falla = ""
    
    if estado_ignicion: 
        if diferencia_tiempo > UMBRAL_ENCENDIDA:
            es_falla_gps = True
            motivo_falla = f"Encendida **{minutos_sin_reportar:.0f} minutos** sin reportar (Umbral {minutos_encendida} min)."
    else: 
        if diferencia_tiempo > UMBRAL_APAGADA:
            es_falla_gps = True
            # Display simplificado a minutos totales (o horas si es mucho)
            if minutos_sin_reportar >= 60:
                 tiempo_display = f"{(minutos_sin_reportar / 60.0):.1f} horas"
            else:
                 tiempo_display = f"{minutos_sin_reportar:.0f} minutos"

            umbral_display = f"{minutos_apagada // 60}h {minutos_apagada % 60}min" if minutos_apagada >= 60 else f"{minutos_apagada}min"

            motivo_falla = f"Apagada **{tiempo_display}** sin reportar (Umbral {umbral_display})."
            
    # 3. Aplicar el estado y estilo si es Falla GPS
    if es_falla_gps:
        unidad_data['Estado_Falla_GPS'] = True 
        unidad_data['FALLA_GPS_MOTIVO'] = motivo_falla 
        unidad_data['LAST_REPORT_TIME_FOR_DETAIL'] = last_report_str 
        unidad_data['IGNICION_OVERRIDE'] = "Falla GPS 🚫"
        # Usamos el f-string para el estilo
        unidad_data['CARD_STYLE_OVERRIDE'] = f"background-color: {COLOR_FALLA_GPS}; padding: 15px; border-radius: 5px; color: black; margin-bottom: 0px;"

    return unidad_data


# --- 🚨 CONFIGURACIÓN DE AUDIO Y BASE64 (EJECUCIÓN ÚNICA AL INICIO) 🚨 ---

# @st.cache_resource para asegurar que se ejecuta una sola vez y no se recalcula en cada rerun.
@st.cache_resource(ttl=None) 
def obtener_audio_base64(audio_path):
    """Codifica el archivo de audio en una cadena Base64 al inicio."""
    if not os.path.exists(audio_path):
        # En una app en producción, es mejor solo logear el error que detener la app
        print(f"Error Crítico: No se encontró el archivo de audio '{audio_path}'.")
        return None
    try:
        with open(audio_path, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except Exception as e:
        print(f"Error al codificar el audio: {e}")
        return None

# 🚨 EJECUCIÓN DEL BASE64 UNA SOLA VEZ AL INICIO 🚨
# NOTA: ASUMO que los archivos 'parada.mp3' y 'velocidad.mp3' existen en el mismo directorio.
# Si no existen, las alertas de audio no funcionarán.
AUDIO_BASE64_PARADA = obtener_audio_base64("parada.mp3") 
AUDIO_BASE64_VELOCIDAD = obtener_audio_base64("velocidad.mp3") 

def reproducir_alerta_sonido(base64_str):
    """
    Inyecta el script HTML con el audio Base64 usando st.markdown.
    """
    if not base64_str:
        return
        
    unique_id = int(time.time() * 1000)
    audio_html = f"""
    <audio controls autoplay style="display:none" id="alerta_audio_tag_{unique_id}">
        <source src="data:audio/mp3;base64,{base64_str}" type="audio/mp3"> 
    </audio>
    <script>
        // Lógica de carga y reproducción para evitar bloqueo de autoplay en algunos navegadores
        const audio = document.getElementById('alerta_audio_tag_{unique_id}');
        if (audio) {{
            audio.volume = 1.0; 
            audio.load();
            audio.play().catch(error => console.warn('Bloqueo de Autoplay: ', error));
        }}
        // OPCIONAL: Eliminar el elemento después de la reproducción para limpiar el DOM
        audio.onended = function() {{
            this.remove();
        }};
    </script>
    """
    st.markdown(audio_html, unsafe_allow_html=True)
# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Monitoreo GPS - FOSPUCA",
    layout="wide",
    initial_sidebar_state="expanded"
)
# --- INYECCIÓN DE CSS (Optimizado para solo lo necesario) ---
st.markdown("""
    <style>
    /* 1. Regla para reducir el espacio superior de TODA la página */
    .block-container {
        padding-top: 2rem; 
        padding-bottom: 0rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    
    /* 2. Regla para apuntar al título "Monitoreo En Tiempo Real" */
    #main-title {
        margin-top: -30px; 
    }
    
    /* Modifica el tamaño de todos los st.header() (h1) */
    h1 {
        font-size: 2.5rem; 
        font-weight: 700; 
    }
    </style>
    """, unsafe_allow_html=True)
# --- CONFIGURACIÓN DE LA API Y SEGURIDAD (st.secrets) ---
API_URL = "https://flexapi.foresightgps.com/ForesightFlexAPI.ashx"

try:
# --- 🔑 La clave se carga de forma SEGURA desde st.secrets ---
    BASIC_AUTH_HEADER = st.secrets["api"]["basic_auth_header"]
except KeyError:
    # Este error detiene la aplicación si no hay clave, lo cual es correcto
    st.error("ERROR CRÍTICO: No se pudo encontrar la clave 'basic_auth_header' en st.secrets.")
    st.info("Asegúrese de configurar el archivo '.streamlit/secrets.toml' o la configuración de 'Secrets' en la nube.")
    st.stop() 

# --- CONFIGURACIÓN DINÁMICA DE CARGA ---

# Nombre de la carpeta que contendrá los archivos JSON de las flotas
CONFIG_DIR = "configuracion_flotas" 

@st.cache_data(ttl=None) # La configuración solo se carga una vez
def cargar_configuracion_flotas(config_dir: str = CONFIG_DIR) -> Dict[str, Dict[str, Any]]:
    """Carga dinámicamente la configuración de las flotas desde archivos JSON."""
    flotas_config = {}
    
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)
        print(f"Directorio de configuración '{config_dir}' creado. ¡Agrega tus archivos JSON!")
        return {}

    for filename in os.listdir(config_dir):
        if filename.endswith(".json"):
            nombre_flota_file = os.path.splitext(filename)[0]
            nombre_flota = nombre_flota_file.replace("_", " ")

            filepath = os.path.join(config_dir, filename)
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # 🚨 MODIFICACIÓN CLAVE: Ahora se valida la existencia de 'sede_coords'.
                    if all(key in data for key in ["ids", "sede_coords"]):
                        
                        # Hacemos que 'resguardo_secundario_coords' sea opcional.
                        if "resguardo_secundario_coords" not in data:
                            data["resguardo_secundario_coords"] = []
                            
                        # 🚨 ¡NUEVO! Hacemos que 'vertedero_coords' sea opcional.
                        if "vertedero_coords" not in data:
                            data["vertedero_coords"] = []

                        flotas_config[nombre_flota] = data
                    else:
                        print(f" [ADVERTENCIA] Archivo '{filename}' omitido: faltan claves obligatorias (ids, sede_coords).")

            except json.JSONDecodeError:
                print(f" [ERROR] No se pudo parsear el archivo JSON: {filename}. Revisa su formato.")
            except Exception as e:
                print(f" [ERROR] Ocurrió un error al cargar {filename}: {e}")

    return flotas_config

# --- CONFIGURACIÓN MULTI-FLOTA (Se carga dinámicamente) ---
FLOTAS_CONFIG = cargar_configuracion_flotas()

# --- VERIFICACIÓN DE CARGA DE CONFIGURACIÓN ---
if not FLOTAS_CONFIG:
    # Esta verificación asegura que si falla la carga al inicio, la app muestra un mensaje útil.
    st.set_page_config(page_title="Error de Configuración", layout="wide")
    st.error("❌ **ERROR CRÍTICO DE CARGA DE FLOTAS** ❌")
    st.markdown("---")
    st.warning("No se pudieron cargar flotas. Por favor, verifica lo siguiente:")
    st.markdown("""
        1.  Asegúrate de tener la carpeta **`configuracion_flotas`** al lado de `dashboard.py`.
        2.  Revisa que tus archivos JSON estén dentro de esa carpeta.
        3.  Verifica que **TODOS** los archivos JSON utilicen el formato con **`"ids"`** y **`"sede_coords"`** (ej: `"sede_coords": [[10.456, -66.123]]`).
    """)
    st.stop() 


# -----------------------------------------------------------

# --- ENCABEZADO DE AUTENTICACION ---
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": BASIC_AUTH_HEADER
}


# --- CALCULO DE DISTANCIA (FUNCIÓN HAVERSINE) ---
def haversine(lat1, lon1, lat2, lon2):
    """Calcula la distancia Haversine entre dos puntos en la Tierra (en km). OPTIMIZADA con numpy."""
    R = 6371  
    # Vectorización con numpy
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = np.sin(dlat/2.0)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2.0)**2
    c = 2 * np.arcsin(np.sqrt(a)) 
    return R * c

# --- FUNCIÓN AUXILIAR PARA ESTILOS (Sigue existiendo para la Leyenda) ---
def get_card_style(ignicion_status, speed):
    """Determina el estilo de la tarjeta basado en el estado de ignición y velocidad."""
    
    # 1. ESTADO POR DEFECTO: Encendida en Ruta (Verde)
    bg_color = "#4CAF50" # Verde
    text_color = "white"

    if "Vertedero" in ignicion_status:
        bg_color = COLOR_VERTEDERO
        text_color = "white" 

    elif "Resguardo (Sede)" in ignicion_status:
        bg_color = "#337ab7"
    elif "Encendida (Sede)" in ignicion_status:
        bg_color = "#B37305"  
    elif "Apagada" in ignicion_status:
        bg_color = "#D32F2F"  
    elif "Resguardo (Fuera de Sede)" in ignicion_status:
        bg_color = COLOR_RESGUARDO_SECUNDARIO
    elif "Falla GPS" in ignicion_status:
        bg_color = COLOR_FALLA_GPS
        text_color = "white"
        
    style = (
        f"background-color: {bg_color}; "
        f"padding: 15px; "
        f"border-radius: 5px; "
        f"color: {text_color}; "
        f"margin-bottom: 0px;"
    )
    return style

# --- CALLBACK MODIFICADO PARA DESCARTE ---
def descartar_alerta_stop(unidad_id_a_descartar):
    """Marca la alerta de Parada Larga como 'descartada' y DESACTIVA la bandera de audio."""
    st.session_state['alertas_descartadas'][unidad_id_a_descartar] = True
    st.session_state['reproducir_audio_alerta'] = False 


# --- DESCARTAR EXCESO DE VELOCIDAD ---
def descartar_alerta_velocidad(unidad_id_a_descartar):
    """Marca la alerta de Exceso de Velocidad como 'descartada' y DESACTIVA la bandera de audio."""
    st.session_state['alertas_velocidad_descartadas'][unidad_id_a_descartar] = True
    st.session_state['reproducir_audio_velocidad'] = False


# --- DATOS DE RESPALDO (FALLBACK) ---
def get_fallback_data(error_type="Conexión Fallida"): 
    """Genera una estructura de datos de una sola fila para señalizar el error en el main loop."""
    
    # Aseguramos que la estructura del DataFrame sea completa para evitar errores en el bucle
    return pd.DataFrame([{
        "UNIDAD": "FALLBACK", 
        "UNIT_ID": "FALLBACK_ID",
        "IGNICION": "N/A", 
        "VELOCIDAD": 0.0, 
        "LATITUD": 0.0, 
        "LONGITUD": 0.0, 
        "UBICACION_TEXTO": f"FALLBACK - {error_type}", 
        "CARD_STYLE": "background-color: #D32F2F; padding: 15px; border-radius: 5px; color: white; margin-bottom: 0px;",
        "FALLA_GPS_MOTIVO": None,
        "LAST_REPORT_TIME_DISPLAY": None,
        "STOP_DURATION_MINUTES": 0.0, # Añadido para consistencia
        "STOP_DURATION_TIMEDELTA": timedelta(seconds=0), # Añadido para consistencia
        "EN_SEDE_FLAG": False, # Añadido para consistencia
        "EN_RESGUARDO_SECUNDARIO_FLAG": False, # Añadido para consistencia
        "EN_VERTEDERO_FLAG": False, # NUEVO FLAG
        "ES_FALLA_GPS_FLAG": False # Añadido para consistencia
    }])

# --- FUNCIÓN DE OBTENCIÓN Y FILTRADO DE DATOS DINÁMICA (TTL de 5 segundos) ---
# Se usan los argumentos gps_min_encendida y gps_min_apagada para que la función sepa cuándo refrescar el caché.
@st.cache_data(ttl=5)
def obtener_datos_unidades(nombre_flota: str, config: Dict[str, Any], gps_min_encendida: int, gps_min_apagada: int):
    """Obtiene y limpia los datos de la API, aplicando la lógica de color por estado/sede, incluyendo Falla GPS."""
    
    flota_data = config.get(nombre_flota)
    if not flota_data:
        # Esto no debería pasar si la lógica de selección en el sidebar es correcta
        return get_fallback_data("Configuración de Flota No Encontrada")

    # 🚨 OBTENCIÓN DE COORDENADAS DE UBICACIONES DINÁMICAS DESDE EL JSON 🚨
    # Todas son listas de listas de [lat, lon]
    SEDE_COORDS = flota_data.get("sede_coords", [])
    COORDENADAS_RESGUARDO_SECUNDARIO = flota_data.get("resguardo_secundario_coords", [])
    COORDENADAS_VERTEDERO = flota_data.get("vertedero_coords", []) # ¡NUEVO!
    
    if not SEDE_COORDS:
        return get_fallback_data("Error de Configuración: 'sede_coords' vacía.")

    # Aseguramos un tamaño de página suficiente para todos los IDs
    payload = {
        "userid": "82825",
        "requesttype": 0,
        "isdeleted": 0,
        "pageindex": 1,
        "orderby": "name",
        "orderdirection": "ASC",
        "conncode": "SATEQSA",
        "elements": 1,
        "ids": flota_data["ids"], 
        "method": "usersearchplatform",
        "pagesize": len(flota_data["ids"].split(',')) + 5, 
        "prefix": True
    }
    
    try:
        response = requests.post(API_URL, json=payload, headers=HEADERS, timeout=5)
        response.raise_for_status()  
        data = response.json()
        
        lista_unidades = data.get("ForesightFlexAPI", {}).get("DATA", [])
        
        if not lista_unidades:
            return get_fallback_data("Lista de Unidades Vacía (Revisa IDs)")
        
        hora_actual_ve = obtener_hora_venezuela()

        # --- PROCESAMIENTO DE DATOS REALES ---
        datos_filtrados = []
        for unidad in lista_unidades:
            
            # 1. APLICAR LÓGICA DE FALLA GPS CON PARÁMETROS DINÁMICOS
            unidad_con_falla_check = verificar_falla_gps(unidad, hora_actual_ve, gps_min_encendida, gps_min_apagada)
            
            es_falla_gps = unidad_con_falla_check.get('Estado_Falla_GPS', False)
            
            # Extracción y limpieza de datos
            ignicion_raw = unidad_con_falla_check.get("ignition", "false").lower()
            # Uso de float() con valor por defecto seguro
            velocidad = float(unidad_con_falla_check.get("speed_dunit", 0.0))
            lat = float(unidad_con_falla_check.get("ylat", 0.0))
            lon = float(unidad_con_falla_check.get("xlong", 0.0))
            # unit_id debe ser único, usamos unitid o name como fallback
            unit_id = unidad_con_falla_check.get("unitid", unidad_con_falla_check.get("name", "N/A_ID_FALLBACK")) 

            ignicion_estado = ignicion_raw == "true"
            
            falla_gps_motivo = None
            last_report_time_display = unidad_con_falla_check.get('LastReportTime', 'N/A')
            
            if es_falla_gps:
                # Caso Falla GPS: Sobrescribe el estado y estilo
                estado_final_display = unidad_con_falla_check['IGNICION_OVERRIDE']
                card_style = unidad_con_falla_check['CARD_STYLE_OVERRIDE']
                falla_gps_motivo = unidad_con_falla_check.get('FALLA_GPS_MOTIVO')
                last_report_time_display = unidad_con_falla_check.get('LAST_REPORT_TIME_FOR_DETAIL', last_report_time_display)
                
                # Para fines de métricas, marcamos el tipo de resguardo como NINGUNO
                en_sede = False
                en_resguardo_secundario = False
                en_vertedero = False # ¡NUEVO FLAG!
                
            else:
                # --- CÁLCULO DE DISTANCIA A UBICACIONES DINÁMICAS ---
                
                # 1. ¿Está en el VERTEDERO? (Máxima Prioridad Operacional)
                en_vertedero = False
                for vertedero_coords in COORDENADAS_VERTEDERO:
                    v_lat, v_lon = vertedero_coords
                    distancia = haversine(lat, lon, v_lat, v_lon)
                    if distancia <= PROXIMIDAD_KM:
                        en_vertedero = True
                        break 
                
                # 2. ¿Está en la SEDE? (Revisar solo si NO está en Vertedero)
                en_sede = False
                if not en_vertedero:
                    for sede_coords in SEDE_COORDS:
                        lat_sede, lon_sede = sede_coords
                        distancia = haversine(lat, lon, lat_sede, lon_sede)
                        if distancia <= PROXIMIDAD_KM:
                            en_sede = True
                            break 
                
                # 3. ¿Está en Resguardo Secundario? (Revisar solo si NO está en Vertedero ni Sede)
                en_resguardo_secundario = False
                if not en_vertedero and not en_sede and COORDENADAS_RESGUARDO_SECUNDARIO: 
                    for resguardo_coords in COORDENADAS_RESGUARDO_SECUNDARIO:
                        lat_res, lon_res = resguardo_coords
                        distancia_resguardo = haversine(lat, lon, lat_res, lon_res)
                        if distancia_resguardo <= PROXIMIDAD_KM:
                            en_resguardo_secundario = True
                            break
                
                # --- LÓGICA DE ESTADO FINAL ---
                
                estado_final_display = "Apagada ❄️" 
                color_fondo = "#D32F2F" 
                color_texto = "white"
                
                if en_vertedero:
                    estado_final_display = "Vertedero 🚛"; 
                    color_fondo = COLOR_VERTEDERO
                    color_texto = "white" 
                
                elif ignicion_estado:
                    if en_sede:
                        estado_final_display = "Encendida (Sede) 🔥"; color_fondo = "#B37305"
                    else:
                        estado_final_display = "Encendida 🔥"; color_fondo = "#4CAF50"
                
                else: # Apagada
                    if en_sede:
                        estado_final_display = "Resguardo (Sede) 🛡️"; color_fondo = "#337ab7"
                    elif en_resguardo_secundario:
                        estado_final_display = "Resguardo (Fuera de Sede) 🛡️"; color_fondo = COLOR_RESGUARDO_SECUNDARIO
                
                card_style = f"background-color: {color_fondo}; padding: 15px; border-radius: 5px; color: {color_texto}; margin-bottom: 0px;"

            datos_filtrados.append({
                "UNIDAD": unidad_con_falla_check.get("name", "N/A"),
                "UNIT_ID": unit_id, 
                "IGNICION": estado_final_display, 
                "VELOCIDAD": velocidad,
                "LATITUD": lat,
                "LONGITUD": lon,
                "UBICACION_TEXTO": unidad_con_falla_check.get("location", "Dirección no disponible"),
                "CARD_STYLE": card_style,
                "FALLA_GPS_MOTIVO": falla_gps_motivo,
                "LAST_REPORT_TIME_DISPLAY": last_report_time_display,
                "STOP_DURATION_MINUTES": 0.0, # Inicializado para el DataFrame
                "STOP_DURATION_TIMEDELTA": timedelta(seconds=0), # Inicializado para el DataFrame
                # NUEVAS COLUMNAS PARA MÉTRICAS (incluido Vertedero)
                "EN_SEDE_FLAG": en_sede,
                "EN_RESGUARDO_SECUNDARIO_FLAG": en_resguardo_secundario,
                "EN_VERTEDERO_FLAG": en_vertedero, # ¡NUEVO FLAG!
                "ES_FALLA_GPS_FLAG": es_falla_gps
            })
        
        # El DataFrame se devuelve con las columnas inicializadas
        return pd.DataFrame(datos_filtrados)

    except requests.exceptions.RequestException as e:
        error_msg = f"API Error: {e}" if not hasattr(e, 'response') else f"HTTP Error: {e.response.status_code}"
        print(f"❌ Error de Conexión/API: {error_msg}")
        return get_fallback_data("Error de Conexión/API")


# --- FUNCIÓN PARA MOSTRAR LA LEYENDA DE COLORES EN EL SIDEBAR ---
def display_color_legend():
    """Muestra la leyenda de colores de las tarjetas de estado de forma compacta."""
    
    # 🚨 LEYENDA ACTUALIZADA CON EL NUEVO COLOR 🚨
    COLOR_MAP = {
        "#4CAF50": "Encendida en Ruta",             
        "#D32F2F": "Apagada",                      
        "#337ab7": "Resguardo (Sede)",             
        COLOR_RESGUARDO_SECUNDARIO: "Resguardo (F. Sede)", 
        COLOR_VERTEDERO: "En Vertedero", # ¡NUEVO COLOR!
        "#B37305": "Encendida (Sede)",             
        "#FFC107": "Parada Larga",                 
        COLOR_FALLA_GPS: "Falla GPS",              
    }

    cols_legend = st.columns(2)
    col_index = 0
    
    for color, description in COLOR_MAP.items():
        # Determina si el texto debe ser negro para fondos claros
        text_color = "white"  
        
        with cols_legend[col_index % 2]:
            legend_html = f"""
            <div style="display: flex; align-items: center; margin-bottom: 3px;">
                <div style="width: 14px; height: 14px; background-color: {color}; border-radius: 3px; margin-right: 5px; border: 1px solid #ddd;"></div>
                <span style="font-size: 0.85em; color: {text_color};">{description}</span>
            </div>
            """
            st.markdown(legend_html, unsafe_allow_html=True)
        col_index += 1
# -------------------------------------------------------------------------------------

# --- CALLBACKS DE AUTENTICACIÓN Y GUARDADO ---

def check_password(password_key="config_password_input"):
    """Callback para verificar la contraseña e iniciar la sesión de configuración."""
    if st.session_state.get(password_key) == CONFIG_PASSWORD:
        st.session_state['authenticated'] = True
        st.session_state[password_key] = "" # Limpiar el campo
    else:
        st.session_state['authenticated'] = False

def save_dynamic_config():
    """Guarda los valores actuales de los inputs del sidebar en el estado de sesión persistente."""
    # Los valores de los inputs se almacenan en st.session_state con sus keys temporales
    st.session_state['config_params']['TIME_SLEEP'] = st.session_state['input_time_sleep_temp']
    st.session_state['config_params']['STOP_THRESHOLD_MINUTES'] = st.session_state['input_stop_threshold_temp']
    st.session_state['config_params']['SPEED_THRESHOLD_KPH'] = st.session_state['input_speed_threshold_temp']
    st.session_state['config_params']['GPS_MIN_ENCENDIDA'] = st.session_state['input_gps_min_on_temp']
    st.session_state['config_params']['GPS_MIN_APAGADA'] = st.session_state['input_gps_min_off_temp']
    
    # Limpiar la caché para que la próxima llamada a la API use los nuevos parámetros
    st.cache_data.clear()
    
    st.toast("✅ Configuración guardada y aplicada!", icon='💾')

# --- INICIALIZACIÓN DEL ESTADO DE SESIÓN ---

if 'flota_seleccionada' not in st.session_state:
    st.session_state['flota_seleccionada'] = None 
if 'filtro_en_ruta' not in st.session_state: 
    st.session_state['filtro_en_ruta'] = False
if 'filtro_estado_especifico' not in st.session_state: 
    st.session_state['filtro_estado_especifico'] = "Mostrar Todos"
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False
if 'config_params' not in st.session_state:
    # Parámetros por defecto activos
    st.session_state['config_params'] = {
        'STOP_THRESHOLD_MINUTES': 10,
        'SPEED_THRESHOLD_KPH': 70,
        'GPS_MIN_ENCENDIDA': 5,
        'GPS_MIN_APAGADA': 70,
        'TIME_SLEEP': 3
    }

# 🚨 NUEVA FUNCIÓN COMPARTIDA: Almacena el estado de parada globalmente (Shared State) 🚨
@st.cache_resource(ttl=None) 
def get_global_stop_state() -> Dict[str, Any]:
    """Retorna un diccionario de estado que es único y compartido por todos los usuarios (Global State)."""
    # Usaremos una simple clave para almacenar el estado de cada unidad
    return {}

# Inicializar y obtener la referencia al estado global (se ejecuta una sola vez)
current_stop_state = get_global_stop_state()
# ------------------------------------------------------------------------------------

# El resto de variables deben seguir usando st.session_state ya que son locales a cada usuario.
if 'alertas_descartadas' not in st.session_state:
    st.session_state['alertas_descartadas'] = {}
if 'alertas_velocidad_descartadas' not in st.session_state:
    st.session_state['alertas_velocidad_descartadas'] = {}
if 'reproducir_audio_alerta' not in st.session_state:
    st.session_state['reproducir_audio_alerta'] = False
if 'reproducir_audio_velocidad' not in st.session_state:
    st.session_state['reproducir_audio_velocidad'] = False
if 'log_historial' not in st.session_state:
    st.session_state['log_historial'] = [] 


# --- CONFIGURACION DEL SIDEBAR ---

def actualizar_dashboard():
    """Función de callback para re-ejecutar el script al cambiar el filtro o flota."""
    st.cache_data.clear() 
    pass

with st.sidebar:
    # 1. SELECCIÓN DE FLOTA
    st.markdown('<p style="font-size: 30px; font-weight: bold; color: white; margin-bottom: 0px; text-align: center;">Selección de Flota 🗺️</p>', unsafe_allow_html=True)
    
    flota_keys = ["-- Seleccione una Flota --"] + list(FLOTAS_CONFIG.keys())
    
    current_flota = st.session_state.get('flota_seleccionada')
    try:
        current_index = flota_keys.index(current_flota) if current_flota else 0
    except ValueError:
        current_index = 0
        
    flota_actual = st.selectbox(
        "Seleccione la Flota a Monitorear:",
        options=flota_keys,
        index=current_index,
        key="flota_selector",
        on_change=actualizar_dashboard,
        label_visibility="collapsed"
    )
    
    if flota_actual == flota_keys[0]:
        st.session_state['flota_seleccionada'] = None
    else:
        st.session_state['flota_seleccionada'] = flota_actual


    # --- NUEVA SECCIÓN: CONFIGURACIÓN DINÁMICA DE PARÁMETROS ---
    with st.expander("⚙️ **Configuración Dinámica**", expanded=st.session_state['authenticated']):
        
        if st.session_state['authenticated']:
            # Inicializar los valores temporales con los activos al abrir el expander
            for key, default_key in [
                ('input_time_sleep_temp', 'TIME_SLEEP'),
                ('input_stop_threshold_temp', 'STOP_THRESHOLD_MINUTES'),
                ('input_speed_threshold_temp', 'SPEED_THRESHOLD_KPH'),
                ('input_gps_min_on_temp', 'GPS_MIN_ENCENDIDA'),
                ('input_gps_min_off_temp', 'GPS_MIN_APAGADA')
            ]:
                if key not in st.session_state:
                    st.session_state[key] = st.session_state['config_params'][default_key]
                
            st.markdown("##### Frecuencia y Tiempos de App")
            
            st.slider(
                "Pausa del Ciclo (Segundos)", min_value=1, max_value=10, 
                value=st.session_state['config_params']['TIME_SLEEP'], 
                step=1, 
                key="input_time_sleep_temp", 
                help="Tiempo de espera entre actualizaciones completas del Dashboard (tiempo.sleep)."
            )
            
            st.caption(f"TTL de Datos (API): **5 segundos** (fijo en el código, pero se limpia con cada cambio de parámetro).")
            
            st.markdown("##### Umbrales de Alerta")
            
            st.number_input(
                "Parada Larga (minutos)", min_value=1, max_value=120, 
                value=st.session_state['config_params']['STOP_THRESHOLD_MINUTES'], 
                step=1, 
                key="input_stop_threshold_temp", 
                help="Tiempo inactivo fuera de sede para activar la alerta de parada larga."
            )
            
            st.number_input(
                "Umbral de Velocidad (Km/h)", min_value=10, max_value=120, 
                value=st.session_state['config_params']['SPEED_THRESHOLD_KPH'], 
                step=5, 
                key="input_speed_threshold_temp", 
                help="Velocidad mínima para activar la alerta de exceso de velocidad."
            )
            
            st.markdown("##### Falla GPS (Minutos sin Reportar)")
            
            st.number_input(
                "Falla GPS (Motor Encendido)", min_value=1, max_value=60, 
                value=st.session_state['config_params']['GPS_MIN_ENCENDIDA'], 
                step=1, 
                key="input_gps_min_on_temp", 
                help="Umbral de minutos sin reporte con ignición en True."
            )
            
            st.number_input(
                "Falla GPS (Motor Apagado)", min_value=30, max_value=180, 
                value=st.session_state['config_params']['GPS_MIN_APAGADA'], 
                step=5, 
                key="input_gps_min_off_temp", 
                help="Umbral de minutos sin reporte con ignición en False (70 min = 1h 10min)."
            )
            
            st.markdown("---")

            st.button(
                "💾 Guardar Cambios y Aplicar",
                on_click=save_dynamic_config,
                type="primary",
                use_container_width=True,
                key="btn_save_config"
            )
            
        else:
            # --- USUARIO NO AUTENTICADO: SOLICITAR CONTRASEÑA ---
            st.markdown("🔒 Introduce la contraseña para acceder a la configuración dinámica.")
            
            st.text_input(
                "Contraseña", 
                type="password", 
                key="config_password_input",
                on_change=check_password,
                label_visibility="collapsed"
            )
            
            if 'config_password_input' in st.session_state and st.session_state['config_password_input'] and st.session_state['config_password_input'] != CONFIG_PASSWORD:
                st.error("Contraseña incorrecta.")
                
            st.caption("Contraseña de acceso: `admin`")
  
    # 3. LEYENDA DE COLORES 
    with st.expander("##### Leyenda de Estados 🎨", expanded=False):
        display_color_legend()
        
    # --- INICIO DEL EXPANDER DE FILTROS ---
    if st.session_state['flota_seleccionada']:
       
        with st.expander("Filtros de Estado 🚦", expanded=False):
            
            st.checkbox(
                "**Unidades en Ruta** (Excluir Resguardo y Fallas)", 
                key="filtro_en_ruta", 
                on_change=actualizar_dashboard 
            )
            
            # 🚨 FILTRO ACTUALIZADO CON VERTEDERO 🚨
            filtro_estado_options = [
                "Mostrar Todos",
                "Vertedero 🚛", # ¡NUEVO FILTRO!
                "Falla GPS 🚫", 
                "Apagadas ❄️", 
                "Paradas Largas 🛑", 
                "Resguardo (Sede) 🛡️",
                "Resguardo (Fuera de Sede) 🛡️"
            ]
            
            st.session_state['filtro_estado_especifico'] = st.radio(
                "O estados específicos:",
                options=filtro_estado_options,
                key="filtro_radio",
                index=filtro_estado_options.index(st.session_state['filtro_estado_especifico']),
                on_change=actualizar_dashboard,
                label_visibility="collapsed"
            )
# --- FIN DEL EXPANDER DE FILTROS ---

    # --- PLACEHOLDERS EN EL SIDEBAR (Declaración única) ---
    metricas_placeholder = st.empty() # Este es el placeholder que contendrá el expander de estadísticas.
    st.markdown("---")
    audio_stop_placeholder = st.empty()
    alerta_stop_placeholder = st.empty()
    st.markdown("---")
    audio_velocidad_placeholder = st.empty()
    alerta_velocidad_placeholder = st.empty()
    st.markdown("---")
    
    debug_status_placeholder = st.empty()
    log_placeholder = st.empty() 
    
# --- Función para generar la línea de métrica con estilo (Fuera del sidebar para uso en el loop) ---
def format_metric_line(label, value=None, value_size="1.5rem", is_header=False, is_section_title=False):
    """Genera el HTML para las métricas con estilo unificado: Etiqueta a la izquierda, Valor a la derecha."""
        
    text_style = "color: white; font-family: 'Consolas', 'Courier New', monospace; font-size: 1rem;"
        
    if is_header:
        label_html = f'<p style="font-size: 1.2rem; font-weight: bold; margin-bottom: 0px;">{label}</p>'
        return f'<div style="border-bottom: 1px solid #444444; margin: 10px 0 10px 0;">{label_html}</div>'
            
    if is_section_title:
        return f'<p style="font-size: 1.1rem; font-weight: bold; margin-bottom: 5px; color: white;">{label}</p>'

    value_html = f'<span style="font-size: {value_size}; font-weight: bold; color: white;">{value}</span>'
        
    html_content = f"""
    <p style="{text_style} display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
        <span style="white-space: nowrap;">{label}:</span>
        <span style="display: flex; align-items: baseline;">{value_html}</span>
    </p>
    """
    return html_content

# === BUCLE PRINCIPAL (while True) ===

# Placeholder para el contenido principal (Tarjetas)
placeholder_main_content = st.empty() 

# Usamos la referencia al estado global obtenida antes del bucle
# current_stop_state = get_global_stop_state()

while True:
    
    flota_a_usar = st.session_state['flota_seleccionada'] 
    
    # LECTURA DE LOS PARÁMETROS ACTIVOS
    config = st.session_state['config_params']
    STOP_THRESHOLD_MINUTES = config['STOP_THRESHOLD_MINUTES']
    SPEED_THRESHOLD_KPH = config['SPEED_THRESHOLD_KPH']
    GPS_MIN_ENCENDIDA = config['GPS_MIN_ENCENDIDA']
    GPS_MIN_APAGADA = config['GPS_MIN_APAGADA']
    TIME_SLEEP = config['TIME_SLEEP']

    # --- CONDICIÓN CRÍTICA: NO EJECUTAR SI NO HAY FLOTA SELECCIONADA ---
    if not flota_a_usar:
        with placeholder_main_content.container():
            st.markdown(
    f"<h2 id='main-title'>Rastreo GPS - Monitoreo GPS - FOSPUCA</h2>", 
    unsafe_allow_html=True
)
            st.markdown("---")
            st.info("👋 Por favor, **seleccione una Flota** en el panel lateral (Sidebar) para comenzar el monitoreo en tiempo real.")
            
        # Limpiar Placeholders (reutilizamos la referencia del sidebar)
        try:
             # Estas referencias deben existir si el sidebar se cargó correctamente.
            audio_stop_placeholder.empty()
            audio_velocidad_placeholder.empty()
            alerta_velocidad_placeholder.empty()
            alerta_stop_placeholder.empty()
            metricas_placeholder.empty()
            debug_status_placeholder.empty()
            log_placeholder.empty() 
        except NameError:
             # Solo si se accede antes de la inicialización del sidebar
             pass
            
        time.sleep(1) 
        continue 
    # --------------------------------------------------------------------------

    # Obtener datos
    # 🚨 NOTA: La función obtener_datos_unidades ahora retorna flags EN_VERTEDERO_FLAG
    df_data_original = obtener_datos_unidades(flota_a_usar, FLOTAS_CONFIG, GPS_MIN_ENCENDIDA, GPS_MIN_APAGADA)
    
    is_fallback = "FALLBACK" in df_data_original["UNIDAD"].iloc[0]
    
    # -- LÓGICA DE DETECCIÓN DE PARADAS LARGAS Y EXCESO DE VELOCIDAD --

    now = pd.Timestamp.now(tz='America/Caracas') 
    
    if not is_fallback:
        # Optimización: Iterar sobre las filas y actualizar el estado
        for index, row in df_data_original.iterrows():
            unit_id_api = row['UNIT_ID']
            velocidad = row['VELOCIDAD']
            
            # Inicialización de estado completo
            if unit_id_api not in current_stop_state:
                current_stop_state[unit_id_api] = {
                    'last_move_time': now,
                    'alerted_stop_minutes': None, 
                    'speed_alert_start_time': None, 
                    'last_recorded_speed': 0.0      
                }
                # No podemos continuar, necesitamos el estado inicial
            
            last_state = current_stop_state[unit_id_api]
            is_moving = velocidad > 1.0 
            
            # Determinar si la unidad NO está en ninguna zona de resguardo/sede/vertedero
            is_out_of_hq = not (row['EN_SEDE_FLAG'] or row['EN_RESGUARDO_SECUNDARIO_FLAG'] or row['EN_VERTEDERO_FLAG'] or row['ES_FALLA_GPS_FLAG'])
            
            is_speeding = velocidad >= SPEED_THRESHOLD_KPH

            # --- LÓGICA DE EXCESO DE VELOCIDAD (START/UPDATE) ---
            if is_speeding and is_out_of_hq:
                if last_state['speed_alert_start_time'] is None:
                    last_state['speed_alert_start_time'] = now
                
                if velocidad > last_state['last_recorded_speed']:
                    last_state['last_recorded_speed'] = velocidad

            # --- LÓGICA DE EXCESO DE VELOCIDAD (END/LOG) ---
            elif not is_speeding and last_state['speed_alert_start_time'] is not None:
                start_time = last_state['speed_alert_start_time']
                duration_timedelta = now - start_time
                duration_minutes = duration_timedelta.total_seconds() / 60.0
                
                # Registra solo si el exceso duró más de 10 segundos (~0.166 min)
                if duration_minutes >= 0.166: 
                    hora_log = now.strftime('%H:%M:%S')
                    nombre_unidad_display = row['UNIDAD'].split('-')[0] if '-' in row['UNIDAD'] else row['UNIDAD']
                    max_speed_recorded = last_state['last_recorded_speed']
                    
                    log_message = (
                        f"**🟡 {hora_log}** | Unidad: **{nombre_unidad_display}** "
                        f"| Exceso de Velocidad Máx: **{max_speed_recorded:.1f} Km/h** "
                        f"| por: **{duration_minutes:.1f} min** "
                        f"| en Dirección: {row['UBICACION_TEXTO']}"
                    )
                    st.session_state['log_historial'].insert(0, log_message)
                
                # RESET
                last_state['speed_alert_start_time'] = None 
                last_state['last_recorded_speed'] = 0.0

            # --- LÓGICA DE PARADA LARGA (Movimiento Detectado - Log FIN Parada Larga) ---
            if is_moving:
                
                # Actualizar el DataFrame *antes* del log
                df_data_original.loc[index, 'STOP_DURATION_MINUTES'] = 0.0 
                
                if last_state.get('alerted_stop_minutes'):
                    
                    hora_log = now.strftime('%H:%M:%S')
                    duracion_log = f"{last_state['alerted_stop_minutes']:.1f}"
                    nombre_unidad_display = row['UNIDAD'].split('-')[0] if '-' in row['UNIDAD'] else row['UNIDAD']
                    
                    log_message = (
                        f"**🟢 {hora_log}** | Unidad: **{nombre_unidad_display}** "
                        f"| FIN de Parada Larga, por: **{duracion_log} min** "
                        f"| Ubicación: {row['UBICACION_TEXTO']}"
                    )
                    
                    st.session_state['log_historial'].insert(0, log_message)
                    
                    last_state['alerted_stop_minutes'] = None
                
                last_state['last_move_time'] = now
                
                # Reinicio de estados de alerta al moverse
                if row['UNIDAD'] in st.session_state['alertas_descartadas']:
                    del st.session_state['alertas_descartadas'][row['UNIDAD']]
                if row['UNIDAD'] in st.session_state['alertas_velocidad_descartadas']:
                    del st.session_state['alertas_velocidad_descartadas'][row['UNIDAD']]
                
                # Desactivamos las banderas de reproducción si la unidad se mueve
                st.session_state['reproducir_audio_alerta'] = False
                st.session_state['reproducir_audio_velocidad'] = False

            else: # Unit is stopped (Lógica de Parada Larga - Actualizar Duración)
                stop_duration_timedelta = now - last_state['last_move_time']
                stop_duration_minutes = stop_duration_timedelta.total_seconds() / 60.0
                
                # Actualizar el DataFrame
                df_data_original.loc[index, 'STOP_DURATION_MINUTES'] = stop_duration_minutes
                df_data_original.loc[index, 'STOP_DURATION_TIMEDELTA'] = stop_duration_timedelta
                
                # LÓGICA para marcar una parada larga *activa*
                if stop_duration_minutes > STOP_THRESHOLD_MINUTES and is_out_of_hq:
                    last_state['alerted_stop_minutes'] = stop_duration_minutes
                
    
    # Lógica de Filtrado Condicional (Mejorada la lógica de Parada Larga)
    df_data_mostrada = df_data_original
    
    filtro_en_ruta_activo = st.session_state.get("filtro_en_ruta", False) 
    filtro_estado_activo = st.session_state.get('filtro_estado_especifico', "Mostrar Todos")
    
    filtro_descripcion = "Todas las Unidades"
    
    if not is_fallback:
        
        # 1. Aplicar filtro de ESTADO ESPECÍFICO
        if filtro_estado_activo != "Mostrar Todos":
            
            if "Vertedero" in filtro_estado_activo: # ¡NUEVO FILTRO!
                df_data_mostrada = df_data_original[df_data_original["EN_VERTEDERO_FLAG"] == True]

            elif "Falla GPS" in filtro_estado_activo:
                df_data_mostrada = df_data_original[df_data_original["IGNICION"].str.contains("Falla GPS")]
            
            elif "Apagadas" in filtro_estado_activo:
                df_data_mostrada = df_data_original[df_data_original["IGNICION"].str.contains("Apagada ❄️")]
                
            elif "Resguardo (Sede)" in filtro_estado_activo:
                # Usa el flag para ser más preciso
                df_data_mostrada = df_data_original[df_data_original['EN_SEDE_FLAG'] == True]
                
            elif "Resguardo (Fuera de Sede)" in filtro_estado_activo:
                # Usa el flag para ser más preciso
                df_data_mostrada = df_data_original[df_data_original['EN_RESGUARDO_SECUNDARIO_FLAG'] == True]
            
            elif "Paradas Largas" in filtro_estado_activo:
                is_out_of_hq_status = ~df_data_original["IGNICION"].str.contains("(Sede)|Resguardo|Falla GPS|Vertedero") # ACTUALIZADO
                
                df_data_mostrada = df_data_original[
                    (df_data_original['STOP_DURATION_MINUTES'] > STOP_THRESHOLD_MINUTES) &
                    (df_data_original['VELOCIDAD'] < 1.0) &
                    is_out_of_hq_status
                ].copy()
                
            filtro_descripcion = filtro_estado_activo

        # 2. Aplicar filtro "Unidades en Ruta"
        elif filtro_en_ruta_activo:
            # En ruta significa: NO está en sede, NO en resguardo secundario, NO en vertedero, NO es Falla GPS
            is_en_ruta = ~(df_data_original['EN_SEDE_FLAG'] | df_data_original['EN_RESGUARDO_SECUNDARIO_FLAG'] | df_data_original['EN_VERTEDERO_FLAG'] | df_data_original['ES_FALLA_GPS_FLAG'])
            df_data_mostrada = df_data_original[is_en_ruta].copy()
            filtro_descripcion = "Unidades Fuera de Sede 🛣️"
            
        df_data_mostrada = df_data_mostrada.reset_index(drop=True)
    # FIN DE LA LÓGICA DE FILTRADO
    
    # Lógica de Detección y Construcción de Alerta de Parada Larga (Alertas Visibles)
    unidades_en_alerta_stop = pd.DataFrame()
    mensaje_alerta_stop = ""

    if not is_fallback:
        # La condición de parada larga incluye ahora NO estar en Vertedero
        todas_las_alertas_stop = df_data_original[
            (df_data_original['STOP_DURATION_MINUTES'] > STOP_THRESHOLD_MINUTES) &
            (~(df_data_original['EN_SEDE_FLAG'] | df_data_original['EN_RESGUARDO_SECUNDARIO_FLAG'] | df_data_original['EN_VERTEDERO_FLAG'] | df_data_original['ES_FALLA_GPS_FLAG']))
        ].copy()

        unidades_pendientes_stop = [
            uid for uid in todas_las_alertas_stop['UNIDAD'] 
            if st.session_state['alertas_descartadas'].get(uid) != True
        ]

        unidades_en_alerta_stop = todas_las_alertas_stop[
            todas_las_alertas_stop['UNIDAD'].isin(unidades_pendientes_stop)
        ].sort_values(by='STOP_DURATION_MINUTES', ascending=False)
        
        # CONTROL DEL AUDIO PARADA
        if not unidades_en_alerta_stop.empty:
            if st.session_state.get('reproducir_audio_alerta') == False:
                 st.session_state['reproducir_audio_alerta'] = True
            
            total_alertas = len(unidades_en_alerta_stop)
            mensaje_alerta_stop += f"**{total_alertas} PARADA LARGA(S) PENDIENTE(S) 🚨**\n\n"
            
            for _, row in unidades_en_alerta_stop.head(5).iterrows():
                nombre_unidad = row['UNIDAD'].split('-')[0]
                total_segundos = row['STOP_DURATION_TIMEDELTA'].total_seconds()
                tiempo_parado = f"{int(total_segundos // 60)}min {int(total_segundos % 60):02}seg" 
                mensaje_alerta_stop += (f"**{nombre_unidad}** ({tiempo_parado}):\n---\n")
        else:
             st.session_state['reproducir_audio_alerta'] = False
    
    # Lógica de Detección de Alerta de Velocidad
    unidades_en_alerta_speed = pd.DataFrame()
    mensaje_alerta_speed = ""

    if not is_fallback:
        # La condición de exceso de velocidad incluye ahora NO estar en Vertedero
        todas_las_alertas_speed = df_data_original[
            (df_data_original['VELOCIDAD'] >= SPEED_THRESHOLD_KPH) &
            (~(df_data_original['EN_SEDE_FLAG'] | df_data_original['EN_RESGUARDO_SECUNDARIO_FLAG'] | df_data_original['EN_VERTEDERO_FLAG'] | df_data_original['ES_FALLA_GPS_FLAG']))
        ].copy()

        unidades_pendientes_speed = [
            uid for uid in todas_las_alertas_speed['UNIDAD']
            if st.session_state['alertas_velocidad_descartadas'].get(uid) != True
        ]

        unidades_en_alerta_speed = todas_las_alertas_speed[
            todas_las_alertas_speed['UNIDAD'].isin(unidades_pendientes_speed)
        ].sort_values(by='VELOCIDAD', ascending=False)
        
        # CONTROL DEL AUDIO VELOCIDAD
        if not unidades_en_alerta_speed.empty:
            if st.session_state.get('reproducir_audio_velocidad') == False:
                 st.session_state['reproducir_audio_velocidad'] = True
            
            total_alertas = len(unidades_en_alerta_speed)
            mensaje_alerta_speed += f"**{total_alertas} EXCESO DE VELOCIDAD PENDIENTE(S) ⚠️**\n\n"
            
            for _, row in unidades_en_alerta_speed.head(5).iterrows():
                nombre_unidad = row['UNIDAD'].split('-')[0]
                velocidad_formateada = f"{row['VELOCIDAD']:.1f} Km/h"
                estado_critico = "🚨 CRÍTICO" if row['VELOCIDAD'] > SPEED_THRESHOLD_KPH + 4.0 else "⚠️ ALERTA"
                mensaje_alerta_speed += (f"**{nombre_unidad}** ({estado_critico} a {velocidad_formateada}):\n---\n")
        else:
            st.session_state['reproducir_audio_velocidad'] = False
    
    # =========================================================================
    # --- RENDERIZADO DE ALERTAS EN EL SIDEBAR ---
    # =========================================================================
    unique_time_id = int(time.time() * 1000) 
    
    # AUDIO PARADA
    with audio_stop_placeholder.container():
        if st.session_state.get('reproducir_audio_alerta'):
             reproducir_alerta_sonido(AUDIO_BASE64_PARADA)
        else:
             audio_stop_placeholder.empty() 
             
    # ALERTA PARADA
    with alerta_stop_placeholder.container():
        if not unidades_en_alerta_stop.empty:
            total_alertas_pendientes = len(unidades_en_alerta_stop)
            st.markdown(f"#### 🚨 Alerta de Parada Larga ({total_alertas_pendientes})")
            st.markdown("---")
                 
            st.warning(mensaje_alerta_stop) 
            
            def aceptar_todas_paradas():
                for uid in unidades_en_alerta_stop['UNIDAD']:
                    st.session_state['alertas_descartadas'][uid] = True
                st.session_state['reproducir_audio_alerta'] = False
                    
            st.button(
                "✅ Aceptar y Silenciar TODAS las Paradas", 
                key=f"descartar_all_stops_{unique_time_id}",
                on_click=aceptar_todas_paradas,
                type="primary", 
                use_container_width=True
            )
        else:
            alerta_stop_placeholder.empty()

    # AUDIO VELOCIDAD
    with audio_velocidad_placeholder.container():
        if st.session_state.get('reproducir_audio_velocidad'):
             reproducir_alerta_sonido(AUDIO_BASE64_VELOCIDAD)
        else:
             audio_velocidad_placeholder.empty()
             
    # ALERTA VELOCIDAD
    with alerta_velocidad_placeholder.container():
        if not unidades_en_alerta_speed.empty:
            total_alertas_pendientes_speed = len(unidades_en_alerta_speed)
            st.markdown(f"#### ⚠️ Exceso de Velocidad ({total_alertas_pendientes_speed})")
            st.markdown("---")
            
            st.error(mensaje_alerta_speed) 
            
            def aceptar_todas_velocidades():
                for uid in unidades_en_alerta_speed['UNIDAD']:
                    st.session_state['alertas_velocidad_descartadas'][uid] = True
                st.session_state['reproducir_audio_velocidad'] = False
                    
            st.button(
                "✅ Aceptar y Silenciar TODOS los Excesos", 
                key=f"descartar_all_speed_{unique_time_id}",
                on_click=aceptar_todas_velocidades,
                type="primary",
                use_container_width=True
            )
        else:
            alerta_velocidad_placeholder.empty()
            
    # --- 3. Actualización de Métricas del Sidebar (AHORA EN UN EXPANDER) ---
    with metricas_placeholder.container():
        if not is_fallback: 
            
            # Lógica para calcular métricas
            total_unidades = len(df_data_original)
            
            # Unidades encendidas (Incluye Encendida en Sede y Encendida en Ruta)
            unidades_encendidas = len(df_data_original[df_data_original["IGNICION"].str.contains("Encendida")])
            
            # Unidades apagadas (Solo Apagada ❄️)
            unidades_apagadas = len(df_data_original[df_data_original["IGNICION"].str.contains("Apagada ❄️")])
            
            # Unidades en Resguardo/Encendida en Sede (Usa el nuevo flag EN_SEDE_FLAG)
            unidades_en_sede = df_data_original['EN_SEDE_FLAG'].sum()
            
            # Unidades en Resguardo (Fuera de Sede) (Usa el nuevo flag EN_RESGUARDO_SECUNDARIO_FLAG)
            unidades_resguardo_fuera_sede = df_data_original['EN_RESGUARDO_SECUNDARIO_FLAG'].sum()
            
            # Unidades en Vertedero (¡NUEVO!)
            unidades_en_vertedero = df_data_original['EN_VERTEDERO_FLAG'].sum()
            
            # Unidades Falla GPS (Usa el nuevo flag ES_FALLA_GPS_FLAG)
            unidades_falla_gps = df_data_original['ES_FALLA_GPS_FLAG'].sum()
            
            # INICIO DEL DESPLEGABLE DE ESTADÍSTICAS
            with st.expander("📊 **Estadísticas de la Flota**", expanded=True):
                # Renderizado (usando la función definida fuera del loop)
                st.markdown(format_metric_line("Total Flota", total_unidades), unsafe_allow_html=True)
                st.markdown("---")
                st.markdown(format_metric_line("Estado Operacional", is_section_title=True), unsafe_allow_html=True)
                st.markdown(format_metric_line("Encendidas", unidades_encendidas), unsafe_allow_html=True)
                st.markdown(format_metric_line("Apagadas (Ruta)", unidades_apagadas), unsafe_allow_html=True)
                st.markdown("---")
                st.markdown(format_metric_line("Ubicación Crítica", is_section_title=True), unsafe_allow_html=True)
                
                # METRICA 3: EN VERTEDERO
                st.markdown(format_metric_line("En Vertedero", unidades_en_vertedero), unsafe_allow_html=True)
                
                st.markdown("---")
                st.markdown(format_metric_line("Resguardo y Fallas", is_section_title=True), unsafe_allow_html=True)
                
                # METRICA 1: EN SEDE
                st.markdown(format_metric_line("En Sede", unidades_en_sede), unsafe_allow_html=True)
                
                # METRICA 2: RESGUARDO FUERA DE SEDE
                st.markdown(format_metric_line("Resguardo (F. Sede)", unidades_resguardo_fuera_sede), unsafe_allow_html=True)
                
                # METRICA 4: FALLA GPS
                st.markdown(format_metric_line("Falla GPS", unidades_falla_gps), unsafe_allow_html=True)
            # FIN DEL DESPLEGABLE
            
            # --- RENDERIZADO DE DEBUG Y HORA ---
            with debug_status_placeholder.container():
                hora_actual = obtener_hora_venezuela().strftime('%Y-%m-%d %H:%M:%S')
                
                st.markdown(
                    f'<div style="text-align: center; color: #888888; margin-top: 15px; font-size: 0.8em;">'
                    f'Última actualización:<br><strong>{hora_actual} VET</strong>'
                    f'</div>', 
                    unsafe_allow_html=True
                )
        else:
             metricas_placeholder.empty()
             debug_status_placeholder.empty()
        
    # RENDERIZADO DEL LOG DE EVENTOS
    with log_placeholder.container():
        if st.session_state['log_historial']:
            st.markdown("---")
            st.markdown("#### 📜 Historial de Eventos")
            # Mostrar solo los 10 más recientes
            for log_entry in st.session_state['log_historial'][:10]:
                st.info(log_entry)
            st.markdown("---")
        else:
            log_placeholder.empty()

    # --- Actualizar el Contenedor Principal (Tarjetas) ---
    with placeholder_main_content.container():
        st.markdown(
    f"<h2 id='main-title'>Rastreo GPS - Flota {flota_a_usar}</h2>", 
    unsafe_allow_html=True
)
        st.markdown("---")
        
        st.subheader(f"{filtro_descripcion} - ({len(df_data_mostrada)})")

        if is_fallback:
            causa_display = df_data_original['UBICACION_TEXTO'].iloc[0].split(' - ')[1]
            st.error(f"🚨 **ERROR CRÍTICO DE CONEXIÓN/DATOS** 🚨")
            st.warning(f"La API de Foresight GPS no devolvió datos. Razón: **{causa_display}**.")
            
        elif df_data_mostrada.empty:
             st.info(f"No hay unidades que cumplan el filtro **'{filtro_descripcion}'** para la flota **{flota_a_usar}** en este momento.")

        else:
            
            # COMIENZO DEL RENDERIZADO DE TARJETAS
            
            COLUMNS_PER_ROW = 5
            rows = [df_data_mostrada[i:i + COLUMNS_PER_ROW] for i in range(0, len(df_data_mostrada), COLUMNS_PER_ROW)]

            for row_index, row_data in enumerate(rows):
                cols = st.columns(COLUMNS_PER_ROW)
                
                for col_index, row_tuple in enumerate(row_data.iterrows()):
                    with cols[col_index]:
                        
                        row = row_tuple[1] 

                        nombre_unidad_display = row['UNIDAD'].split('-')[0] if '-' in row['UNIDAD'] else row['UNIDAD']
                        velocidad_formateada = f"{row['VELOCIDAD']:.0f}"
                        card_style = row['CARD_STYLE']
                        estado_ignicion = row['IGNICION']
                        velocidad_float = row['VELOCIDAD']
                        stop_duration = row['STOP_DURATION_MINUTES']
                        
                        estado_display = estado_ignicion 
                        color_velocidad = "white"
                        
                        # Determinar si la unidad NO está en ninguna zona crítica
                        is_out_of_hq_status = not (row['EN_SEDE_FLAG'] or row['EN_RESGUARDO_SECUNDARIO_FLAG'] or row['EN_VERTEDERO_FLAG'] or row['ES_FALLA_GPS_FLAG'])
                        
                        # Lógica de Precedencia: Falla GPS > Parada Larga > Exceso de Velocidad
                        
                        if row['ES_FALLA_GPS_FLAG']:
                            color_velocidad = "black" 
                            
                        else:
                            # Resaltado visual para Parada Larga
                            if stop_duration > STOP_THRESHOLD_MINUTES and velocidad_float < 1.0 and is_out_of_hq_status:
                                parada_display = f"Parada Larga 🛑: {stop_duration:.0f} min"
                                card_style = "background-color: #FFC107; padding: 15px; border-radius: 5px; color: black; margin-bottom: 0px;" 
                                estado_display = parada_display 
                                color_velocidad = "black"
                                
                            # Resaltado visual para Exceso de Velocidad
                            elif velocidad_float > SPEED_THRESHOLD_KPH + 4.0: 
                                color_velocidad = "#D32F2F" # ROJO (Crítico)
                                estado_display = "EXCESO VELOCIDAD 🚨"
                            elif velocidad_float >= SPEED_THRESHOLD_KPH:
                                color_velocidad = "#FF9800" # NARANJA (Alerta)
                                estado_display = "Alerta Velocidad ⚠️" 

                        # Estructura del card HTML
                        st.markdown(f'<div style="{card_style}">', unsafe_allow_html=True)
                        st.markdown(
                            f'<p style="text-align: center; margin-bottom: 10px; margin-top: 0px;">'
                            f'<span style="background-color: rgba(0,0,0,0.3); padding: 5px 10px; border-radius: 5px; font-size: 1.5em; font-weight: 900;">'
                            f'{nombre_unidad_display}'
                            f'</span>'
                            f'</p>',
                            unsafe_allow_html=True
                        )
                        # El texto de la velocidad debe ser negro si el fondo es claro (Vertedero o Falla GPS)
                        final_text_color = "black" if COLOR_VERTEDERO == "#FCC6BB" and row['EN_VERTEDERO_FLAG'] else color_velocidad
                        if row['ES_FALLA_GPS_FLAG']:
                            final_text_color = "black"
                            
                        st.markdown(
                            f'<p style="display: flex; align-items: center; justify-content: center; font-size: 1.9em; font-weight: 900; margin-top: 0px;">'
                            f'📍 <span style="margin-left: 8px; color: {final_text_color};">{velocidad_formateada} Km</span>'
                            f'</p>',
                            unsafe_allow_html=True
                        )
                        st.markdown(f'<p style="font-size: 1.0em; margin-top: 0px; opacity: 1.1; text-align: center; margin-bottom: 0px;">{estado_display}</p>', unsafe_allow_html=True)
                        st.markdown('</div>', unsafe_allow_html=True)

                        # Botón de Ubicación
                        with st.expander("Detalles ℹ️", expanded=False):
                            stop_timedelta_card = row['STOP_DURATION_TIMEDELTA']
                            tiempo_parado_display = f"{int(stop_timedelta_card.total_seconds() // 60)} min {int(stop_timedelta_card.total_seconds() % 60):02} seg"
                            
                            st.caption(f"Tiempo Parado: **{tiempo_parado_display}**") 
                            
                            falla_motivo = row.get('FALLA_GPS_MOTIVO')
                            last_report_display = row.get('LAST_REPORT_TIME_DISPLAY')
                            
                            if falla_motivo:
                                st.error(
                                    f"🚫 **Motivo Falla GPS:** {falla_motivo}\n\n"
                                    f"🕒 **Último Reporte:** {last_report_display}"
                                )
                            
                            st.caption(f"Estado GPS: **{estado_ignicion}**")
                            st.caption(f"Dirección: **{row['UBICACION_TEXTO']}**")
                            
                            if not falla_motivo:
                                st.caption(f"Último Reporte: **{last_report_display}**")
                                
                            st.caption(f"Coordenadas: ({row['LONGITUD']:.4f}, {row['LATITUD']:.4f})\r\n")
                        
                st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)
            
    st.markdown("---")
    
    # USO DEL PARÁMETRO DINÁMICO DE PAUSA
    time.sleep(TIME_SLEEP)
