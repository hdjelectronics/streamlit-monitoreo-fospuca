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

# --- CONFIGURACIÓN DE LA API Y MÁXIMA SEGURIDAD (st.secrets) ---
API_URL = "https://flexapi.foresightgps.com/ForesightFlexAPI.ashx"

try:
    # 🔑 La clave se carga de forma SEGURA desde st.secrets
    BASIC_AUTH_HEADER = st.secrets["api"]["basic_auth_header"]
except KeyError:
    # Si el secreto NO se encuentra, detenemos la aplicación (MÁXIMA SEGURIDAD)
    st.error("ERROR CRÍTICO: No se pudo encontrar la clave 'basic_auth_header' en st.secrets.")
    st.info("Asegúrese de configurar el archivo '.streamlit/secrets.toml' o la configuración de 'Secrets' en la nube.")
    st.stop() # Detiene la ejecución

# Definimos la Carga Útil (Payload)
payload = {
    "userid": "82825",
    "requesttype": 0,
    "isdeleted": 0,
    "pageindex": 1,
    "orderby": "name",
    "orderdirection": "ASC",
    "conncode": "SATEQSA",
    "elements": 1,
    # Lista de IDs
    "ids": "328601,307300,307317,307301,301893,310389,310494,310629,318795,310460,334708,319412,309599,328471,330208",
    "method": "usersearchplatform",
    "pagesize": 15,
    "prefix": True
}

# Encabezados de autenticación
headers = {
    "Content-Type": "application/json",
    "Authorization": BASIC_AUTH_HEADER
}

# --- CONSTANTES DE LA SEDE (AJUSTADAS) ---
LAT_SEDE = 10.9523  
LON_SEDE = -63.8630
PROXIMIDAD_KM = 0.5 

# Función auxiliar para calcular la distancia Haversine
def haversine(lat1, lon1, lat2, lon2):
    """Calcula la distancia Haversine entre dos puntos en la Tierra (en km)."""
    R = 6371  # Radio de la Tierra en km
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])

    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = np.sin(dlat/2.0)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2.0)**2
    c = 2 * np.arcsin(np.sqrt(a))
    return R * c

# --- FUNCIÓN AUXILIAR PARA ESTILOS ---
def get_card_style(estado):
    """Función auxiliar para obtener el estilo de la tarjeta basado en el estado."""
    color_map = {
        "Encendida (Sede) 🔥": "#FF9800",  # NARANJA
        "Encendida 🔥": "#4CAF50",         # VERDE
        "Resguardo (Sede) 🛡️": "#337ab7",  # AZUL
        "Apagada ❄️": "#D32F2F"            # ROJO
    }
    color_fondo = color_map.get(estado, "#CCCCCC")
    # Usamos .format() para evitar problemas con el ajuste de línea en f-strings largos
    return "background-color: {}; padding: 15px; border-radius: 5px; color: white; margin-bottom: 0px;".format(color_fondo)


# --- DATOS DE RESPALDO (FALLBACK) ---
def get_fallback_data(error_type="Conexión Fallida"):
    """Genera datos de prueba si la API falla, para mantener el diseño visible."""
    
    # Datos de ejemplo
    fallback_data = [
        {"UNIDAD": "3071", "IGNICION": "Apagada ❄️", "VELOCIDAD": 0, "LATITUD": LAT_SEDE + 0.01, "LONGITUD": LON_SEDE + 0.01, "UBICACION_TEXTO": f"FALLBACK - {error_type}"}, 
        {"UNIDAD": "9004", "IGNICION": "Encendida 🔥", "VELOCIDAD": 43, "LATITUD": LAT_SEDE + 0.01, "LONGITUD": LON_SEDE + 0.01, "UBICACION_TEXTO": f"FALLBACK - {error_type}"},
        {"UNIDAD": "9001", "IGNICION": "Resguardo (Sede) 🛡️", "VELOCIDAD": 42, "LATITUD": LAT_SEDE, "LONGITUD": LON_SEDE, "UBICACION_TEXTO": f"FALLBACK - {error_type}"}, 
        {"UNIDAD": "9010", "IGNICION": "Encendida (Sede) 🔥", "VELOCIDAD": 25, "LATITUD": LAT_SEDE, "LONGITUD": LON_SEDE, "UBICACION_TEXTO": f"FALLBACK - {error_type}"}, 
        {"UNIDAD": "9011", "IGNICION": "Apagada ❄️", "VELOCIDAD": 1, "LATITUD": LAT_SEDE + 0.01, "LONGITUD": LON_SEDE + 0.01, "UBICACION_TEXTO": f"FALLBACK - {error_type}"}, 
    ] 

    df = pd.DataFrame(fallback_data)
    df['CARD_STYLE'] = df.apply(lambda row: get_card_style(row['IGNICION']), axis=1)
    
    return df

