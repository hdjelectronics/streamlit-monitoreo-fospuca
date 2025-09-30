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
import datetime 


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
        padding-top: 1rem; 
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
PROXIMIDAD_KM = 0.2

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
        "CARD_STYLE": "background-color: #D32F2F; padding: 15px; border-radius: 5px; color: white; margin-bottom: 0px;"
    }])

# --- FUNCIÓN DE OBTENCIÓN Y FILTRADO DE DATOS DINÁMICA (TTL de 5 segundos) ---
@st.cache_data(ttl=5)
def obtener_datos_unidades(nombre_flota: str, config: Dict[str, Any]):
    """Obtiene y limpia los datos de la API, aplicando la lógica de color por estado/sede."""
    
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

        # --- PROCESAMIENTO DE DATOS REALES ---
        datos_filtrados = []
        for unidad in lista_unidades:
            ignicion_raw = unidad.get("ignition", "false").lower()
            velocidad = float(unidad.get("speed_dunit", "0"))
            lat = float(unidad.get("ylat", 0))
            lon = float(unidad.get("xlong", 0))
            unit_id = unidad.get("unitid", unidad.get("name", "N/A")) 

            ignicion_estado = ignicion_raw == "true"
            
            distancia = haversine(lat, lon, LAT_SEDE, LON_SEDE)
            en_sede = distancia <= PROXIMIDAD_KM
            
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
            
            card_style = "background-color: {}; padding: 15px; border-radius: 5px; color: white; margin-bottom: 0px;".format(color_fondo)

            datos_filtrados.append({
                "UNIDAD": unidad.get("name", "N/A"),
                "UNIT_ID": unit_id, 
                "IGNICION": estado_final_display,
                "VELOCIDAD": velocidad,
                "LATITUD": lat,
                "LONGITUD": lon,
                "UBICACION_TEXTO": unidad.get("location", "Dirección no disponible"),
                "CARD_STYLE": card_style
            })
        
        return pd.DataFrame(datos_filtrados)

    except requests.exceptions.RequestException as e:
        error_msg = f"API Error: {e}" if not hasattr(e, 'response') else f"HTTP Error: {e.response.status_code}"
        print(f"❌ Error de Conexión/API: {error_msg}")
        return get_fallback_data("Error de Conexión/API")


# --- INICIALIZACIÓN DEL ESTADO DE SESIÓN ---
if 'flota_seleccionada' not in st.session_state:
    st.session_state['flota_seleccionada'] = None 
if 'filtro_sede' not in st.session_state:
    st.session_state['filtro_sede'] = False
if 'unidades_stop_state' not in st.session_state:
    st.session_state['unidades_stop_state'] = {}
if 'alertas_descartadas' not in st.session_state:
    st.session_state['alertas_descartadas'] = {}
if 'alertas_velocidad_descartadas' not in st.session_state:
    st.session_state['alertas_velocidad_descartadas'] = {}
if 'reproducir_audio_alerta' not in st.session_state:
    st.session_state['reproducir_audio_alerta'] = False
if 'reproducir_audio_velocidad' not in st.session_state:
    st.session_state['reproducir_audio_velocidad'] = False
# NUEVA CLAVE PARA EL HISTORIAL DE LOGS
if 'log_historial' not in st.session_state:
    st.session_state['log_historial'] = [] 


# --- CONFIGURACION DEL SIDEBAR ---

def actualizar_dashboard():
    """Función de callback para re-ejecutar el script al cambiar el filtro o flota."""
    st.cache_data.clear()
    pass

with st.sidebar:
    st.markdown(
    '<p style="font-size: 30px; font-weight: bold; color: white; margin-bottom: 0px;">Selección de Flota</p>', 
    unsafe_allow_html=True
)
    
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
        on_change=actualizar_dashboard 
    )
    
    if flota_actual == flota_keys[0]:
        st.session_state['flota_seleccionada'] = None
    else:
        st.session_state['flota_seleccionada'] = flota_actual
        
    st.markdown("---")
    
    alerta_velocidad_placeholder = st.empty()
    st.markdown("---")
    
    alerta_stop_placeholder = st.empty()
    
    if st.session_state['flota_seleccionada']:
        st.markdown("---") 
        st.checkbox(
            "**Unidades en Ruta**", 
            key="filtro_sede",
            on_change=actualizar_dashboard 
        )
    
    st.markdown("---")
    st.header("Estadísticas de la Flota")
    
    metricas_placeholder = st.empty()
    

# === BUCLE PRINCIPAL (while True) - Lógica Completa ===

placeholder = st.empty()
# NUEVO PLACEHOLDER para el Historial de Logs
log_placeholder = st.empty() 

STOP_THRESHOLD_MINUTES = 7.0
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
            
        with alerta_velocidad_placeholder.container(): st.empty()
        with alerta_stop_placeholder.container(): st.empty()
        with metricas_placeholder.container(): st.empty()
        with log_placeholder.container(): st.empty() # Limpiar el log
            
        time.sleep(1) 
        continue 
    # --------------------------------------------------------------------------

    # Obtener datos (se usa el caché para evitar lentitud)
    df_data_original = obtener_datos_unidades(flota_a_usar, FLOTAS_CONFIG)
    
    is_fallback = "FALLBACK" in df_data_original["UNIDAD"].iloc[0]
    
    
    # -- LÓGICA DE DETECCIÓN DE PARADAS LARGAS Y EXCESO DE VELOCIDAD --

    current_stop_state = st.session_state['unidades_stop_state']
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
            is_out_of_hq = not ("(Sede)" in row['IGNICION'] or "Resguardo" in row['IGNICION'])
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
                
                if last_state.get('alerted_stop_minutes'):
                    
                    hora_log = now.strftime('%H:%M:%S')
                    duracion_log = f"{last_state['alerted_stop_minutes']:.1f}"
                    nombre_unidad_display = row['UNIDAD'].split('-')[0] if '-' in row['UNIDAD'] else row['UNIDAD']
                    
                    # Log message Parada Larga (ajustado para incluir 'por:')
                    log_message = (
                        f"**🟢 {hora_log}** | Unidad: **{nombre_unidad_display}** "
                        
