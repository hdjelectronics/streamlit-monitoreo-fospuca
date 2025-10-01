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
# MODIFICACIÓN CRÍTICA: Importar datetime, timedelta y timezone de forma explícita
from datetime import datetime, timedelta, timezone 


# --- CONFIGURACIÓN DE ZONA HORARIA Y LÓGICA DE TIEMPO ---

# Definir la zona horaria de Venezuela (VET = UTC-4)
VENEZUELA_TZ = timezone(timedelta(hours=-4))
# Formato de fecha y hora requerido para parsear 'LastReportTime': 'Sep 30 2025 12:57PM'
TIME_FORMAT = '%b %d %Y %I:%M%p'
COLOR_FALLA_GPS = "#AAAAAA" # Gris para Falla GPS

def obtener_hora_venezuela() -> datetime:
    """Retorna el objeto datetime con la hora actual en la Zona Horaria de Venezuela (VET)."""
    # Se crea un objeto aware (consciente) de la zona horaria.
    return datetime.now(VENEZUELA_TZ)

def verificar_falla_gps(unidad_data: Dict[str, Any], hora_venezuela: datetime) -> Dict[str, Any]:
    """
    Evalúa si la unidad debe cambiar a estado 'Falla GPS' y actualiza el diccionario de datos,
    incluyendo el motivo específico de la falla y la hora del último reporte.
    
    :param unidad_data: Diccionario de datos de la unidad (debe contener 'LastReportTime' y 'ignition').
    :param hora_venezuela: Objeto datetime con la hora actual de Venezuela.
    :return: Diccionario de la unidad con el estado 'Falla GPS' y estilo actualizado si aplica.
    """
    last_report_str = unidad_data.get('LastReportTime')
    ignicion_raw = unidad_data.get("ignition", "false").lower()
    estado_ignicion = ignicion_raw == "true"
    
    if not last_report_str:
        return unidad_data # No se puede verificar la falla sin un reporte de tiempo

    try:
        # 1. Parsear LastReportTime y ASIGNARLE la TZ de Venezuela.
        last_report_dt = datetime.strptime(last_report_str, TIME_FORMAT).replace(tzinfo=VENEZUELA_TZ)
    except ValueError:
        # En caso de error de formato, retornamos los datos originales sin cambio.
        return unidad_data 

    # 2. Calcular la diferencia de tiempo
    diferencia_tiempo: timedelta = hora_venezuela - last_report_dt
    
    # 3. Definir los umbrales de tiempo
    UMBRAL_ENCENDIDA = timedelta(minutes=5)
    # 🚨 MODIFICACIÓN DE UMBRAL (1 hora y 10 minutos)
    UMBRAL_APAGADA = timedelta(hours=1, minutes=10)
    
    # 4. Aplicar la lógica de Falla GPS
    es_falla_gps = False
    motivo_falla = ""
    
    if estado_ignicion: # Unidad Encendida (Ignition = True)
        # Condición: Encendida Y diferencia > 5 minutos
        if diferencia_tiempo > UMBRAL_ENCENDIDA:
            es_falla_gps = True
            # Calcular minutos sin reportar
            minutos_sin_reportar = diferencia_tiempo.total_seconds() / 60.0
            motivo_falla = f"Encendida **{minutos_sin_reportar:.0f} minutos** sin reportar (Umbral 5 min)."
    else: # Unidad Apagada (Ignition = False)
        # Condición: Apagada Y diferencia > 1 hora y 10 minutos
        if diferencia_tiempo > UMBRAL_APAGADA:
            es_falla_gps = True
            # Calcular horas/minutos sin reportar para el motivo
            segundos_sin_reportar = diferencia_tiempo.total_seconds()
            horas = int(segundos_sin_reportar // 3600)
            minutos = int((segundos_sin_reportar % 3600) // 60)
            
            tiempo_display = ""
            if horas > 0:
                tiempo_display += f"{horas} hora(s)"
            if minutos > 0 or (horas == 0 and minutos == 0): # Asegurar que se muestre algo si es justo el umbral
                tiempo_display += f" y {minutos} minuto(s)" if horas > 0 else f"{minutos} minuto(s)"

            motivo_falla = f"Apagada **{tiempo_display.strip()}** sin reportar (Umbral 1h 10min)."
            
    # 5. Aplicar el estado y estilo si es Falla GPS
    if es_falla_gps:
        unidad_data['Estado_Falla_GPS'] = True # Bandera para fácil referencia
        # 🚨 CAMBIO AÑADIDO: Guardar el motivo de la falla GPS 🚨
        unidad_data['FALLA_GPS_MOTIVO'] = motivo_falla 
        # 🚨 NUEVO CAMBIO AÑADIDO: Guardar el último tiempo de reporte (string original)
        unidad_data['LAST_REPORT_TIME_FOR_DETAIL'] = last_report_str 
        # Sobrescribimos el estado en el diccionario antes de que sea procesado por la lógica de sede/resguardo
        unidad_data['IGNICION_OVERRIDE'] = "Falla GPS 🚫"
        unidad_data['CARD_STYLE_OVERRIDE'] = f"background-color: {COLOR_FALLA_GPS}; padding: 15px; border-radius: 5px; color: black; margin-bottom: 0px;"

    return unidad_data


# --- 🚨 CONFIGURACIÓN DE AUDIO Y BASE64 (EJECUCIÓN ÚNICA AL INICIO) 🚨 ---

def obtener_audio_base64(audio_path):
    """Codifica el archivo de audio en una cadena Base64 al inicio."""
    # Nota: Asegúrate de que los archivos de audio existan.
    if not os.path.exists(audio_path):
        st.error(f"Error Crítico: No se encontró el archivo de audio '{audio_path}'.")
        return None
    try:
        with open(audio_path, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except Exception as e:
        st.error(f"Error al codificar el audio: {e}")
        return None

# 🚨 EJECUCIÓN DEL BASE64 UNA SOLA VEZ AL INICIO 🚨
# **Asegúrate de cambiar los nombres de los archivos si es necesario.**
# Nota: Si no tienes los archivos 'parada.mp3' y 'velocidad.mp3', esta parte fallará.
# Si no usas audio, puedes comentar estas dos líneas.
# AUDIO_BASE64_PARADA = obtener_audio_base64("parada.mp3") 
# AUDIO_BASE64_VELOCIDAD = obtener_audio_base64("velocidad.mp3") 
AUDIO_BASE64_PARADA = None # Placeholder si no se usa audio
AUDIO_BASE64_VELOCIDAD = None # Placeholder si no se usa audio

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
        const audio = document.getElementById('alerta_audio_tag_{unique_id}');
        if (audio) {{
            audio.volume = 1.0; 
            audio.load();
            audio.play().catch(error => console.warn('Bloqueo de Autoplay: ', error));
        }}
    </script>
    """
    st.markdown(audio_html, unsafe_allow_html=True)


# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Monitoreo GPS - FOSPUCA",
    layout="wide",
    initial_sidebar_state="expanded"
)
# --- INYECCIÓN DE CSS ---
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
    st.error("ERROR CRÍTICO: No se pudo encontrar la clave 'basic_auth_header' en st.secrets.")
    st.info("Asegúrese de configurar el archivo '.streamlit/secrets.toml' o la configuración de 'Secrets' en la nube.")
    st.stop() 


# --- CONFIGURACIÓN MULTI-FLOTA (Se mantiene la misma configuración) ---
FLOTAS_CONFIG = {   
    
    "Baruta": {
        "ids": "330882,319393,304624,314780,300968,314766,328710,314841,323056,319338,310625,334716,303071,322990,307999,305206,324944,323042,314827,323512,301440,324653,301347,301411,325762,314820,331491,330249,335231,329771,330141,328587,330247,330980,330243,329081,330220,325271,330226,330918,331490,331498,323009,303487,313336,328626,326027,314855,328847,301295,310382,324721,309730,335216,328623",
        "lat_sede": 10.420910,
        "lon_sede": -66.933790
    },
    "Chacao": {
        "ids": "324551,323134,324723,322999,305462,324722,309721,314824,331492,325270,334710,334683,335249",
        "lat_sede": 10.487110,
        "lon_sede": -66.867390
    },
    "El Tigre": {
        "ids": "308193,303031,303048,308204,328483,308221,328469,303039,308185,308189,308187,309229,305419,305445,308208,308222,335091,308228,314762",
        "lat_sede": 8.896940,
        "lon_sede": -64.213300
    },
    "Girardot": {
        "ids": "330238,330866,331233,330886,331442,328609,331231,328968,330225,330888,329769,314811,329084,328484,328473,328462,328443,328493,329083,328477,319360,319363,319324,319346,319321,328653,328614,324946",
        "lat_sede": 10.220410,
        "lon_sede": -67.577930
    },
    "Guayana": {
        "ids": "309729,308046,309715,309705,323092,310632,309701,309713,334690,325267,308179,303054,310621,310649,310541,310633,322992,319408,319311,309691,309731,310496,325264,310652,330909,314828,330276,310671,318796,310478,310614,318778,310551,310533,309726,310630,318803,310333,309724,319326,310622,310480,310550,328703,314834,309228,303080,318816,318831,318847,330856,328846",
        "lat_sede": 8.248220,  
        "lon_sede": -62.819900
    },
    "Hatillo": {
        "ids": "310616,314795,314776,314833,319395,305415,309255,309249,310336,318804,328456,331914,328482,331912,328643,333203,314823,328646,330858,324950,328705,319373,310530,328611,334709,314772,327390,309737",
        "lat_sede": 10.420870,  
        "lon_sede": -66.864310
    },
    "Iribarren": {
        "ids": "319388,307296,307321,328704,307291,307338,307327,307325,309693,307289,308225,307303,307311,308191,319398,307322,307332,307340,319382,319411,319417,319404,319308,305410,314831,309740,314839,309706,323078,309250,328467,309230,323049,310596,310626,323041,328502,330887,308019",
        "lat_sede": 10.076970,
        "lon_sede": -69.352470
    },
    "Maneiro": {
        "ids": "328601,307300,307317,307301,301893,310389,310494,310629,318795,310460,334708,319412,309599,328471,330208",
        "lat_sede": 10.9523,
        "lon_sede": -63.8630
    },
    "San Diego": {
        "ids": "302005,335250,322991,301848,323144,301931,301873,301975,301891,308190,314809,319378,307304",
        "lat_sede": 10.191370,
        "lon_sede": -67.961420
    },
    
}
# --- DISTANCIA DE LA SEDE (PARA ASUMIR EN SEDE) (100MTS fijos) ---
# 🚨 VALOR MODIFICADO: 0.1 KM (100 metros) 🚨
PROXIMIDAD_KM = 0.1

# --- 🚨 NUEVOS RESGUARDOS FUERA DE SEDE (ACTUALIZADO) 🚨 ---
# 🚨 COLOR REEMPLAZADO POR EL CÓDIGO (191452) 🚨
COLOR_RESGUARDO_SECUNDARIO = "#191452" 

# Lista de coordenadas de resguardo secundario [Latitud, Longitud]
COORDENADAS_RESGUARDO_SECUNDARIO = [
    # Ubicación Anterior 1
    [10.975240, -63.836690],
    # Ubicación Anterior 2
    [10.998340, -63.799760],
    # Nueva Ubicación Añadida
    [11.004680, -63.798240] 
]
# ----------------------------------------------------------------------

# --- ENCABEZADO DE AUTENTICACION ---
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": BASIC_AUTH_HEADER
}


# --- CALCULO DE DISTANCIA (FUNCIÓN HAVERSINE) ---
def haversine(lat1, lon1, lat2, lon2):
    """Calcula la distancia Haversine entre dos puntos en la Tierra (en km)."""
    R = 6371  
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = np.sin(dlat/2.0)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2.0)**2
    c = 2 * np.arcsin(np.sqrt(a))
    return R * c

# --- FUNCIÓN AUXILIAR PARA ESTILOS ---
def get_card_style(ignicion_status, speed):
    """Determina el estilo de la tarjeta basado en el estado de ignición y velocidad."""
    
    # 1. ESTADO POR DEFECTO: Encendida en Ruta (Verde)
    bg_color = "#4CAF50" # Verde
    text_color = "white"

    if "Resguardo (Sede)" in ignicion_status:
        bg_color = "#337ab7"
        text_color = "white"
        
    elif "Encendida (Sede)" in ignicion_status:
        bg_color = "#B37305"  
        text_color = "white"
        
    elif "Apagada" in ignicion_status:
        bg_color = "#D32F2F"  
        text_color = "white"

    # AÑADIDO: Lógica de estilo para Resguardo Fuera de Sede
    elif "Resguardo (Fuera de Sede)" in ignicion_status:
        bg_color = COLOR_RESGUARDO_SECUNDARIO
        text_color = "white"
    
    # NUEVA LÓGICA: Estilo para Falla GPS (gris con texto negro para el card)
    elif "Falla GPS" in ignicion_status:
        bg_color = COLOR_FALLA_GPS
        text_color = "black"
        
    style = (
        f"background-color: {bg_color}; "
        f"padding: 15px; "
        f"border-radius: 5px; "
        f"color: {text_color}; "
        f"margin-bottom: 0px;"
    )
    return style

# --- CALLBACK MODIFICADO PARA DESCARTE (PARADA LARGA) ---
def descartar_alerta_stop(unidad_id_a_descartar):
    """
    Marca la alerta de Parada Larga como 'descartada' y DESACTIVA la bandera de audio.
    """
    st.session_state['alertas_descartadas'][unidad_id_a_descartar] = True
    st.session_state['reproducir_audio_alerta'] = False 


# --- DESCARTAR EXCESO DE VELOCIDAD ---
def descartar_alerta_velocidad(unidad_id_a_descartar):
    """
    Marca la alerta de Exceso de Velocidad como 'descartada' y DESACTIVA la bandera de audio.
    """
    st.session_state['alertas_velocidad_descartadas'][unidad_id_a_descartar] = True
    # Desactivamos el audio al aceptar para que se apague en el siguiente ciclo.
    st.session_state['reproducir_audio_velocidad'] = False


# --- DATOS DE RESPALDO (FALLBACK) ---
def get_fallback_data(error_type="Conexión Fallida"): 
    """Genera una estructura de datos de una sola fila para señalizar el error en el main loop."""
    
    return pd.DataFrame([{
        "UNIDAD": "FALLBACK", 
        "UNIT_ID": "FALLBACK_ID",
        "IGNICION": "N/A", 
        "VELOCIDAD": 0, 
        "LATITUD": 0, 
        "LONGITUD": 0, 
        "UBICACION_TEXTO": f"FALLBACK - {error_type}", 
        "CARD_STYLE": "background-color: #D32F2F; padding: 15px; border-radius: 5px; color: white; margin-bottom: 0px;",
        # Campos añadidos para evitar error al crear el DataFrame:
        "FALLA_GPS_MOTIVO": None,
        "LAST_REPORT_TIME_DISPLAY": None 
    }])

# --- FUNCIÓN DE OBTENCIÓN Y FILTRADO DE DATOS DINÁMICA (TTL de 5 segundos) ---
@st.cache_data(ttl=5)
def obtener_datos_unidades(nombre_flota: str, config: Dict[str, Any]):
    """Obtiene y limpia los datos de la API, aplicando la lógica de color por estado/sede, incluyendo Falla GPS."""
    
    flota_data = config.get(nombre_flota, config["Maneiro"])
    LAT_SEDE = flota_data["lat_sede"]
    LON_SEDE = flota_data["lon_sede"]

    num_ids = len(flota_data["ids"].split(','))
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
        "pagesize": num_ids + 5, 
        "prefix": True
    }
    
    try:
        response = requests.post(API_URL, json=payload, headers=HEADERS, timeout=5)
        response.raise_for_status()  
        data = response.json()
        
        lista_unidades = data.get("ForesightFlexAPI", {}).get("DATA", [])
        
        if not lista_unidades:
            return get_fallback_data("Lista de Unidades Vacía (Revisa IDs)")
        
        # --- Obtener la hora de Venezuela antes del bucle ---
        hora_actual_ve = obtener_hora_venezuela()

        # --- PROCESAMIENTO DE DATOS REALES ---
        datos_filtrados = []
        for unidad in lista_unidades:
            
            # 🚨 1. APLICAR LÓGICA DE FALLA GPS (sobrescribe los datos en caso de falla) 🚨
            unidad_con_falla_check = verificar_falla_gps(unidad, hora_actual_ve)
            
            # Bandera para saber si el estado fue cambiado por Falla GPS
            es_falla_gps = unidad_con_falla_check.get('Estado_Falla_GPS', False)
            
            # Extraer campos necesarios (los raw del API, o los override si Falla GPS es True)
            ignicion_raw = unidad_con_falla_check.get("ignition", "false").lower()
            velocidad = float(unidad_con_falla_check.get("speed_dunit", "0"))
            lat = float(unidad_con_falla_check.get("ylat", 0))
            lon = float(unidad_con_falla_check.get("xlong", 0))
            unit_id = unidad_con_falla_check.get("unitid", unidad_con_falla_check.get("name", "N/A")) 

            ignicion_estado = ignicion_raw == "true"
            
            falla_gps_motivo = None # Valor por defecto
            # Obtener el tiempo del último reporte (string original del API)
            last_report_time_display = unidad_con_falla_check.get('LastReportTime', 'N/A')
            
            if es_falla_gps:
                # Si es Falla GPS, usamos el estado y el estilo sobrescrito
                estado_final_display = unidad_con_falla_check['IGNICION_OVERRIDE']
                card_style = unidad_con_falla_check['CARD_STYLE_OVERRIDE']
                # 🚨 CAMBIO AÑADIDO: Recuperar el motivo de la falla GPS 🚨
                falla_gps_motivo = unidad_con_falla_check.get('FALLA_GPS_MOTIVO')
                # 🚨 NUEVO CAMBIO: Recuperar la hora del reporte para el display, guardada en verificar_falla_gps
                last_report_time_display = unidad_con_falla_check.get('LAST_REPORT_TIME_FOR_DETAIL', last_report_time_display)
            else:
                # --- LÓGICA EXISTENTE DE ESTADO (IGNICIÓN/SEDE/RESGUARDO) ---
                
                # --- CÁLCULO DE DISTANCIA A LA SEDE PRINCIPAL ---
                distancia = haversine(lat, lon, LAT_SEDE, LON_SEDE)
                en_sede = distancia <= PROXIMIDAD_KM
                
                # --- CÁLCULO DE DISTANCIA A LAS UBICACIONES DE RESGUARDO SECUNDARIO ---
                en_resguardo_secundario = False
                for resguardo_coords in COORDENADAS_RESGUARDO_SECUNDARIO:
                    lat_res, lon_res = resguardo_coords
                    # El umbral de PROXIMIDAD_KM se usa aquí también
                    distancia_resguardo = haversine(lat, lon, lat_res, lon_res)
                    if distancia_resguardo <= PROXIMIDAD_KM:
                        en_resguardo_secundario = True
                        break
                # -----------------------------------------------------------------------------------
                
                estado_final_display = "Apagada ❄️" 
                color_fondo = "#D32F2F" 
                
                if ignicion_estado:
                    if en_sede:
                        estado_final_display = "Encendida (Sede) 🔥"; color_fondo = "#B37305"
                    else:
                        estado_final_display = "Encendida 🔥"; color_fondo = "#4CAF50"
                else:
                    if en_sede:
                        estado_final_display = "Resguardo (Sede) 🛡️"; color_fondo = "#337ab7"
                    # --- CONDICIÓN DE ESTADO ---
                    elif en_resguardo_secundario:
                        estado_final_display = "Resguardo (Fuera de Sede) 🛡️"; color_fondo = COLOR_RESGUARDO_SECUNDARIO
                    # ---------------------------------
                
                card_style = "background-color: {}; padding: 15px; border-radius: 5px; color: white; margin-bottom: 0px;".format(color_fondo)

            datos_filtrados.append({
                "UNIDAD": unidad_con_falla_check.get("name", "N/A"),
                "UNIT_ID": unit_id, 
                "IGNICION": estado_final_display, # Ya actualizado con Falla GPS si aplica
                "VELOCIDAD": velocidad,
                "LATITUD": lat,
                "LONGITUD": lon,
                "UBICACION_TEXTO": unidad_con_falla_check.get("location", "Dirección no disponible"),
                "CARD_STYLE": card_style,
                # 🚨 CAMBIO AÑADIDO: Incluir el motivo en el DataFrame 🚨
                "FALLA_GPS_MOTIVO": falla_gps_motivo,
                # 🚨 NUEVO CAMBIO: Incluir la hora del reporte en el DataFrame
                "LAST_REPORT_TIME_DISPLAY": last_report_time_display 
            })
        
        return pd.DataFrame(datos_filtrados)

    except requests.exceptions.RequestException as e:
        error_msg = f"API Error: {e}" if not hasattr(e, 'response') else f"HTTP Error: {e.response.status_code}"
        print(f"❌ Error de Conexión/API: {error_msg}")
        return get_fallback_data("Error de Conexión/API")


# --- FUNCIÓN PARA MOSTRAR LA LEYENDA DE COLORES EN EL SIDEBAR ---
def display_color_legend():
    """Muestra la leyenda de colores de las tarjetas de estado de forma compacta (sin título, ya que lo pone el expander)."""
    
    # Definiciones de colores y estados de la lógica principal (NOMBRES ACTUALIZADOS)
    COLOR_MAP = {
        "#4CAF50": "Encendida en Ruta",             # Verde
        "#D32F2F": "Apagada",                      # Rojo
        "#337ab7": "Resguardo (Sede)",             # Azul Oscuro (Resguardo Sede Apagada)
        COLOR_RESGUARDO_SECUNDARIO: "Resguardo (F. Sede)", # Azul Marino (#191452)
        "#B37305": "Encendida (Sede)",             # Naranja Oscuro (Encendida Sede)
        "#FFC107": "Parada Larga",                 # Amarillo (Sobrepasa el umbral de parada)
        COLOR_FALLA_GPS: "Falla GPS",              # <-- NUEVA LEYENDA
    }

    # Dividir en dos columnas para mayor compacidad
    cols_legend = st.columns(2)
    col_index = 0
    
    for color, description in COLOR_MAP.items():
        with cols_legend[col_index % 2]:
            legend_html = f"""
            <div style="display: flex; align-items: center; margin-bottom: 3px;">
                <div style="width: 14px; height: 14px; background-color: {color}; border-radius: 3px; margin-right: 5px; border: 1px solid #ddd;"></div>
                <span style="font-size: 0.85em;">{description}</span>
            </div>
            """
            st.markdown(legend_html, unsafe_allow_html=True)
        col_index += 1
# -------------------------------------------------------------------------------------


# --- INICIALIZACIÓN DEL ESTADO DE SESIÓN ---
if 'flota_seleccionada' not in st.session_state:
    st.session_state['flota_seleccionada'] = None 
if 'filtro_sede' not in st.session_state:
    st.session_state['filtro_sede'] = False

# 🚨 NUEVA FUNCIÓN COMPARTIDA: Almacena el estado de parada globalmente (Shared State) 🚨
@st.cache_resource(ttl=None) 
def get_global_stop_state() -> Dict[str, Any]:
    """Retorna un diccionario de estado que es único y compartido por todos los usuarios (Global State)."""
    # Esta función se ejecuta UNA SOLA VEZ en el servidor.
    return {}

# Inicializar y obtener la referencia al estado global (la inicialización previa en st.session_state fue eliminada)
get_global_stop_state()
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
    # 1. SELECCIÓN DE FLOTA (TITLE & SELECTOR)
    # 🚨 LÍNEA MODIFICADA PARA CENTRAR EL TEXTO 🚨
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
        label_visibility="collapsed" # Compactar: Ocultar el label del selectbox
    )
    
    if flota_actual == flota_keys[0]:
        st.session_state['flota_seleccionada'] = None
    else:
        st.session_state['flota_seleccionada'] = flota_actual

    # 2. FILTRO EN RUTA
    if st.session_state['flota_seleccionada']:
        st.checkbox(
            "**Unidades en Ruta** (Excluir Resguardo)", 
            key="filtro_sede",
            on_change=actualizar_dashboard 
        )

    # 3. LEYENDA DE COLORES (Ubicación fija)
    # 🚨 CAMBIO: Se envuelve la llamada en un st.expander con expanded=False 🚨
    with st.expander("##### Leyenda de Estados 🎨", expanded=False):
        display_color_legend() 

    # 4. Este placeholder contendrá todas las métricas, el debug y la hora.
    # El contenido de este placeholder se renderizará más abajo, pero la variable debe existir aquí.
    metricas_placeholder = st.empty() 
    
    # 5. PLACEHOLDER ALERTA PARADA LARGA
    alerta_stop_placeholder = st.empty()
    st.markdown("---")
    
    # 6. PLACEHOLDER ALERTA EXCESO DE VELOCIDAD
    alerta_velocidad_placeholder = st.empty()
    st.markdown("---")

    # 7. PLACEHOLDER PARA EL DEBUG Y HORA (AHORA FUERA DEL EXPANDER)
    debug_status_placeholder = st.empty()

# === BUCLE PRINCIPAL (while True) - Lógica Completa ===

placeholder = st.empty()

# NUEVO PLACEHOLDER para el Historial de Logs
log_placeholder = st.empty() 

STOP_THRESHOLD_MINUTES = 10
SPEED_THRESHOLD_KPH = 70


while True:
    
    flota_a_usar = st.session_state['flota_seleccionada'] 

    # --- CONDICIÓN CRÍTICA: NO EJECUTAR SI NO HAY FLOTA SELECCIONADA ---
    if not flota_a_usar:
        with placeholder.container():
            st.markdown(
    f"<h2 id='main-title'>Rastreo GPS - Monitoreo GPS - FOSPUCA</h2>", 
    unsafe_allow_html=True
)
            st.markdown("---")
            st.info("👋 Por favor, **seleccione una Flota** en el panel lateral (Sidebar) para comenzar el monitoreo en tiempo real.")
            
        # Limpiar Placeholders
        with alerta_velocidad_placeholder.container(): st.empty()
        with alerta_stop_placeholder.container(): st.empty()
        with metricas_placeholder.container(): st.empty()
        with debug_status_placeholder.container(): st.empty() # Limpiar el nuevo placeholder de debug
        with log_placeholder.container(): st.empty() 
            
        time.sleep(1) 
        continue 
    # --------------------------------------------------------------------------

    # Obtener datos (se usa el caché para evitar lentitud)
    df_data_original = obtener_datos_unidades(flota_a_usar, FLOTAS_CONFIG)
    
    is_fallback = "FALLBACK" in df_data_original["UNIDAD"].iloc[0]
    
    
    # -- LÓGICA DE DETECCIÓN DE PARADAS LARGAS Y EXCESO DE VELOCIDAD --

    # 🚨 CAMBIO CRUCIAL: Se accede a la referencia ÚNICA y GLOBAL del estado.
    current_stop_state = get_global_stop_state() 
    # Se usa la zona horaria para un manejo consistente, aunque no se muestre
    now = pd.Timestamp.now(tz='America/Caracas') 
    
    df_data_original['STOP_DURATION_MINUTES'] = 0.0
    df_data_original['STOP_DURATION_TIMEDELTA'] = pd.Timedelta(seconds=0) 

    if not is_fallback:
        for index, row in df_data_original.iterrows():
            unidad_id = row['UNIDAD']
            unit_id_api = row['UNIT_ID']
            velocidad = row['VELOCIDAD']
            
            # --- INICIALIZACIÓN DE ESTADO COMPLETO ---
            if unit_id_api not in current_stop_state:
                current_stop_state[unit_id_api] = {
                    'last_move_time': now,
                    'alerted_stop_minutes': None, # Parada Larga state
                    'speed_alert_start_time': None, # Nuevo: Inicio del Exceso de Velocidad
                    'last_recorded_speed': 0.0      # Nuevo: Máxima Velocidad en el evento
                }
                continue 

            last_state = current_stop_state[unit_id_api]
            is_moving = velocidad > 1.0 
            # is_out_of_hq ahora también excluye el nuevo estado "Resguardo (Fuera de Sede)" Y "Falla GPS"
            is_out_of_hq = not ("(Sede)" in row['IGNICION'] or "Resguardo" in row['IGNICION'] or "Falla GPS" in row['IGNICION'])
            is_speeding = velocidad >= SPEED_THRESHOLD_KPH

            # --- LÓGICA DE EXCESO DE VELOCIDAD (START/UPDATE) ---
            if is_speeding and is_out_of_hq:
                if last_state['speed_alert_start_time'] is None:
                    # START: Inicia el evento de exceso de velocidad
                    last_state['speed_alert_start_time'] = now
                
                # UPDATE: Siempre rastrea la velocidad máxima alcanzada
                if velocidad > last_state['last_recorded_speed']:
                    last_state['last_recorded_speed'] = velocidad

            # --- LÓGICA DE EXCESO DE VELOCIDAD (END/LOG) ---
            elif not is_speeding and last_state['speed_alert_start_time'] is not None:
                # END: La unidad ha dejado de exceder la velocidad y un evento estaba activo.
                start_time = last_state['speed_alert_start_time']
                duration_timedelta = now - start_time
                duration_minutes = duration_timedelta.total_seconds() / 60.0
                
                # Registra solo si el exceso duró más de 10 segundos (~0.166 min)
                if duration_minutes >= 0.166: 
                    hora_log = now.strftime('%H:%M:%S')
                    nombre_unidad_display = row['UNIDAD'].split('-')[0] if '-' in row['UNIDAD'] else row['UNIDAD']
                    max_speed_recorded = last_state['last_recorded_speed']
                    
                    # Log message siguiendo el formato solicitado: hora, Unidad, exeso de velocidad, por (minutos), en Direccion
                    log_message = (
                        f"**🟡 {hora_log}** | Unidad: **{nombre_unidad_display}** "
                        f"| Exceso de Velocidad Máx: **{max_speed_recorded:.1f} Km/h** "
                        f"| por: **{duration_minutes:.1f} min** "
                        f"| en Dirección: {row['UBICACION_TEXTO']}"
                    )
                    st.session_state['log_historial'].insert(0, log_message)
                
                # RESET: Limpia el estado de velocidad para un nuevo evento
                last_state['speed_alert_start_time'] = None 
                last_state['last_recorded_speed'] = 0.0

            # --- LÓGICA DE PARADA LARGA (Movimiento Detectado - Log FIN Parada Larga) ---
            if is_moving:
                
                # 🚨 CORRECCIÓN 2 APLICADA: Forzamos la duración de parada a cero en el DataFrame 
                # para que la tarjeta visual se actualice inmediatamente.
                df_data_original.loc[index, 'STOP_DURATION_MINUTES'] = 0.0 
                
                if last_state.get('alerted_stop_minutes'):
                    
                    hora_log = now.strftime('%H:%M:%S')
                    duracion_log = f"{last_state['alerted_stop_minutes']:.1f}"
                    nombre_unidad_display = row['UNIDAD'].split('-')[0] if '-' in row['UNIDAD'] else row['UNIDAD']
                    
                    # Log message Parada Larga (ajustado para incluir 'por:')
                    log_message = (
                        f"**🟢 {hora_log}** | Unidad: **{nombre_unidad_display}** "
                        f"| FIN de Parada Larga, por: **{duracion_log} min** "
                        f"| Ubicación: {row['UBICACION_TEXTO']}"
                    )
                    
                    st.session_state['log_historial'].insert(0, log_message)
                    
                    last_state['alerted_stop_minutes'] = None
                
                last_state['last_move_time'] = now
                
                # Reinicio de estados de alerta al moverse
                if unidad_id in st.session_state['alertas_descartadas']:
                    del st.session_state['alertas_descartadas'][unidad_id]
                if unidad_id in st.session_state['alertas_velocidad_descartadas']:
                    del st.session_state['alertas_velocidad_descartadas'][unidad_id]
                
                # Desactivamos las banderas de reproducción si la unidad se mueve
                if st.session_state.get('reproducir_audio_alerta'):
                     st.session_state['reproducir_audio_alerta'] = False
                if st.session_state.get('reproducir_audio_velocidad'): 
                     st.session_state['reproducir_audio_velocidad'] = False

            else: # Unit is stopped (Lógica de Parada Larga - Actualizar Duración)
                stop_duration_timedelta = now - last_state['last_move_time']
                stop_duration_total_seconds = stop_duration_timedelta.total_seconds()
                stop_duration_minutes = stop_duration_total_seconds / 60.0
                
                df_data_original.loc[index, 'STOP_DURATION_MINUTES'] = stop_duration_minutes
                df_data_original.loc[index, 'STOP_DURATION_TIMEDELTA'] = stop_duration_timedelta
                
                # LÓGICA para marcar una parada larga *activa* (para logearla luego al moverse)
                if stop_duration_minutes > STOP_THRESHOLD_MINUTES and is_out_of_hq:
                    last_state['alerted_stop_minutes'] = stop_duration_minutes
                
            # ❌ CORRECCIÓN 1 APLICADA: Línea eliminada que causaba KeyError.
            # st.session_state['unidades_stop_state'][unit_id_api] = last_state 
    
    # Lógica de Filtrado Condicional
    df_data_mostrada = df_data_original
    filtro_descripcion = "Todas las Unidades"

    if not is_fallback and st.session_state.get("filtro_sede", False):
        # Excluimos Resguardo, Encendida (Sede), Resguardo (Fuera de Sede) Y Falla GPS
        is_en_ruta = ~df_data_original["IGNICION"].str.contains("(Sede)|Resguardo|Falla GPS")
        df_data_mostrada = df_data_original[is_en_ruta].reset_index(drop=True)
        filtro_descripcion = "Unidades Fuera de Sede 🛣️"
    
    # Lógica de Detección y Construcción de Alerta de Parada Larga (Alertas Visibles)
    unidades_en_alerta_stop = pd.DataFrame()
    mensaje_alerta_stop = ""

    if not is_fallback:
        # Se excluyen Resguardo, Sede Y Falla GPS
        todas_las_alertas_stop = df_data_original[
            (df_data_original['STOP_DURATION_MINUTES'] > STOP_THRESHOLD_MINUTES) &
            (~df_data_original["IGNICION"].str.contains("(Sede)|Resguardo|Falla GPS"))
        ].copy()

        unidades_pendientes_stop = [
            uid for uid in todas_las_alertas_stop['UNIDAD'] 
            if st.session_state['alertas_descartadas'].get(uid) != True
        ]

        unidades_en_alerta_stop = todas_las_alertas_stop[
            todas_las_alertas_stop['UNIDAD'].isin(unidades_pendientes_stop)
        ].sort_values(by='STOP_DURATION_MINUTES', ascending=False)
        
        # 🚨 CONTROL DEL AUDIO PARADA: Si hay alertas pendientes Y el audio está apagado, lo activamos 🚨
        if not unidades_en_alerta_stop.empty and st.session_state.get('reproducir_audio_alerta') == False:
             st.session_state['reproducir_audio_alerta'] = True 


        if not unidades_en_alerta_stop.empty:
            total_alertas = len(unidades_en_alerta_stop)
            
            mensaje_alerta_stop += f"**{total_alertas} PARADA LARGA(S) PENDIENTE(S) 🚨**\n\n"
            
            for _, row in unidades_en_alerta_stop.head(5).iterrows():
                nombre_unidad = row['UNIDAD'].split('-')[0]
                total_segundos = row['STOP_DURATION_TIMEDELTA'].total_seconds()
                tiempo_parado = f"{int(total_segundos // 60)}min {int(total_segundos % 60):02}seg" 
                mensaje_alerta_stop += (f"**{nombre_unidad}** ({tiempo_parado}):\n---\n")
    
    # Lógica de Detección de Alerta de Velocidad
    unidades_en_alerta_speed = pd.DataFrame()
    mensaje_alerta_speed = ""

    if not is_fallback:
        # Se excluyen Resguardo, Sede Y Falla GPS
        todas_las_alertas_speed = df_data_original[
            (df_data_original['VELOCIDAD'] >= SPEED_THRESHOLD_KPH) &
            (~df_data_original["IGNICION"].str.contains("(Sede)|Resguardo|Falla GPS"))
        ].copy()

        unidades_pendientes_speed = [
            uid for uid in todas_las_alertas_speed['UNIDAD']
            if st.session_state['alertas_velocidad_descartadas'].get(uid) != True
        ]

        unidades_en_alerta_speed = todas_las_alertas_speed[
            todas_las_alertas_speed['UNIDAD'].isin(unidades_pendientes_speed)
        ].sort_values(by='VELOCIDAD', ascending=False)
        
        # 🚨 CONTROL DEL AUDIO VELOCIDAD: Si hay alertas pendientes Y el audio está apagado, lo activamos 🚨
        if not unidades_en_alerta_speed.empty and st.session_state.get('reproducir_audio_velocidad') == False:
             st.session_state['reproducir_audio_velocidad'] = True


        if not unidades_en_alerta_speed.empty:
            total_alertas = len(unidades_en_alerta_speed)
            mensaje_alerta_speed += f"**{total_alertas} EXCESO DE VELOCIDAD PENDIENTE(S) ⚠️**\n\n"
            
            for _, row in unidades_en_alerta_speed.head(5).iterrows():
                nombre_unidad = row['UNIDAD'].split('-')[0]
                velocidad_formateada = f"{row['VELOCIDAD']:.1f} Km/h"
                estado_critico = "🚨 CRÍTICO" if row['VELOCIDAD'] > 74.0 else "⚠️ ALERTA"
                mensaje_alerta_speed += (f"**{nombre_unidad}** ({estado_critico} a {velocidad_formateada}):\n---\n")
    
    # --- 1. RENDERIZADO DEL TEXT BOX DE ALERTA (PARADA LARGA) ---
    unique_time_id = int(time.time() * 1000) 
    
    with alerta_stop_placeholder.container():
        if not unidades_en_alerta_stop.empty:
            total_alertas_pendientes = len(unidades_en_alerta_stop)
            st.markdown(f"#### 🚨 Alerta de Parada Larga ({total_alertas_pendientes})")
            st.markdown("---")
            
            if st.session_state.get('reproducir_audio_alerta'):
                 reproducir_alerta_sonido(AUDIO_BASE64_PARADA)
                 
            st.warning(mensaje_alerta_stop) 
            
            st.markdown("##### Descartar Paradas:")
            cols_btn = st.columns(3) 
            
            for index, row in unidades_en_alerta_stop.iterrows():
                unidad_id = row['UNIDAD']
                nombre_display = unidad_id.split('-')[0]
                col_index = index % 3
                
                with cols_btn[col_index]:
                    st.button(
                        f"Aceptar: {nombre_display}", 
                        key=f"descartar_stop_{unidad_id}_{unique_time_id}", 
                        on_click=descartar_alerta_stop,
                        args=(unidad_id,),
                        type="primary"
                    )
                    
            def aceptar_todas_paradas():
                for uid in unidades_en_alerta_stop['UNIDAD']:
                    st.session_state['alertas_descartadas'][uid] = True
                st.session_state['reproducir_audio_alerta'] = False
                    
            st.button(
                "Aceptar TODAS las Paradas",
                key=f"descartar_all_stops_{unique_time_id}",
                on_click=aceptar_todas_paradas,
                type="secondary"
            )
        else:
            st.session_state['reproducir_audio_alerta'] = False
            alerta_stop_placeholder.empty()

    # --- 2. RENDERIZADO DEL TEXT BOX DE ALERTA (EXCESO VELOCIDAD) ---
    with alerta_velocidad_placeholder.container():
        if not unidades_en_alerta_speed.empty:
            total_alertas_pendientes_speed = len(unidades_en_alerta_speed)
            st.markdown(f"#### ⚠️ Exceso de Velocidad ({total_alertas_pendientes_speed})")
            st.markdown("---")
            
            if st.session_state.get('reproducir_audio_velocidad'):
                 reproducir_alerta_sonido(AUDIO_BASE64_VELOCIDAD)
            
            st.error(mensaje_alerta_speed) 
            
            st.markdown("##### Descartar Excesos:")
            cols_btn_speed = st.columns(3) 
            
            for index, row in unidades_en_alerta_speed.iterrows():
                unidad_id = row['UNIDAD']
                nombre_display = unidad_id.split('-')[0]
                col_index = index % 3
                
                with cols_btn_speed[col_index]:
                    st.button(
                        f"Aceptar: {nombre_display}",
                        key=f"descartar_speed_{unidad_id}_{unique_time_id}", 
                        on_click=descartar_alerta_velocidad,
                        args=(unidad_id,),
                        type="primary"
                    )
            
            def aceptar_todas_velocidades():
                for uid in unidades_en_alerta_speed['UNIDAD']:
                    st.session_state['alertas_velocidad_descartadas'][uid] = True
                st.session_state['reproducir_audio_velocidad'] = False
                    
            st.button(
                "Aceptar TODAS las Alertas de Velocidad",
                key=f"descartar_all_speed_{unique_time_id}",
                on_click=aceptar_todas_velocidades,
                type="secondary"
            )
        else:
            st.session_state['reproducir_audio_velocidad'] = False
            alerta_velocidad_placeholder.empty()
            
    # --- 3. Actualización de Métricas del Sidebar (FINAL: Títulos sin valor) ---
    with metricas_placeholder.container():
        
        # --- Función para generar la línea de métrica con estilo ---
        def format_metric_line(label, value=None, value_size="1.5rem", is_header=False, is_section_title=False, detail_html=""):
            """Genera el HTML para las métricas con estilo unificado: Etiqueta a la izquierda, Valor a la derecha."""
            
            text_style = "color: white; font-family: 'Consolas', 'Courier New', monospace; font-size: 1rem;"
            
            # 1. Título PRINCIPAL (Estadística de la Flota)
            if is_header:
                label_html = f'<p style="font-size: 1.2rem; font-weight: bold; margin-bottom: 0px;">{label}</p>'
                return f'<div style="border-bottom: 1px solid #444444; margin: 10px 0 10px 0;">{label_html}</div>'
                
            # 2. Título de SECCIÓN (Estado Operacional, Resguardo) - SOLO TEXTO SIN VALOR
            if is_section_title:
                return f'<p style="font-size: 1.1rem; font-weight: bold; margin-bottom: 5px; color: white;">{label}</p>'

            # 3. Métrica Normal (Etiqueta: Valor)
            value_html = f'<span style="font-size: {value_size}; font-weight: bold; color: white;">{value}</span>'
            
            # Contenedor de la métrica
            html_content = f"""
            <p style="{text_style} display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
                <span style="white-space: nowrap;">{label}:</span>
                <span style="display: flex; align-items: baseline;">{value_html} {detail_html}</span>
            </p>
            """
            return html_content

        # --- INICIO DEL RENDERIZADO (SIMULANDO IMAGEN 2) ---
        if not is_fallback:
            # 🚨 CAMBIO: Se envuelve el bloque de estadísticas en un st.expander con expanded=False 🚨
            with st.expander("📊 Estadística de Flota", expanded=False):
            
                # Lógica de cálculo (MISMA LÓGICA DE TU CÓDIGO)
                total_unidades_flota = len(df_data_original) 
                
                # Se excluye Falla GPS del conteo de Resguardo y En Ruta para mayor precisión operativa
                df_operando = df_data_original[~df_data_original["IGNICION"].str.contains("Falla GPS")].copy()
                
                unidades_resguardo_total = df_operando[df_operando["IGNICION"].str.contains(
                    "Resguardo \(Sede\)|Encendida \(Sede\)|Resguardo \(Fuera de Sede\)"
                )].shape[0]
                unidades_en_ruta = df_operando.shape[0] - unidades_resguardo_total
                
                unidades_falla_gps = df_data_original[df_data_original["IGNICION"].str.contains("Falla GPS")].shape[0]
                
                unidades_encendidas_ruta = df_operando[
                    df_operando["IGNICION"].str.contains("Encendida 🔥")
                ].shape[0]
                unidades_apagadas_ruta = df_operando[
                    df_operando["IGNICION"].str.contains("Apagada ❄️")
                ].shape[0]
                unidades_resguardo_sede_apagada = df_operando[df_operando["IGNICION"].str.contains("Resguardo \(Sede\)")].shape[0]
                unidades_resguardo_sede_encendida = df_operando[df_operando["IGNICION"].str.contains("Encendida \(Sede\)")].shape[0]
                unidades_resguardo_fuera = df_operando[df_operando["IGNICION"].str.contains("Resguardo \(Fuera de Sede\)")].shape[0]
                
                total_resguardo_sede = unidades_resguardo_sede_apagada + unidades_resguardo_sede_encendida

                
                # --- RENDERIZADO CON HTML COMPACTO ---
                
                # 1. TÍTULO PRINCIPAL: Estadística de la Flota
                st.markdown(format_metric_line("Estadística de la Flota 🚚", is_header=True), unsafe_allow_html=True)
                
                # Total Unidades de Flota
                st.markdown(format_metric_line("Total Unidades Flota", total_unidades_flota, value_size="2.0rem"), unsafe_allow_html=True)
                st.markdown(format_metric_line("Unidades Falla GPS", unidades_falla_gps), unsafe_allow_html=True) # NUEVA MÉTRICA
                st.markdown('<div style="border-bottom: 1px solid #444444; margin: 10px 0 10px 0;"></div>', unsafe_allow_html=True)
                
                # 2. ESTADO OPERACIONAL (TÍTULO DE SECCIÓN SIN VALOR)
                st.markdown(format_metric_line("Estado Operacional 🔥", is_section_title=True), unsafe_allow_html=True)
                
                # Detalle de Encendidas en Ruta
                delta_encendidas_ruta = f'<span style="color: #4CAF50; font-size: 0.9em; font-weight: bold; margin-left: 10px; white-space: nowrap;">↑ {unidades_encendidas_ruta} Encendidas</span>'

                # Unidades en Ruta
                st.markdown(
                    format_metric_line("Unidades en Ruta", unidades_en_ruta, 
                                    detail_html=delta_encendidas_ruta), 
                    unsafe_allow_html=True
                )
                # Unidades Apagadas en Ruta
                st.markdown(format_metric_line("Unidades Apagadas (Ruta)", unidades_apagadas_ruta), unsafe_allow_html=True)

                st.markdown('<div style="border-bottom: 1px solid #444444; margin: 10px 0 10px 0;"></div>', unsafe_allow_html=True)
                
                # 3. RESGUARDO (TÍTULO DE SECCIÓN SIN VALOR)
                st.markdown(format_metric_line("Resguardo 🛡️", is_section_title=True), unsafe_allow_html=True)
                
                # Total Resguardo Sede (Unidades en HQ, Encendidas o Apagadas)
                st.markdown(format_metric_line("Total Resguardo Sede", total_resguardo_sede), unsafe_allow_html=True)
                
                # Detalle Resguardo Sede
                st.markdown(
                    f'<p style="font-family: monospace; font-size: 0.9rem; color: #aaaaaa; margin-top: -5px; margin-bottom: 5px;">'
                    f'Detalle: {unidades_resguardo_sede_encendida} Encendidas / {unidades_resguardo_sede_apagada} Apagadas.'
                    f'</p>', 
                    unsafe_allow_html=True
                )
                
                # Total Resguardo Fuera de Sede
                st.markdown(format_metric_line("Total Resguardo Fuera Sede", unidades_resguardo_fuera), unsafe_allow_html=True)
                
            st.markdown("---") 
            
            # --- RENDERIZADO DEL DEBUG Y HORA (FUERA DEL EXPANDER) ---
            with debug_status_placeholder.container():
                current_time = now.strftime('%H:%M:%S')
                st.info(f"Última Actualización: **{current_time}**") 
                st.markdown("---")
                st.header("DEBUG API STATUS")
                
                st.success(f"Conexión **OK**. Se recibieron {total_unidades_flota} registros.") 
                if st.session_state.get("filtro_sede", False):
                    st.info(f"Filtro Activo: **{filtro_descripcion}**. Mostrando **{len(df_data_mostrada)}** unidades.")
                
        else:
            # (Lógica de Fallback sin cambios, pero movida al nuevo placeholder)
            with debug_status_placeholder.container():
                causa = df_data_original['UBICACION_TEXTO'].iloc[0].split(' - ')[1]
                st.metric("Total Unidades", "Error")
                st.error(f"❌ API Falló: {causa}")
                st.markdown("---")
                st.info(f"Última Actualización: **{now.strftime('%H:%M:%S')}**") 

    # RENDERIZADO DEL LOG DE EVENTOS
    with log_placeholder.container():
        if st.session_state['log_historial']:
            st.markdown("---")
            st.markdown("#### 📜 Historial de Eventos")
            for log_entry in st.session_state['log_historial'][:10]:
                st.info(log_entry)
            st.markdown("---")
        else:
            log_placeholder.empty()

    # --- Actualizar el Contenedor Principal (Tarjetas) ---
    with placeholder.container():
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
                        
                        # Definimos si está en ruta (excluye Resguardo, Sede Y Falla GPS)
                        is_out_of_hq_status = not ("(Sede)" in estado_ignicion or "Resguardo" in estado_ignicion or "Falla GPS" in estado_ignicion)
                        
                        # Lógica de Precedencia: Falla GPS > Parada Larga > Exceso de Velocidad
                        
                        if "Falla GPS" in estado_ignicion:
                            # Falla GPS ya trae su estilo y display (gris, texto negro en card)
                            color_velocidad = "black" 
                            
                        # Si NO es Falla GPS, verificamos otras alertas:
                        else:
                            # Resaltado visual para Parada Larga (Solo si no es Falla GPS)
                            if stop_duration > STOP_THRESHOLD_MINUTES and velocidad_float < 1.0 and is_out_of_hq_status:
                                parada_display = f"Parada Larga 🛑: {stop_duration:.0f} min"
                                card_style = "background-color: #FFC107; padding: 15px; border-radius: 5px; color: black; margin-bottom: 0px;" 
                                estado_display = parada_display 
                                color_velocidad = "black"
                                
                            # Resaltado visual para Exceso de Velocidad (Solo si no es Falla GPS ni Parada Larga)
                            elif velocidad_float > 74.0:
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
                        st.markdown(
                            f'<p style="display: flex; align-items: center; justify-content: center; font-size: 1.9em; font-weight: 900; margin-top: 0px;">'
                            f'📍 <span style="margin-left: 8px; color: {color_velocidad};">{velocidad_formateada} Km</span>'
                            f'</p>',
                            unsafe_allow_html=True
                        )
                        st.markdown(f'<p style="font-size: 1.0em; margin-top: 0px; opacity: 1.1; text-align: center; margin-bottom: 0px;">{estado_display}</p>', unsafe_allow_html=True)
                        st.markdown('</div>', unsafe_allow_html=True)

                        # Botón de Ubicación
                        with st.expander("Detalles ℹ️"):
                            stop_timedelta_card = row['STOP_DURATION_TIMEDELTA']
                            tiempo_parado_display = f"{int(stop_timedelta_card.total_seconds() // 60)} min {int(stop_timedelta_card.total_seconds() % 60):02} seg"
                            
                            st.caption(f"Tiempo Parado: **{tiempo_parado_display}**") 
                            
                            # 🚨 CAMBIO AÑADIDO: Muestra el motivo específico de la Falla GPS y el último reporte 🚨
                            falla_motivo = row.get('FALLA_GPS_MOTIVO')
                            last_report_display = row.get('LAST_REPORT_TIME_DISPLAY') # Recuperar la hora/fecha del reporte
                            
                            if falla_motivo:
                                # Usamos st.error para que se destaque bien en el expander
                                st.error(
                                    f"🚫 **Motivo Falla GPS:** {falla_motivo}\n\n"
                                    f"🕒 **Último Reporte:** {last_report_display}"
                                )
                            # -------------------------------------------------------------
                            
                            st.caption(f"Estado GPS: **{estado_ignicion}**")
                            st.caption(f"Dirección: **{row['UBICACION_TEXTO']}**")
                            
                            # Muestra el último reporte como caption si NO es una falla GPS, para información general
                            if not falla_motivo:
                                st.caption(f"Último Reporte: **{last_report_display}**")
                                
                            st.caption(f"Coordenadas: ({row['LONGITUD']:.4f}, {row['LATITUD']:.4f})")
                        
                st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)
            
    st.markdown("---")
    
    # PAUSA DE 3 SEGUNDOS
    time.sleep(3)