# --- FUNCIÓN DE OBTENCIÓN Y FILTRADO DE DATOS ---
@st.cache_data(ttl=5) 
def obtener_datos_unidades():
    """Obtiene y limpia los datos de la API, aplicando la lógica de color por estado/sede."""
    try:
        # Petición a la API
        response = requests.post(API_URL, json=payload, headers=headers, timeout=5) 
        response.raise_for_status() 
        data = response.json()
        
        lista_unidades = data.get("ForesightFlexAPI", {}).get("DATA", [])
        
        # Si la lista de datos está vacía, usa el fallback
        if not lista_unidades:
            return get_fallback_data("Lista de Unidades Vacía (Revisa IDs)")

        # --- PROCESAMIENTO DE DATOS REALES ---
        datos_filtrados = []
        for unidad in lista_unidades:
            # Línea de ignición corregida
            ignicion_raw = unidad.get("ignition", "false").lower()
            velocidad = float(unidad.get("speed_dunit", "0"))
            lat = float(unidad.get("ylat", 0))
            lon = float(unidad.get("xlong", 0))

            ignicion_estado = ignicion_raw == "true"
            
            # Lógica de ubicación y estado
            distancia = haversine(lat, lon, LAT_SEDE, LON_SEDE)
            en_sede = distancia <= PROXIMIDAD_KM
            
            color_fondo = ""
            if ignicion_estado:
                if en_sede:
                    estado_final_display = "Encendida (Sede) 🔥"; color_fondo = "#FF9800"  
                else:
                    estado_final_display = "Encendida 🔥"; color_fondo = "#4CAF50"  
            else:
                if en_sede:
                    estado_final_display = "Resguardo (Sede) 🛡️"; color_fondo = "#337ab7"  
                else:
                    estado_final_display = "Apagada ❄️"; color_fondo = "#D32F2F"  
            
            # Línea de estilo corregida con .format()
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
        # Captura 401 Unauthorized (Clave incorrecta)
        print(f"❌ HTTP Error (API Key/Auth?): {e}")
        return get_fallback_data(f"HTTP Error: {e.response.status_code}")
    except requests.exceptions.RequestException as e:
        # Captura errores de red, DNS o Timeout
        print(f"❌ Error de Conexión o Timeout: {e}")
        return get_fallback_data("Error de Conexión/Red")


# --- CÓDIGO PRINCIPAL DE STREAMLIT (BUCLE DE ACTUALIZACIÓN) ---

placeholder = st.empty()

