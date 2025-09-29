# --- IMPORTACIONES ---
import streamlit as st
import requests
import json
import pandas as pd
import time
import numpy as np
from typing import List, Dict, Any

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Monitoreo GPS - FOSPUCA",
    layout="wide",
    initial_sidebar_state="expanded"
)
# --- iNYECCION DE css ---
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
    
    /* 🚨 NUEVA REGLA AÑADIDA: Modifica el tamaño de todos los st.header() (h1) 🚨 */
    h1 {
        font-size: 2.5rem; /* Ajusta este valor (2.0rem es más pequeño que el valor por defecto) */
        font-weight: 700; /* Mantiene el texto en negrita, estilo header */
        /* Si notas que el color cambia o se pierde, puedes forzarlo aquí: 
        color: white; 
        */
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


# --- CONFIGURACIÓN MULTI-FLOTA ---
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
        "ids": "302005,335250,322991,301848,323144,301931,301873,301897,301975,301891,308190,314809,319378,307304",
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

# --- FUNCIÓN AUXILIAR PARA ESTILOS (SE MANTIENE SIN CAMBIOS) ---
def get_card_style(ignicion_status, speed):
    """Determina el estilo de la tarjeta basado en el estado de ignición y velocidad."""
    
    # 1. ESTADO POR DEFECTO: Encendida en Ruta (Verde)
    bg_color = "#4CAF50" # Verde
    text_color = "white"

    if "Resguardo (Sede)" in ignicion_status:
    # 2. Resguardo (Sede) - Azul Claro
        bg_color = "#337ab7"
        text_color = "white"
        
    elif "Encendida (Sede)" in ignicion_status:
    # 3. Encendida en Sede - NARANJA 
        bg_color = "#B37305" 
        text_color = "white"

    elif "Apagada" in ignicion_status:
    # 4. Apagada - Rojo Oscuro
        bg_color = "#D32F2F" 
        text_color = "white"
        
    # La alerta de Parada Larga/Velocidad se aplica en el bucle principal.

    style = (
        f"background-color: {bg_color}; "
        f"padding: 15px; "
        f"border-radius: 5px; "
        f"color: {text_color}; "
        f"margin-bottom: 0px;"
    )
    return style

# --- DESCARTAR PARADA LARGA (Se renombra la función para claridad) ---
def descartar_alerta_stop(unidad_id_a_descartar):
    """
    Marca la alerta de Parada Larga de una unidad como 'descartada'.
    """
    st.session_state['alertas_descartadas'][unidad_id_a_descartar] = True

# --- DESCARTAR EXCESO DE VELOCIDAD (NUEVA FUNCIÓN) ---
def descartar_alerta_velocidad(unidad_id_a_descartar):
    """
    Marca la alerta de Exceso de Velocidad de una unidad como 'descartada'.
    """
    st.session_state['alertas_velocidad_descartadas'][unidad_id_a_descartar] = True


# --- DATOS DE RESPALDO (FALLBACK) ---
def get_fallback_data(error_type="Conexión Fallida"): 
    """Genera una estructura de datos de una sola fila para señalizar el error en el main loop."""
    
    # Devuelve una sola fila con la información de error
    return pd.DataFrame([{
        "UNIDAD": "FALLBACK", 
        "IGNICION": "N/A", 
        "VELOCIDAD": 0, 
        "LATITUD": 0, 
        "LONGITUD": 0, 
        "UBICACION_TEXTO": f"FALLBACK - {error_type}", 
        "CARD_STYLE": "background-color: #D32F2F; padding: 15px; border-radius: 5px; color: white; margin-bottom: 0px;"
    }])

# --- FUNCIÓN DE OBTENCIÓN Y FILTRADO DE DATOS DINÁMICA ---
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
            unit_id = unidad.get("unitid", unidad.get("name", "N/A")) # Usar unitid para rastreo

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

    except requests.exceptions.HTTPError as e:
        error_code = e.response.status_code
        error_msg = "AUTENTICACIÓN (401)" if error_code == 401 else f"HTTP Error: {error_code}"
        print(f"❌ Error de API: {error_msg}")
        return get_fallback_data(error_msg)
    except requests.exceptions.RequestException as e:
        print(f"❌ Error de Conexión o Timeout: {e}")
        return get_fallback_data("Error de Conexión/Red")


# --- INICIALIZACIÓN DEL ESTADO DE SESIÓN (MODIFICADO) ---
# Inicializar 'flota_seleccionada' a None
if 'flota_seleccionada' not in st.session_state:
    st.session_state['flota_seleccionada'] = None 
if 'filtro_sede' not in st.session_state:
    st.session_state['filtro_sede'] = False
    
# CLAVE PARA RASTREAR PARADAS LARGAS
if 'unidades_stop_state' not in st.session_state:
    st.session_state['unidades_stop_state'] = {}
    
# INICIALIZACIÓN DE ALERTAS DESCARTADAS (PARADA LARGA)    
if 'alertas_descartadas' not in st.session_state:
    st.session_state['alertas_descartadas'] = {}

# INICIALIZACIÓN: ALERTAS DESCARTADAS (EXCESO VELOCIDAD)
if 'alertas_velocidad_descartadas' not in st.session_state:
    st.session_state['alertas_velocidad_descartadas'] = {}


# --- CONFIGURACION DEL SIDEBAR (MODIFICADO) ---

def actualizar_dashboard():
    """Función de callback para re-ejecutar el script al cambiar el filtro o flota."""
    st.cache_data.clear()
    pass

with st.sidebar:
    st.markdown(
    '<p style="font-size: 30px; font-weight: bold; color: white; margin-bottom: 0px;">Selección de Flota</p>', 
    unsafe_allow_html=True
)
    
    # 1. Ajustar opciones y valor por defecto para incluir "Seleccione una Flota"
    flota_keys = ["-- Seleccione una Flota --"] + list(FLOTAS_CONFIG.keys())
    
    # Determinar el índice actual
    current_flota = st.session_state['flota_seleccionada']
    try:
        current_index = flota_keys.index(current_flota) if current_flota else 0
    except ValueError:
        current_index = 0
        
    flota_actual = st.selectbox(
        "Seleccione la Flota a Monitorear:",
        options=flota_keys,
        index=current_index,
        key="flota_selector",
        on_change=actualizar_dashboard # Llamar al cambiar
    )
    
    # 2. Actualizar el estado de sesión: Si se selecciona el valor por defecto, se guarda None
    if flota_actual == flota_keys[0]:
        st.session_state['flota_seleccionada'] = None
    else:
        st.session_state['flota_seleccionada'] = flota_actual
        
    st.markdown("---")
    
# --- PLACEHOLDERS para alertas y métricas ---
    alerta_velocidad_placeholder = st.empty()
    st.markdown("---")
    
    alerta_stop_placeholder = st.empty()
    
# --- FILTRO SOLO SI HAY FLOTA SELECCIONADA ---
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

# --- Umbral de parada larga (5.0 minutos) ---
STOP_THRESHOLD_MINUTES = 5.0
# --- UMBRAL DE EXCESO DE VELOCIDAD (70 km/h) ---
SPEED_THRESHOLD_KPH = 70.0

while True:
    
    flota_a_usar = st.session_state['flota_seleccionada'] 

    # --- 🔑 CONDICIÓN CRÍTICA: NO EJECUTAR SI NO HAY FLOTA SELECCIONADA 🔑 ---
    if not flota_a_usar:
        with placeholder.container():
            st.markdown(
    f"<h2 id='main-title'>Rastreo GPS - Monitoreo GPS - FOSPUCA</h2>", 
    unsafe_allow_html=True
)
            st.markdown("---")
            st.info("👋 Por favor, **seleccione una Flota** en el panel lateral (Sidebar) para comenzar el monitoreo en tiempo real.")
            
        # Limpiar placeholders de alertas y métricas si no hay flota
        with alerta_velocidad_placeholder.container(): st.empty()
        with alerta_stop_placeholder.container(): st.empty()
        with metricas_placeholder.container(): st.empty()
            
        time.sleep(1) # Pausa más corta al estar inactivo
        continue 
    # --------------------------------------------------------------------------

    # Si hay flota seleccionada, obtenemos los datos:
    df_data_original = obtener_datos_unidades(flota_a_usar, FLOTAS_CONFIG)
    
    is_fallback = "FALLBACK" in df_data_original["UNIDAD"].iloc[0]
    
    
    # -- LÓGICA DE DETECCIÓN DE PARADAS LARGAS Y REINICIO DE CONTADOR --

    current_stop_state = st.session_state['unidades_stop_state']
    now = pd.Timestamp.now(tz='America/Caracas')
    
    df_data_original['STOP_DURATION_MINUTES'] = 0.0
    df_data_original['STOP_DURATION_TIMEDELTA'] = pd.Timedelta(seconds=0) 

    if not is_fallback:
        for index, row in df_data_original.iterrows():
            unidad_id = row['UNIDAD']
            unit_id_api = row['UNIT_ID']
            velocidad = row['VELOCIDAD']
            
            if unit_id_api not in current_stop_state:
                current_stop_state[unit_id_api] = {'last_move_time': now}
                continue 

            last_state = current_stop_state[unit_id_api]
            
            is_moving = velocidad > 1.0 
            
            if is_moving:
                last_state['last_move_time'] = now
                df_data_original.loc[index, 'STOP_DURATION_MINUTES'] = 0.0
                df_data_original.loc[index, 'STOP_DURATION_TIMEDELTA'] = pd.Timedelta(seconds=0)
                
                # Reinicio el estado de alerta DESCARTADA de Parada Larga si se mueve
                if unidad_id in st.session_state['alertas_descartadas']:
                    del st.session_state['alertas_descartadas'][unidad_id]
                
                # Reinicio el estado de alerta DESCARTADA de Velocidad si se mueve
                if unidad_id in st.session_state['alertas_velocidad_descartadas']:
                    del st.session_state['alertas_velocidad_descartadas'][unidad_id]
            
            else:
                stop_duration_timedelta = now - last_state['last_move_time']
                stop_duration_total_seconds = stop_duration_timedelta.total_seconds()
                
                df_data_original.loc[index, 'STOP_DURATION_MINUTES'] = stop_duration_total_seconds / 60.0
                df_data_original.loc[index, 'STOP_DURATION_TIMEDELTA'] = stop_duration_timedelta
                
            st.session_state['unidades_stop_state'][unit_id_api] = last_state
    
    
    # -- LÓGICA DE FILTRADO CONDICIONAL DEL CHECKBOX --

    df_data_mostrada = df_data_original
    filtro_descripcion = "Todas las Unidades"

    if not is_fallback and st.session_state.get("filtro_sede", False):
        
        is_en_ruta = ~df_data_original["IGNICION"].str.contains("(Sede)|Resguardo")
        
        df_data_mostrada = df_data_original[is_en_ruta]
        filtro_descripcion = "Unidades Fuera de Sede 🛣️"

        df_data_mostrada = df_data_mostrada.reset_index(drop=True)
    
    
    
    # -- LÓGICA DE DETECCIÓN Y CONSTRUCCIÓN DE ALERTA DE PARADA LARGA --
    # ------------------------------------------------------------------

    unidades_en_alerta_stop = pd.DataFrame()
    mensaje_alerta_stop = ""

    if not is_fallback:
        
        # 1. Detectar TODAS las unidades que cumplen la condición de Parada Larga
        todas_las_alertas_stop = df_data_original[
            (df_data_original['STOP_DURATION_MINUTES'] > STOP_THRESHOLD_MINUTES) &
            (~df_data_original["IGNICION"].str.contains("(Sede)|Resguardo"))
        ].copy()

        # 2. Filtrar aquellas alertas que NO han sido descartadas (aceptadas)
        unidades_pendientes_stop = [
            uid for uid in todas_las_alertas_stop['UNIDAD'] 
            if st.session_state['alertas_descartadas'].get(uid) != True
        ]

        # 3. Filtrar el DataFrame final que se mostrará en el text box
        unidades_en_alerta_stop = todas_las_alertas_stop[
            todas_las_alertas_stop['UNIDAD'].isin(unidades_pendientes_stop)
        ].sort_values(by='STOP_DURATION_MINUTES', ascending=False)


        # Construir el mensaje de alerta
        if not unidades_en_alerta_stop.empty:
            total_alertas = len(unidades_en_alerta_stop)
            
            mensaje_alerta_stop += f"**{total_alertas} PARADA LARGA(S) PENDIENTE(S) 🚨**\n\n"
            
            for _, row in unidades_en_alerta_stop.head(5).iterrows():
                nombre_unidad = row['UNIDAD'].split('-')[0]
                
                total_segundos = row['STOP_DURATION_TIMEDELTA'].total_seconds()
                minutos_parte = int(total_segundos // 60)
                segundos_parte = int(total_segundos % 60)
                tiempo_parado = f"{minutos_parte}min {segundos_parte:02}seg" 
                
                mensaje_alerta_stop += (
                    f"**{nombre_unidad}** ({tiempo_parado}):\n"
                    f"---\n"
                )
    
    
    # --- NUEVA: LÓGICA DE DETECCIÓN Y CONSTRUCCIÓN DE ALERTA DE VELOCIDAD ---
    # -----------------------------------------------------------------------

    unidades_en_alerta_speed = pd.DataFrame()
    mensaje_alerta_speed = ""

    if not is_fallback:
        
        # 1. Detectar TODAS las unidades con exceso de velocidad (MAYOR O IGUAL A 70.0 km/h)
        todas_las_alertas_speed = df_data_original[
            (df_data_original['VELOCIDAD'] >= SPEED_THRESHOLD_KPH) &
            (~df_data_original["IGNICION"].str.contains("(Sede)|Resguardo"))
        ].copy()

        # 2. Filtrar aquellas alertas que NO han sido descartadas (aceptadas)
           color: white; 
        */
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


# --- CONFIGURACIÓN MULTI-FLOTA ---

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
        "lat_sede": 8.2917, 
        "lon_sede": -62.7216
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
        "ids": "302005,335250,322991,301848,323144,301931,301873,301897,301975,301891,308190,314809,319378,307304",
        "lat_sede": 10.191370,
        "lon_sede": -67.961420
    },
    
}
# --- DISTANCIA DE LA SEDE (PARA ASUMIR EN SEDE) (100MTS fijos) ---
PROXIMIDAD_KM = 0.1

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
    # 2. Resguardo (Sede) - Azul Claro
        bg_color = "#337ab7"
        text_color = "white"
        
    elif "Encendida (Sede)" in ignicion_status:
    # 3. Encendida en Sede - CIAN / TURQUESA (Nuevo color para diferenciar de alerta)
        bg_color = "#F7B736" 
        text_color = "white"

    elif "Apagada" in ignicion_status:
    # 4. Apagada - Rojo Oscuro
        bg_color = "#D32F2F" 
        text_color = "white"
        
    # La alerta de Parada Larga se aplica en el bucle principal.

    style = (
        f"background-color: {bg_color}; "
        f"padding: 15px; "
        f"border-radius: 5px; "
        f"color: {text_color}; "
        f"margin-bottom: 0px;"
    )
    return style

