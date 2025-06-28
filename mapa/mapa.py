import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from conexion import obtener_conexion

# Función para obtener los datos
def obtener_datos():
    conn = obtener_conexion()
    query = """
    SELECT codcliente, mse_new AS probabilidad, volumen_le AS impacto, 
           error_reconstruccion, threshold, anomalia
    FROM resultados_prediccion
    WHERE anomalia = 1
    AND fecha_prediccion = (SELECT MAX(fecha_prediccion) FROM resultados_prediccion)
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df


# Función para mostrar el gráfico de calor
def mostrar_mapa_calor():
    st.title("Mapa de Calor de Filtraciones de Agua (Clientes con Anomalía)")
    
    df = obtener_datos()
    
    if df.empty:
        st.warning("⚠️ No se encontraron datos con anomalías en la última predicción.")
        return
    
    colors = df['impacto']
    sizes = np.where(df['error_reconstruccion'] > df['threshold'], 100, 50)  
    
    fig, ax = plt.subplots(figsize=(10, 6))
    scatter = ax.scatter(df['codcliente'], df['error_reconstruccion'], c=colors, s=sizes, cmap="Reds", edgecolors="black", alpha=0.7)
    
    umbral = df['threshold'].iloc[0]
    ax.axhline(umbral, color="blue", linestyle="--", label=f"Umbral = {umbral:.2e}")
    
    for i, txt in enumerate(df['error_reconstruccion']):
        ax.annotate(f"{txt:.2e}", (df['codcliente'].iloc[i], df['error_reconstruccion'].iloc[i] + 1e-7),
                    color="black", ha='center', fontsize=9)
    
    ax.set_xticks(df['codcliente'])
    ax.set_xticklabels(df['codcliente'].astype(int), rotation=45)
    
    cbar = plt.colorbar(scatter)
    cbar.set_label("Impacto")
    ax.set_xlabel("Código de Cliente")
    ax.set_ylabel("Error de Reconstrucción")
    ax.legend()
    
    st.pyplot(fig)
