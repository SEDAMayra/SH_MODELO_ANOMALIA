import streamlit as st
import pandas as pd
from datetime import datetime
from simpledbf import Dbf5
from dbfread import DBF
import os

# Cargar el archivo CSS para personalizar estilos
def cargar_css(ruta_css):
    with open(ruta_css) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Función para leer archivos .dbf y convertirlos en un DataFrame
def leer_dbf(archivo, encoding='latin1'):
    try:
        # Leer el archivo .dbf con la codificación especificada
        dbf = DBF(archivo, encoding=encoding)
        df = pd.DataFrame(iter(dbf))
        return df
    except Exception as e:
        st.error(f"Error al leer el archivo .dbf: {e}")
        return None

# Función para mostrar la carga de datos
def mostrar_carga_datos():
    cargar_css("style/cargarDatos.css")  # Ajusta la ruta si es necesario
    st.title("Cargar Datos")

    # Controlar el estado del archivo y la clave dinámica para el file_uploader
    if 'archivo' not in st.session_state:
        st.session_state['archivo'] = None
    if 'mensaje' not in st.session_state:
        st.session_state['mensaje'] = ""
    if 'uploader_key' not in st.session_state:
        st.session_state['uploader_key'] = 0

    # Mostrar el file_uploader solo si no hay un archivo cargado
    if st.session_state['archivo'] is None:
        archivo = st.file_uploader(
            "Drag and drop file here", 
            type=["csv", "xlsx", "dbf"], 
            key=f"uploader_{st.session_state['uploader_key']}"
        )
        if archivo:
            if archivo.name.lower().endswith('.dbf'):
                # Guardar temporalmente el archivo .dbf para leerlo
                with open(f"temp_{archivo.name}", "wb") as f:
                    f.write(archivo.getbuffer())
                
                # Leer el archivo .dbf y obtener el DataFrame
                df = leer_dbf(f"temp_{archivo.name}")

                # Eliminar el archivo temporal después de leerlo
                os.remove(f"temp_{archivo.name}")

                if df is not None:
                    st.session_state['archivo'] = archivo
                    st.session_state['mensaje'] = f"Archivo '{archivo.name}' cargado exitosamente."
            else:
                st.session_state['archivo'] = archivo
                st.session_state['mensaje'] = f"Archivo '{archivo.name}' cargado exitosamente."

    # Mostrar el mensaje si existe uno en el estado
    if st.session_state['mensaje']:
        st.success(st.session_state['mensaje'], icon="📂")

    # Mostrar botones solo si hay un archivo en la sesión
    if st.session_state['archivo']:
        col1, col2 = st.columns(2)

        with col1:
            if st.button("Cancelar"):
                st.session_state['archivo'] = None
                st.session_state['mensaje'] = "El archivo se ha cancelado. Sube uno nuevo."
                st.session_state['uploader_key'] += 1  # Cambiar la clave para reiniciar el file_uploader
                st.rerun()  # Recargar la interfaz para limpiar el file_uploader

        with col2:
            if st.button("Enviar"):
                fecha_subida = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                st.session_state['mensaje'] = f"El archivo ha sido subido el día {fecha_subida}."
                st.rerun()  # Recargar la interfaz para actualizar el mensaje