# --- DESCARTAR PARADA LARGA ---
def descartar_alerta(unidad_id_a_descartar):
    """
    Marca la alerta de una unidad como 'descartada' para ocultarla del text box.
    NO reinicia el contador de parada.
    """
    st.session_state['alertas_descartadas'][unidad_id_a_descartar] = True

# --- DATOS DE RESPALDO (FALLBACK) ---
def get_fallback_data(error_type="Conexión Fallida"): 
    """Genera una estructura de datos de una sola fila para señalizar el error en el main loop."""
    
    # Devuelve una sola fila con la información de error
    return pd.DataFrame([{
        "UNIDAD": "FALLBACK", 
        "IGNICION": "N/A", 
        "VELOCIDAD": 0, 
        "LATITUD": 0, 
        "LONGITUD": 0, 
        "UBICACION_TEXTO": f"FALLBACK - {error_type}", 
        "CARD_STYLE": "background-color: #D32F2F; padding: 15px; border-radius: 5px; color: white; margin-bottom: 0px;"
    }])

# --- FUNCIÓN DE OBTENCIÓN Y FILTRADO DE DATOS DINÁMICA ---
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

            ignicion_estado = ignicion_raw == "true"
            
            distancia = haversine(lat, lon, LAT_SEDE, LON_SEDE)
            en_sede = distancia <= PROXIMIDAD_KM
            
            estado_final_display = "Apagada ❄️" 
            color_fondo = "#D32F2F" 
            
            if ignicion_estado:
                if en_sede:
                    estado_final_display = "Encendida (Sede) 🔥"; color_fondo = "#F7B736"
                else:
                    estado_final_display = "Encendida 🔥"; color_fondo = "#4CAF50"
            else:
                if en_sede:
                    estado_final_display = "Resguardo (Sede) 🛡️"; color_fondo = "#337ab7"
            
            card_style = "background-color: {}; padding: 15px; border-radius: 5px; color: white; margin-bottom: 0px;".format(color_fondo)

            datos_filtrados.append({
                "UNIDAD": unidad.get("name", "N/A"),
                "IGNICION": estado_final_display,
                "VELOCIDAD": velocidad,
                "LATITUD": lat,
                "LONGITUD": lon,
                "UBICACION_TEXTO": unidad.get("location", "Dirección no disponible"),
                "CARD_STYLE": card_style
            })
        
        return pd.DataFrame(datos_filtrados)

    except requests.exceptions.HTTPError as e:
        error_code = e.response.status_code
        error_msg = "AUTENTICACIÓN (401)" if error_code == 401 else f"HTTP Error: {error_code}"
        print(f"❌ Error de API: {error_msg}")
        return get_fallback_data(error_msg)
    except requests.exceptions.RequestException as e:
        print(f"❌ Error de Conexión o Timeout: {e}")
        return get_fallback_data("Error de Conexión/Red")


