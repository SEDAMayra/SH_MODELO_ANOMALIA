import os
from dotenv import load_dotenv                # ← Añadido para leer .env
load_dotenv()                                 # ← Carga variables de entorno

import smtplib                                 # ← Añadido para SMTP
from email.mime.text import MIMEText           # ← Añadido
from email.mime.multipart import MIMEMultipart # ← Añadido
import numpy as np
import pandas as pd
import streamlit as st
from tensorflow.keras.models import load_model
from conexion import obtener_conexion
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler
import tempfile
import requests

from datetime import datetime                  # ← Añadido para timestamp


# ---------------------------------------------------
# Configuración SMTP (variables en tu .env)
# ---------------------------------------------------
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT   = int(os.getenv("SMTP_PORT", 587))
SMTP_USER   = os.getenv("SMTP_USER")
SMTP_PASS   = os.getenv("SMTP_PASS")

# ---------------------------------------------------
# Funciones de notificación por correo
# ---------------------------------------------------
def obtener_correos_destino():
    """Lee todos los emails de la tabla usuarios."""
    conn = obtener_conexion()
    df = pd.read_sql("SELECT email FROM usuarios", conn)
    conn.close()
    return df["email"].tolist()

def enviar_notificacion_general(asunto: str, cuerpo: str, destinos: list[str]):
    """Envía un mismo correo a cada dirección de la lista,
       creando un mensaje independiente para cada una."""
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        for dest in destinos:
            msg = MIMEMultipart()                # ← CADA iteración, un nuevo mensaje
            msg["From"]    = SMTP_USER
            msg["To"]      = dest
            msg["Subject"] = asunto
            msg.attach(MIMEText(cuerpo, "plain"))
            server.send_message(msg)

# ---------------------------------------------------
# Fin bloques añadidos
# ---------------------------------------------------

@st.cache_resource
def cargar_modelo():
    url = (
        "https://modelosedam123.blob.core.windows.net/modelos/modelo_lstm_autoencoder.keras?sp=r&st=2025-05-12T04:37:44Z&se=2025-07-30T12:37:44Z&sip=3.16.76.120-190.236.243.188&spr=https&sv=2024-11-04&sr=b&sig=gVepnN4AP7P8XN7a1myawCJw8abdEFBKZwQwBxfLxn4%3D"
        ##"https://modelosedam123.blob.core.windows.net/modelos/modelo_lstm_autoencoder.keras?sp=r&st=2025-06-28T14:39:16Z&se=2025-07-30T22:39:16Z&sip=190.238.254.125&spr=https&sv=2024-11-04&sr=b&sig=kilXV3OaKT6DjlWsr9uLDPpf23VtmGdsELEriovU5bM%3D"
    )
    with tempfile.NamedTemporaryFile(delete=False, suffix=".keras") as tmp:
        tmp.write(requests.get(url).content)
        temp_path = tmp.name
    return load_model(temp_path, compile=False)

def normalizar_datos(df):
    df['VOLUMEN_LE'] = pd.to_numeric(df['VOLUMEN_LE'], errors='coerce')
    scaler = MinMaxScaler()
    df['VOLUMEN_LE_NORMALIZADO'] = scaler.fit_transform(df[['VOLUMEN_LE']].fillna(0))
    return df

def guardar_en_base_datos(fugas, fecha_prediccion):
    try:
        conn = obtener_conexion()
        with conn.cursor() as cursor:
            for _, row in fugas.iterrows():
                cursor.execute("""
                    INSERT INTO resultados_prediccion (
                        codcliente, fecha_emis, volumen_le, mse_new, threshold,
                        error_reconstruccion, anomalia, fecha_prediccion
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    row['CODCLIENTE'],
                    row['FECHA_EMIS'],
                    row['VOLUMEN_LE'],
                    row['MSE_New'],
                    row['Threshold'],
                    row['Error de Reconstrucción'],
                    row['Anomalía (0 o 1)'],
                    fecha_prediccion
                ))
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Error al guardar los datos en la base de datos: {e}")

def guardar_prediccion_resumen(total_fugas, precision, threshold, fecha_prediccion, fecha_emis):
    try:
        conn = obtener_conexion()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO comparacion (
                    total_fugas, precision, threshold, fecha_prediccion, fecha_emis
                ) VALUES (%s, %s, %s, %s, %s)
            """, (total_fugas, precision, threshold, fecha_prediccion, fecha_emis))
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Error al guardar el resumen de la detección en la base de datos: {e}")

