import os
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import streamlit as st
import pandas as pd
from dbfread import DBF
from sklearn.preprocessing import MinMaxScaler
from conexion import obtener_conexion
from psycopg2.extras import execute_values
from datetime import datetime

# ---------------------------------------------------
# 0) Cargamos las vars de .env para SMTP
# ---------------------------------------------------
load_dotenv()
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT   = int(os.getenv("SMTP_PORT", 587))
SMTP_USER   = os.getenv("SMTP_USER")      # tu cuenta de correo
SMTP_PASS   = os.getenv("SMTP_PASS")      # contraseña de aplicación

# ---------------------------------------------------
# 1) Funciones de notificación por correo
# ---------------------------------------------------
# ---------------------------------------------------
# 1) Funciones de notificación por correo
# ---------------------------------------------------


def obtener_correos_destino():
    """Lee todos los emails de la tabla usuarios"""
    conn = obtener_conexion()
    df = pd.read_sql("SELECT email FROM usuarios", conn)
    conn.close()
    return df["email"].tolist()

def enviar_notificacion_general(asunto: str, cuerpo: str, destinos: list[str]):
    """Envía un mismo correo a cada dirección de la lista"""
    # Abrimos la conexión SMTP solo una vez
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        for dest in destinos:
            # Por cada destinatario construimos un nuevo mensaje
            msg = MIMEMultipart()
            msg["From"]    = SMTP_USER
            msg["To"]      = dest
            msg["Subject"] = asunto
            msg.attach(MIMEText(cuerpo, "plain"))
            server.send_message(msg)


# ---------------------------------------------------
# 2) Código existente para carga y procesamiento
# ---------------------------------------------------

# Crear carpeta para guardar archivos CSV
output_dir = "guardar_datos"
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# Cargar estilo CSS
def load_css(file_name):
    with open(file_name) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css("style/cargarDatos.css")

# Leer archivo DBF
def leer_dbf(archivo):
    try:
        with open("temp_file.dbf", "wb") as f:
            f.write(archivo.getbuffer())
        dbf_data = DBF("temp_file.dbf", encoding="latin1")
        df = pd.DataFrame(iter(dbf_data))
        os.remove("temp_file.dbf")
        return df
    except Exception as e:
        st.markdown(
            f"<div class='mensaje-advertencia'>Error al leer el archivo DBF: {e}</div>",
            unsafe_allow_html=True
        )
        return None

# Procesar datos
def procesar_datos(df):
    df = df[df['LOCALIDAD'] == 'EL TAMBO']
    df = df.dropna(subset=['MEDIDOR'])
    df = df[df['MEDIDOR'].astype(str).str.strip() != '']
    df = df.sort_values(by=['FECHA_EMIS', 'CODCLIENTE', 'MEDIDOR'])
    df['FECHA_EMIS'] = pd.to_datetime(df['FECHA_EMIS'])

    columnas_a_eliminar = [
        "TIPOFACTUR", "CARGO_FIJO", "AGUA", "ALCANTARIL", "VMA", "OTROS_COL","UNIDADES_U","ACTIVIDAD",
        "INTERESES", "IGV", "DEUDA", "REDONDEO", "IMPORTE_RE", "TOTAL","RAZON_SOCI","SERVICIO","CATEGORIA",
        "MESES_DE_D", "ESTADO", "CODIUSUA", "ULTIMOPAGO", "RUTADIST","LATUTUD","LONGITUD",
        "NROORDEN", "OBSERVACIO"
    ]
    df = df.drop(columns=[col for col in columnas_a_eliminar if col in df.columns], errors='ignore')
    return df

# Insertar todos los clientes directamente (sin validación)
def insertar_clientes(df):
    df = df[df['LOCALIDAD'].str.strip().str.upper() == 'EL TAMBO']
    conn = obtener_conexion()
    cursor = conn.cursor()
    
    datos_a_insertar = [
        (int(row['CODCLIENTE']), str(row['DIRECCION']).strip(), str(row['LOCALIDAD']).strip())
        for _, row in df.iterrows()
    ]

    # Insertar ignorando duplicados
    execute_values(
        cursor,
        """
        INSERT INTO public.clientes (codcliente, direccion, localidad)
        VALUES %s
        ON CONFLICT (codcliente) DO NOTHING
        """,
        datos_a_insertar
    )

    conn.commit()
    cursor.close()
    conn.close()
    return len(datos_a_insertar)

# Normalizar volumen
def normalizar_datos(df):
    scaler = MinMaxScaler()
    df['VOLUMEN_LE_NORMALIZADO'] = scaler.fit_transform(df[['VOLUMEN_LE']].fillna(0))
    return df

# Guardar archivo CSV
def guardar_archivo(df, tipo):
    file_name = f"{tipo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    df.to_csv(os.path.join(output_dir, file_name), index=False)
    return file_name

# Interfaz principal
def mostrar_carga_datos():
    st.title("Cargar y Procesar Datos para Predicción")

    # ───────────────────────────────────────────────
    # Validamos si se cambió de módulo
    # ───────────────────────────────────────────────
    modulo_actual = 'cargar_datos'
    modulo_anterior = st.session_state.get('modulo_actual')

    if modulo_anterior != modulo_actual:
        # Si viene de otro módulo, limpiamos los estados previos
        st.session_state['archivo_cargado'] = False
        st.session_state['archivo'] = None
        st.session_state['data_path'] = None

    # Actualizamos el módulo actual
    st.session_state['modulo_actual'] = modulo_actual

    # ───────────────────────────────────────────────
    # Comprobamos si ya se ha cargado un archivo antes
    # ───────────────────────────────────────────────
    if 'archivo_cargado' not in st.session_state:
        st.session_state['archivo_cargado'] = False

    archivo = st.file_uploader("Sube un archivo DBF", type=["dbf"])
    if archivo:
        st.session_state['archivo_cargado'] = True
        st.session_state['archivo'] = archivo
        st.markdown(
            "<div class='mensaje-exito'>Archivo cargado exitosamente. Puedes procesarlo ahora.</div>",
            unsafe_allow_html=True
        )

    if st.session_state['archivo_cargado']:
        st.write("Archivo cargado correctamente.")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("Cancelar"):
                st.session_state['archivo_cargado'] = False
                st.session_state['archivo'] = None
                st.rerun()

        with col2:
            if st.button("Enviar"):
                archivo = st.session_state.get('archivo', None)
                if archivo:
                    df = leer_dbf(archivo)
                    if df is not None:
                        df_procesado   = procesar_datos(df)
                        insertados     = insertar_clientes(df_procesado)
                        df_normalizado = normalizar_datos(df_procesado)

                        file_name = guardar_archivo(df_normalizado, "data_final_con_normalizado")

                        st.session_state['data_path']           = os.path.join(output_dir, file_name)
                        st.session_state['prediccion_generada'] = False
                        st.session_state['archivo_nuevo']       = True
                        st.session_state['data_version']        = datetime.now().timestamp()

                        st.markdown(
                            f"<div class='mensaje-exito'>Archivo guardado como: {file_name}</div>",
                            unsafe_allow_html=True
                        )

                        hora    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        asunto  = "✅ Carga de Datos Procesada"
                        cuerpo  = f"""
Tu carga de datos se ha procesado correctamente.

• Archivo generado: {file_name}
• Registros insertados: {insertados}
• Fecha y hora: {hora}
"""
                        destinos = obtener_correos_destino()
                        enviar_notificacion_general(asunto, cuerpo, destinos)
                        st.success("✅ Notificación enviada por correo a todos los usuarios.")