# --- INICIALIZACIÓN DEL ESTADO DE SESIÓN ---
if 'flota_seleccionada' not in st.session_state:
    st.session_state['flota_seleccionada'] = "Maneiro" 
if 'filtro_sede' not in st.session_state:
    st.session_state['filtro_sede'] = False
    
# 🚨 NUEVA CLAVE PARA RASTREAR PARADAS LARGAS 🚨
if 'unidades_stop_state' not in st.session_state:
    st.session_state['unidades_stop_state'] = {}
    
# INICIALIZACIÓN DE ALERTAS DESCARTADAS    
if 'alertas_descartadas' not in st.session_state:
    st.session_state['alertas_descartadas'] = {}



# --- CONFIGURACION DEL SIDEBAR(FUERA DEL BUCLE) ---

def actualizar_dashboard():
    """Función de callback para re-ejecutar el script al cambiar el filtro."""
    st.cache_data.clear()
    # Limpia el caché para asegurar datos frescos si es necesario
    # st.rerun()
    # Descomentar si el cambio no es inmediato (aunque el bucle ya debería manejarlo)
    pass
    # Normalmente, el propio st.checkbox desencadena la re-ejecución
with st.sidebar:
    st.markdown(
    '<p style="font-size: 30px; font-weight: bold; color: white; margin-bottom: 0px;">Selección de Flota</p>', 
    unsafe_allow_html=True
)
    
    flota_keys = list(FLOTAS_CONFIG.keys())
    try:
        current_flota = st.session_state['flota_seleccionada']
        if current_flota not in flota_keys:
            current_flota = "Maneiro"
            
        current_index = flota_keys.index(current_flota)
    except ValueError:
        current_index = 0 
        st.session_state['flota_seleccionada'] = flota_keys[0]

    flota_actual = st.selectbox(
        "Seleccione la Flota a Monitorear:",
        options=flota_keys,
        index=current_index,
        key="flota_selector" 
    )
    
    st.session_state['flota_seleccionada'] = flota_actual
    st.markdown("---")
    