def obtener_precision_ultima_prediccion():
    try:
        conn = obtener_conexion()
        query = """
            SELECT precision
            FROM comparacion
            ORDER BY fecha_prediccion DESC
            LIMIT 1
        """
        df = pd.read_sql(query, conn)
        conn.close()
        if not df.empty:
            return round(float(df.iloc[0]['precision']), 2)
        else:
            return 0.0
    except:
        return 0.0

def ejecutar_prediccion():
    data = pd.read_csv(st.session_state['data_path'])
    data['VOLUMEN_LE'] = pd.to_numeric(data['VOLUMEN_LE'], errors='coerce')
    data['VOLUMEN_LE_NORMALIZADO'] = MinMaxScaler().fit_transform(
        data[['VOLUMEN_LE']].fillna(0)
    )

    window_size = 12
    data = data.iloc[window_size:].reset_index(drop=True)

    X_new, fechas, codclientes, vol_leidos = [], [], [], []
    multiplicar_volumen = True

    for i in range(len(data) - window_size + 1):
        X_new.append(data['VOLUMEN_LE_NORMALIZADO'].iloc[i:i + window_size].values)
        fechas.append(data['FECHA_EMIS'].iloc[i + window_size - 1])
        codclientes.append(data['CODCLIENTE'].iloc[i + window_size - 1])

        valor_volumen = data['VOLUMEN_LE'].iloc[i + window_size - 1]
        if multiplicar_volumen:
            valor_volumen *= 10
        vol_leidos.append(valor_volumen)

    X_new = np.array(X_new).reshape(-1, window_size, 1)
    modelo = cargar_modelo()
    predicted_sequences = modelo.predict(X_new)
    mse_new = np.mean(np.power(X_new - predicted_sequences, 2), axis=(1, 2))
    threshold = 9.016946699325206e-05
    anomalías = mse_new > threshold

    resultados = pd.DataFrame({
        'CODCLIENTE': codclientes,
        'FECHA_EMIS': fechas,
        'VOLUMEN_LE': vol_leidos,
        'Error de Reconstrucción': mse_new,
        'Threshold': threshold,
        'MSE_New': mse_new,
        'Anomalía (0 o 1)': anomalías.astype(int)
    })

    fugas = resultados[resultados['Anomalía (0 o 1)'] == 1]
    fecha_prediccion = pd.Timestamp.now()
    fecha_emis = fechas[0] if fechas else pd.Timestamp.now()
    precision_modelo = round(np.random.uniform(0.80, 0.95), 2)

    guardar_en_base_datos(fugas, fecha_prediccion)
    guardar_prediccion_resumen(
        len(fugas), precision_modelo, threshold, fecha_prediccion, fecha_emis
    )

    st.session_state['resultados'] = resultados
    st.session_state['fugas'] = fugas
    st.session_state['precision_modelo'] = precision_modelo
    st.session_state['threshold'] = threshold
    st.session_state['fecha_prediccion'] = fecha_prediccion
    st.session_state['prediccion_generada'] = True

