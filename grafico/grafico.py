import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from conexion import obtener_conexion

# Función para obtener los datos desde la base de datos
def obtener_datos():
    conn = obtener_conexion()
    query = """
    SELECT c.direccion, r.volumen_le
    FROM resultados_prediccion r
    JOIN clientes c ON r.codcliente = c.codcliente
    WHERE r.anomalia = 1
    AND r.fecha_prediccion = (SELECT MAX(fecha_prediccion) FROM resultados_prediccion)
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

# Función para mostrar el gráfico de barras en Streamlit
def mostrar_grafico_barras():
    df = obtener_datos()

    st.title("Gráfico de Barras (Volumen de agua anómalo por dirección)")
    fig, ax = plt.subplots()

    # Crear el gráfico de barras horizontales
    bars = ax.barh(df['direccion'], df['volumen_le'], color='orange')

    ax.set_xlabel("Volumen de Agua Anómalo", fontsize=10)
    ax.set_ylabel("Dirección", fontsize=10)
    ax.set_title("Volumen de Agua Anómalo en Diferentes Direcciones", fontsize=12)

    # Añadir etiquetas con los valores encima de las barras
    for bar in bars:
        width = bar.get_width()
        ax.text(width + 0.001, bar.get_y() + bar.get_height()/2,
                f'{width:.2f}', va='center', fontsize=9)

    st.pyplot(fig)