while True:
    
    # 1. Realiza la petición y obtiene los datos
    df_data = obtener_datos_unidades()
    
    # --- CÓDIGO DE SIDEBAR (Estadísticas) ---
    with st.sidebar:
        st.markdown("---")
        st.header("Estadísticas de la Flota")
        
        # Estadísticas basadas en los datos recibidos (reales o de fallback)
        total_unidades = len(df_data)
        unidades_encendidas = df_data[df_data["IGNICION"].str.contains("Encendida")].shape[0]
        unidades_resguardo = df_data[df_data["IGNICION"].str.contains("Resguardo")].shape[0]
        unidades_apagadas = total_unidades - unidades_encendidas - unidades_resguardo
        current_time = pd.Timestamp.now(tz='America/Caracas').strftime('%H:%M:%S')

        st.metric("Total Unidades", total_unidades)
        st.metric("Encendidas 🔥", unidades_encendidas)
        st.metric("Apagadas ❄️", unidades_apagadas)
        st.metric("Resguardo 🛡️", unidades_resguardo) 
        st.markdown("---")
        st.info(f"Última Actualización: **{current_time}**")
        st.markdown("---")
        st.header("DEBUG API STATUS")
        
        # Mensaje de estado: Si se usó el Fallback, lo indica.
        if "FALLBACK" in df_data["UBICACION_TEXTO"].iloc[0]:
            st.warning(f"⚠️ Usando datos de respaldo. Causa: {df_data['UBICACION_TEXTO'].iloc[0].split(' - ')[1]}.")
        else:
            st.success(f"Conexión OK. Se recibieron {len(df_data)} registros.")


    # 3. Actualizar el contenedor principal
    with placeholder.container():
        
        st.markdown("## Monitoreo En Tiempo Real")
        st.markdown("---")
        
        # --- GRID DE UNIDADES ---
        st.subheader("Unidades Maneiro")
        COLUMNS_PER_ROW = 5 
        
        rows = [df_data[i:i + COLUMNS_PER_ROW] for i in range(0, len(df_data), COLUMNS_PER_ROW)]

        for row_index, row_data in enumerate(rows):
            
            cols = st.columns(COLUMNS_PER_ROW)
            
            for col_index, row in row_data.iterrows():
                with cols[col_index % COLUMNS_PER_ROW]:
                    
                    nombre_unidad_display = row['UNIDAD'].split('-')[0] if '-' in row['UNIDAD'] else row['UNIDAD']
                    velocidad_formateada = f"{row['VELOCIDAD']:.0f}"
                    card_style = row['CARD_STYLE']
                    estado_display = row['IGNICION']
                    velocidad_float = row['VELOCIDAD']
                    
                    # Lógica de color dinámico para la VELOCIDAD
                    color_velocidad = "white"
                    if velocidad_float > 35.0:
                        color_velocidad = "#D32F2F"  # ROJO (Exceso)
                    elif velocidad_float >= 40.0:
                        color_velocidad = "#FF9800"  # NARANJA (Advertencia en el límite)

                    # 1. Inicia el contenedor principal con el color de fondo
                    st.markdown(f'<div style="{card_style}">', unsafe_allow_html=True)
                    
                    # 2. Número de la Unidad (Patente/ID) con el recuadro oscuro/semitransparente
                    st.markdown(
                        f'<p style="text-align: center; margin-bottom: 10px; margin-top: 0px;">'
                        f'<span style="background-color: rgba(0,0,0,0.3); padding: 5px 10px; border-radius: 5px; font-size: 1.5em; font-weight: 900;">'
                        f'{nombre_unidad_display}'
                        f'</span>'
                        f'</p>', 
                        unsafe_allow_html=True
                    )
                    
                    # 3. Velocidad y Marcador (con color dinámico)
                    st.markdown(
                        f'<p style="display: flex; align-items: center; justify-content: center; font-size: 1.9em; font-weight: 900; margin-top: 0px;">'
                        f'📍 <span style="margin-left: 8px; color: {color_velocidad};">{velocidad_formateada} Km</span>'
                        f'</p>', 
                        unsafe_allow_html=True
                    )

                    # 4. Estado 
                    st.markdown(f'<p style="font-size: 1.1em; margin-top: 0px; opacity: 1.1; text-align: center; margin-bottom: 0px;">{estado_display}</p>', unsafe_allow_html=True)
                    
                    # Cierra el div del fondo de color
                    st.markdown('</div>', unsafe_allow_html=True)

                    # 5. Botón de Ubicación (st.expander NATICO y FUNCIONAL)
                    with st.expander("Ubicación 🗺️"):
                        st.caption(f"Dirección: **{row['UBICACION_TEXTO']}**")
                        st.caption(f"Coordenadas: ({row['LONGITUD']:.4f}, {row['LATITUD']:.4f})")
                        
            # Separación entre filas
            st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)
            
    st.markdown("---")
    
    # PAUSA DE 5 SEGUNDOS
    time.sleep(5)