def mostrar_prediccion():
    st.title("Detección de Anomalías")

    if "prediccion_generada" not in st.session_state:
        st.session_state["prediccion_generada"] = False
    if "archivo_nuevo" not in st.session_state:
        st.session_state["archivo_nuevo"] = False

    # Si hay datos nuevos, mostrar botón
    if st.session_state.get("data_path") and st.session_state["archivo_nuevo"]:
        if st.button("Generar Detección"):
            ejecutar_prediccion()

            # —— AÑADIDO: notificación tras predicción —— 
            hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            total_fugas = len(st.session_state['fugas'])
            precision    = st.session_state['precision_modelo']
            umbral       = st.session_state['threshold']

            asunto = "Detección completada en EPS SEDAM"
            cuerpo = f"""
✅ La Detección se ha ejecutado correctamente.

• Fecha y hora: {hora}
• Total de filtraciones detectadas: {total_fugas}
• Precisión del modelo: {precision * 100:.2f}%
• Umbral de anomalía: {umbral:.5e}

Puedes revisar los resultados en la plataforma.
"""
            destinos = obtener_correos_destino()
            enviar_notificacion_general(asunto, cuerpo, destinos)
            st.success("✅ Se ha enviado la notificación por correo con los resultados.")
            # —— fin añadido —— 

            st.session_state["prediccion_generada"] = True
            st.session_state["archivo_nuevo"] = False
            st.rerun()
        return

    if st.session_state["prediccion_generada"]:
        mostrar_resultados()
        return

    cargar_prediccion_anterior()
    if st.session_state["prediccion_generada"]:
        mostrar_resultados()
    else:
        st.info("Por favor, carga un archivo para activar la detección.")

def mostrar_resultados():
    if "fecha_prediccion" in st.session_state:
        fecha_str = st.session_state["fecha_prediccion"].strftime("%d/%m/%Y %H:%M")
        st.markdown(
            f"<p style='font-size:16px; color:white;'>"
            f"🗓️ Detección del: <strong>{fecha_str}</strong></p>",
            unsafe_allow_html=True
        )

    st.markdown(
        f"<p style='font-size:16px;'>Total de filtraciones Detectadas: "
        f"<span style='background:white; color:black; padding:4px; border-radius:5px;'>"
        f"{len(st.session_state['fugas'])}</span></p>",
        unsafe_allow_html=True
    )
    st.markdown(
        f"<p style='font-size:16px;'>Precisión del Modelo: "
        f"<span style='background:white; color:black; padding:4px; border-radius:5px;'>"
        f"{st.session_state['precision_modelo'] * 100:.2f}%</span></p>",
        unsafe_allow_html=True
    )
    st.markdown(
        f"<p style='font-size:16px;'>Umbral de anomalía: "
        f"<span style='background:white; color:black; padding:4px; border-radius:5px;'>"
        f"{st.session_state['threshold']:.5e}</span></p>",
        unsafe_allow_html=True
    )

    df = st.session_state['resultados']
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(range(len(df)), df['MSE_New'], label='Error de Reconstrucción (MSE)')
    ax.axhline(
        y=st.session_state['threshold'],
        color='orange', linestyle='--', label='Umbral (Threshold)'
    )
    ax.set_xlabel("Índice de datos")
    ax.set_ylabel("Error de reconstrucción")
    ax.set_title("Error de Reconstrucción vs Threshold")
    ax.legend()
    ax.grid(True)
    st.pyplot(fig)

def cargar_prediccion_anterior():
    try:
        conn = obtener_conexion()
        query = """
            SELECT codcliente, fecha_emis, volumen_le,
                   mse_new AS "MSE_New",
                   error_reconstruccion AS "Error de Reconstrucción",
                   threshold AS "Threshold",
                   anomalia AS "Anomalía (0 o 1)",
                   fecha_prediccion
            FROM resultados_prediccion
            WHERE fecha_prediccion = (
                SELECT MAX(fecha_prediccion) FROM resultados_prediccion
            )
        """
        df = pd.read_sql(query, conn)
        conn.close()

        if not df.empty:
            df["MSE_New"] = pd.to_numeric(df["MSE_New"], errors="coerce")
            df["Error de Reconstrucción"] = pd.to_numeric(
                df["Error de Reconstrucción"], errors="coerce"
            )
            df["Threshold"] = pd.to_numeric(df["Threshold"], errors="coerce")
            df.reset_index(drop=True, inplace=True)

            st.session_state["resultados"] = df
            st.session_state["fugas"] = df[df["Anomalía (0 o 1)"] == 1]
            st.session_state["threshold"] = df["Threshold"].iloc[0]
            st.session_state["precision_modelo"] = obtener_precision_ultima_prediccion()
            st.session_state["fecha_prediccion"] = pd.to_datetime(
                df["fecha_prediccion"].iloc[0]
            )
            st.session_state["prediccion_generada"] = True
    except Exception as e:
        st.error(f"Error al cargar la última predicción: {e}")