# --- 🚨 NUEVO PLACEHOLDER PARA LA ALERTA DE PARADA LARGA 🚨 ---
    alerta_placeholder = st.empty()
    
# --- FILTRO SOLICITADO AQUÍ ---
    st.markdown("---") 
    # Usamos on_change para garantizar la respuesta al clic
    st.checkbox(
        "**Unidades en Ruta**", 
        key="filtro_sede",
        on_change=actualizar_dashboard # Asegura la actualización
    )
  
    st.markdown("---")
    st.header("Estadísticas de la Flota")
    
    metricas_placeholder = st.empty()
    

# === BUCLE PRINCIPAL (while True) - Lógica Completa y Corregida ===

placeholder = st.empty()

# --- Umbral de parada larga (5.0 minutos) ---
STOP_THRESHOLD_MINUTES = 5.0

while True:
    
    # NOTA: Asegúrate de que pandas (pd), time, y las funciones/configuraciones auxiliares
    # estén definidas e importadas antes de este bucle.
    
    flota_a_usar = st.session_state['flota_seleccionada'] 
    df_data_original = obtener_datos_unidades(flota_a_usar, FLOTAS_CONFIG)
    
    # Comprobar si estamos en modo Fallback
    is_fallback = "FALLBACK" in df_data_original["UNIDAD"].iloc[0]
    
   
    # -- 🚨 LÓGICA DE DETECCIÓN DE PARADAS LARGAS Y REINICIO DE CONTADOR 🚨 --

    current_stop_state = st.session_state['unidades_stop_state']
    now = pd.Timestamp.now(tz='America/Caracas')
    
    # -- 🛠 INICIALIZACIÓN: Crear las columnas necesarias para el tiempo --
    df_data_original['STOP_DURATION_MINUTES'] = 0.0
    df_data_original['STOP_DURATION_TIMEDELTA'] = pd.Timedelta(seconds=0) 

    if not is_fallback:
        for index, row in df_data_original.iterrows():
            unidad_id = row['UNIDAD']
            velocidad = row['VELOCIDAD']

            if unidad_id not in current_stop_state:
                current_stop_state[unidad_id] = {'last_move_time': now}
                continue 

            last_state = current_stop_state[unidad_id]
            
            # Si la unidad se está moviendo (> 1 Km/h), reinicia el contador de parada
            is_moving = velocidad > 1.0 
            
            if is_moving:
                last_state['last_move_time'] = now
                df_data_original.loc[index, 'STOP_DURATION_MINUTES'] = 0.0
                df_data_original.loc[index, 'STOP_DURATION_TIMEDELTA'] = pd.Timedelta(seconds=0)
                
            # Si se mueve, reiniciamos el estado de alerta DESCARTADA
                if unidad_id in st.session_state['alertas_descartadas']:
                     del st.session_state['alertas_descartadas'][unidad_id]
            
            # Lógica de cálculo de duración (Parada)
            else:
                # Si está parada (velocidad <= 1), calcula la duración
                stop_duration_timedelta = now - last_state['last_move_time']
                stop_duration_total_seconds = stop_duration_timedelta.total_seconds()
                
                # Almacenar la duración en minutos (matemáticos) para el filtro
                df_data_original.loc[index, 'STOP_DURATION_MINUTES'] = stop_duration_total_seconds / 60.0
                
                # Almacenar la duración como timedelta para facilitar la presentación (MM min SS seg)
                df_data_original.loc[index, 'STOP_DURATION_TIMEDELTA'] = stop_duration_timedelta
                
            # Actualiza el estado de sesión
            st.session_state['unidades_stop_state'][unidad_id] = last_state
    
    
    # --🚨 LÓGICA DE FILTRADO CONDICIONAL DEL CHECKBOX 🚨 --

    df_data_mostrada = df_data_original
    filtro_descripcion = "Todas las Unidades"

    if not is_fallback and st.session_state.get("filtro_sede", False):
        
        is_en_ruta = ~df_data_original["IGNICION"].str.contains("(Sede)|Resguardo")
        
        df_data_mostrada = df_data_original[is_en_ruta]
        filtro_descripcion = "Unidades Fuera de Sede 🛣️"

        df_data_mostrada = df_data_mostrada.reset_index(drop=True)
    
    
    
    # -- 🚨 LÓGICA DE DETECCIÓN Y CONSTRUCCIÓN DE ALERTA DE PARADA LARGA 🚨 --
  

    unidades_en_alerta = pd.DataFrame()
    mensaje_alerta = ""

    if not is_fallback:
        
        # 1. Detectar TODAS las unidades que cumplen la condición de Parada Larga
        todas_las_alertas = df_data_original[
            (df_data_original['STOP_DURATION_MINUTES'] > STOP_THRESHOLD_MINUTES) &
            (~df_data_original["IGNICION"].str.contains("(Sede)|Resguardo"))
        ].copy()

        # 2. Filtrar aquellas alertas que NO han sido descartadas (aceptadas)
        unidades_pendientes = []
        for uid in todas_las_alertas['UNIDAD']:
            # IMPORTANTE: No necesitas el registro de las que aceptaste, solo evitas que se muestre aquí si ya fue marcada
            if st.session_state['alertas_descartadas'].get(uid) != True:
                unidades_pendientes.append(uid)

        # 3. Filtrar el DataFrame final que se mostrará en el text box
        unidades_en_alerta = todas_las_alertas[
            todas_las_alertas['UNIDAD'].isin(unidades_pendientes)
        ].sort_values(by='STOP_DURATION_MINUTES', ascending=False)


        # Construir el mensaje de alerta
        if not unidades_en_alerta.empty:
            total_alertas = len(unidades_en_alerta)
            
            mensaje_alerta += f"**{total_alertas} PARADA LARGA(S) PENDIENTE(S) 🚨**\n\n"
            
            for _, row in unidades_en_alerta.head(5).iterrows():
                nombre_unidad = row['UNIDAD'].split('-')[0]
                
                # 🛠️ PRESENTACIÓN CORREGIDA DE TIEMPO (ALERTA)
                total_segundos = row['STOP_DURATION_TIMEDELTA'].total_seconds()
                minutos_parte = int(total_segundos // 60)
                segundos_parte = int(total_segundos % 60)
                tiempo_parado = f"{minutos_parte}min {segundos_parte:02}seg" # Formato MM min SS seg
                
                direccion = row['UBICACION_TEXTO'][:40] + "..."
                
                mensaje_alerta += (
                    f"**{nombre_unidad}** ({tiempo_parado}):\n"
                    f"---\n"
                )
            
    # --- Actualización de Métricas del Sidebar ---
    with metricas_placeholder.container():
        
        current_time = now.strftime('%H:%M:%S')

        if not is_fallback:
            # ESTADÍSTICAS REALES 
            total_unidades_flota = len(df_data_original) 
            unidades_encendidas = df_data_original[df_data_original["IGNICION"].str.contains("Encendida")].shape[0]
            unidades_resguardo = df_data_original[df_data_original["IGNICION"].str.contains("Resguardo")].shape[0]
            unidades_apagadas = total_unidades_flota - unidades_encendidas - unidades_resguardo
            
            st.metric("Total Unidades", total_unidades_flota) 
            st.metric("Encendidas 🔥", unidades_encendidas)
            st.metric("Apagadas ❄️", unidades_apagadas)
            st.metric("Resguardo 🛡️", unidades_resguardo) 
            
            # Mensaje de DEBUG API
            st.markdown("---")
            st.info(f"Última Actualización: **{current_time}**") 
            st.markdown("---")
            st.header("DEBUG API STATUS")
            
            st.success(f"Conexión **OK**. Se recibieron {total_unidades_flota} registros.") 
            if st.session_state.get("filtro_sede", False):
                st.info(f"Filtro Activo: **{filtro_descripcion}**. Mostrando **{len(df_data_mostrada)}** unidades.")
        else:
            # ESTADÍSTICAS FALLBACK
            causa = df_data_original['UBICACION_TEXTO'].iloc[0].split(' - ')[1]
            st.metric("Total Unidades", "Error")
            st.error(f"❌ API Falló: {causa}")
            st.markdown("---")
            st.info(f"Última Actualización: **{current_time}**") 
            
    
    # 4. ACTUALIZAR EL TEXT BOX DE ALERTA (BOTONES INDIVIDUALES y GLOBAL)

    
    # Generar un ID basado en el tiempo para forzar la unicidad de las llaves
    unique_time_id = int(time.time() * 1000) 
    
    with alerta_placeholder.container():
        if not unidades_en_alerta.empty:
            total_alertas_pendientes = len(unidades_en_alerta)
            st.markdown(f"#### 🚨 Alerta de Parada Larga ({total_alertas_pendientes})")
            st.markdown("---")
            
            st.warning(mensaje_alerta) 
            
            # Botones de descarte individuales (CON LLAVE DINÁMICA)
            st.markdown("##### Aceptar y Descartar Mensaje:")
            cols_btn = st.columns(3) 
            
            for index, row in unidades_en_alerta.iterrows():
                unidad_id = row['UNIDAD']
                nombre_display = unidad_id.split('-')[0]
                col_index = index % 3
                
                with cols_btn[col_index]:
                    st.button(
                        f"Aceptar: {nombre_display}",
                        # FIX: Llave dinámica individual
                        key=f"descartar_{unidad_id}_{unique_time_id}", 
                        on_click=descartar_alerta,
                        args=(unidad_id,),
                        type="primary"
                    )
                    
            st.markdown("---")
            
            # Botón de Descarte Global 
            if total_alertas_pendientes > 0:
                st.button(
                    "Aceptar TODAS las Alertas PENDIENTES",
                    # FIX: Llave dinámica global para evitar el nuevo error
                    key=f"descartar_all_stops_{unique_time_id}",
                    on_click=lambda: [descartar_alerta(uid) for uid in unidades_en_alerta['UNIDAD']],
                    type="secondary"
                )
                
        # Si no hay alertas pendientes, limpiamos el placeholder
        else:
            alerta_placeholder.empty()

    # --- Actualizar el Contenedor Principal (Tarjetas) ---
    with placeholder.container():
        st.markdown(
    f"<h2 id='main-title'>Rastreo GPS - Flota {flota_a_usar}</h2>", 
    unsafe_allow_html=True
)
        st.markdown("---")
        
        # AJUSTE DE SUBTÍTULO
  
        st.subheader(f"{filtro_descripcion} - ({len(df_data_mostrada)})")
        # Si el resultado fue FALLBACK, mostrar el error en el contenedor principal
        if is_fallback:
            causa_display = df_data_original['UBICACION_TEXTO'].iloc[0].split(' - ')[1]
            st.error(f"🚨 **ERROR CRÍTICO DE CONEXIÓN/DATOS** 🚨")
            st.warning(f"La API de Foresight GPS no devolvió datos. Razón: **{causa_display}**.")
            
        else:
            # Lógica para mostrar tarjetas
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
                        
                        is_out_of_hq_status = not ("(Sede)" in estado_ignicion or "Resguardo" in estado_ignicion)
                        
                        # 🚨 RESALTADO VISUAL PERMANENTE (ALERTA DE PARADA LARGA) 🚨
                        if stop_duration > STOP_THRESHOLD_MINUTES and velocidad_float < 1.0 and is_out_of_hq_status:
                            parada_display = f"Parada Larga 🛑: {stop_duration:.0f} min"
                            card_style = "background-color: #FFC107; padding: 15px; border-radius: 5px; color: black; margin-bottom: 0px;" 
                            estado_display = parada_display 
                            color_velocidad = "black"
                            
                        # --- Resaltado visual para alta velocidad ---
                        elif velocidad_float > 74.0:
                            color_velocidad = "#D32F2F" # ROJO
                            estado_display = "EXCESO VELOCIDAD 🚨"
                        
                        elif velocidad_float > 70.0:
                            color_velocidad = "#FF9800" # NARANJA
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
                            # 🛠️ PRESENTACIÓN CORREGIDA DE TIEMPO (DETALLES)
                            stop_timedelta_card = row['STOP_DURATION_TIMEDELTA']
                            total_segundos_card = stop_timedelta_card.total_seconds()
                            minutos_parte_card = int(total_segundos_card // 60)
                            segundos_parte_card = int(total_segundos_card % 60)
                            tiempo_parado_display = f"{minutos_parte_card} min {segundos_parte_card:02} seg"

                            st.caption(f"Tiempo Parado: **{tiempo_parado_display}**") 
                            st.caption(f"Estado GPS: **{estado_ignicion}**")
                            st.caption(f"Dirección: **{row['UBICACION_TEXTO']}**")
                            st.caption(f"Coordenadas: ({row['LONGITUD']:.4f}, {row['LATITUD']:.4f})")
                
                st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)
            
    st.markdown("---")
    
    # PAUSA DE 5 SEGUNDOS
    time.sleep(5)
