import numpy as np
import pandas as pd
import streamlit as st
import io
from conexion import obtener_conexion
from reportlab.lib.pagesizes import landscape, letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
from datetime import datetime

# --- FUNCIONES DE APOYO ---
def clasificar_severidad(error_reconstruccion, threshold):
    if error_reconstruccion > threshold * 1.05:
        return "Alta"
    elif threshold <= error_reconstruccion <= threshold * 1.05:
        return "Media"

def obtener_datos_anomalias():
    conn = obtener_conexion()
    query = """
        SELECT 
            r.codcliente, c.direccion, r.fecha_emis, r.volumen_le, 
            r.error_reconstruccion, r.threshold, r.anomalia, r.fecha_prediccion
        FROM resultados_prediccion AS r
        JOIN clientes AS c ON r.codcliente = c.codcliente
        WHERE r.anomalia = 1
        AND r.fecha_prediccion = (SELECT MAX(fecha_prediccion) FROM resultados_prediccion)
        ORDER BY r.fecha_prediccion DESC
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def obtener_precision_ultima_prediccion():
    conn = obtener_conexion()
    query = """
        SELECT precision FROM comparacion
        ORDER BY fecha_prediccion DESC
        LIMIT 1
    """
    precision = pd.read_sql(query, conn)
    conn.close()
    if not precision.empty:
        return f"{precision.iloc[0]['precision'] * 100:.2f}%"
    else:
        return "No disponible"

def generar_pdf(df):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(letter))
    width, height = landscape(letter)

    c.setFont("Helvetica-Bold", 16)
    c.drawString(250, height - 40, "Informe de Filtraciones")

    data = [df.columns.tolist()] + df.values.tolist()
    table = Table(data, colWidths=[90, 150, 90, 90, 110, 90, 70])

    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ])
    table.setStyle(style)

    table.wrapOn(c, width, height)
    table_height = 20 * len(data)
    table.drawOn(c, 30, height - 80 - table_height)

    c.save()
    pdf = buffer.getvalue()
    buffer.close()
    return pdf

def mostrar_historial_mes_actual():
    df = obtener_datos_anomalias()

    if df.empty:
        st.warning("⚠️ No hay historial que mostrar")
        return

    # Agregamos columnas necesarias para guardar
    df["Severidad"] = df.apply(lambda row: clasificar_severidad(row["error_reconstruccion"], row["threshold"]), axis=1)
    df["Precisión"] = obtener_precision_ultima_prediccion()
    df["Volumen Actual"] = df["volumen_le"].astype(str) + "L"
    df["Fecha de Lectura"] = pd.to_datetime(df["fecha_emis"]).dt.strftime("%d/%m/%Y")
    df["Fecha de Predicción"] = pd.to_datetime(df["fecha_prediccion"]).dt.strftime("%d/%m/%Y")

    # Creamos una copia solo para mostrar (renombrada)
    df_vista = df[[
        "codcliente", "direccion", "Fecha de Lectura", "Volumen Actual",
        "Severidad", "Precisión", "Fecha de Predicción"
    ]].copy()
    df_vista.columns = [
        "Código de Cliente", "Dirección", "Fecha de Lectura",
        "Volumen Actual", "Severidad", "Precisión", "Fecha de Predicción"
    ]

    # --- Estilos ---
    st.markdown("""
        <style>
        .report-table {
            margin-left: auto;
            margin-right: auto;
            width: 70%;
            background-color: white;
            color: black;
            border-collapse: collapse;
            font-size: 13px;
        }
        .report-table th, .report-table td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: center;
        }
        .report-table th {
            background-color: white;
            color: black;
            font-weight: bold;
            font-size: 14px;
        }
        div.stDownloadButton > button {
            background-color: #0072C6;
            color: white;
            font-weight: bold;
            padding: 10px 20px;
            border-radius: 8px;
            border: none;
            margin: 5px;
        }
        div.stDownloadButton > button:hover {
            background-color: #005999;
            color: white;
        }
        </style>
    """, unsafe_allow_html=True)

    st.subheader("Historial del mes actual")
    st.markdown(df_vista.to_html(index=False, classes="report-table"), unsafe_allow_html=True)

    # Exportar
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_vista.to_excel(writer, index=False, sheet_name='Filtraciones')
    excel_data = output.getvalue()
    pdf_file = generar_pdf(df_vista)

    col1, col2 = st.columns(2)
    with col1:
        st.download_button("📥 Descargar Excel", excel_data, "informe_filtraciones_mes_actual.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with col2:
        st.download_button("📥 Descargar PDF", pdf_file, "informe_filtraciones_mes_actual.pdf", "application/pdf")

    # Guarda el original, no el renombrado
    guardar_en_historial(df)
    actualizar_alertas_criticas()



def guardar_en_historial(df):
    conn = obtener_conexion()
    cursor = conn.cursor()

    insert_query = """
        INSERT INTO HistorialActual (
            codcliente, direccion, fecha_lectura, volumen_actual,
            severidad, precision, fecha_prediccion
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
    """

    for _, row in df.iterrows():
        cursor.execute(insert_query, (
            row["codcliente"],
            row["direccion"],
            datetime.strptime(row["Fecha de Lectura"], "%d/%m/%Y").date(),
            row["Volumen Actual"],
            row["Severidad"],
            row["Precisión"],
            datetime.strptime(row["Fecha de Predicción"], "%d/%m/%Y").date()
        ))

    conn.commit()
    cursor.close()
    conn.close()


def obtener_alertas_criticas_por_fecha(fecha):
    conn = obtener_conexion()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(DISTINCT codcliente) 
        FROM HistorialActual
        WHERE severidad = 'Alta'
        AND DATE(fecha_prediccion) = %s
    """, (fecha,))
    resultado = cursor.fetchone()
    conn.close()
    return resultado[0] if resultado else 0

def obtener_datos_periodo(fecha_prediccion):
    conn = obtener_conexion()
    query = f"""
        SELECT fecha_prediccion, fecha_emis, total_fugas, precision
        FROM comparacion
        WHERE DATE(fecha_prediccion) = '{fecha_prediccion}'
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def mostrar_comparacion_periodos():
    st.subheader("Comparación de periodos de predicción")
    if 'resumen_comparacion' not in st.session_state:
        st.session_state['resumen_comparacion'] = None

    fecha_1 = st.date_input("Selecciona la fecha del Periodo 1", key="fecha_prediccion_1")
    fecha_2 = st.date_input("Selecciona la fecha del Periodo 2", key="fecha_prediccion_2")

    if st.button("Comparar Fechas de Predicción", key="btn_comparar_fechas"):
        df1 = obtener_datos_periodo(fecha_1)
        df2 = obtener_datos_periodo(fecha_2)

        if df1.empty or df2.empty:
            st.warning("⚠️ No se encontraron datos para una o ambas fechas seleccionadas.")
            return

        resumen = pd.DataFrame([
            {
                "Fecha de Predicción": df1["fecha_prediccion"].iloc[0].strftime("%Y-%m-%d"),
                "Fecha de Lectura": pd.to_datetime(df1["fecha_emis"].iloc[0]).strftime("%B").capitalize(),
                "Total Filtraciones Detectadas": int(df1["total_fugas"].sum()),
                "Precisión del Modelo (%)": f"{df1['precision'].mean() * 100:.0f}",
                "Alertas Críticas": obtener_alertas_criticas_por_fecha(fecha_1)
            },
            {
                "Fecha de Predicción": df2["fecha_prediccion"].iloc[0].strftime("%Y-%m-%d"),
                "Fecha de Lectura": pd.to_datetime(df2["fecha_emis"].iloc[0]).strftime("%B").capitalize(),
                "Total Filtraciones Detectadas": int(df2["total_fugas"].sum()),
                "Precisión del Modelo (%)": f"{df2['precision'].mean() * 100:.0f}",
                "Alertas Críticas": obtener_alertas_criticas_por_fecha(fecha_2)
            }
        ])
        st.session_state['resumen_comparacion'] = resumen

    if st.session_state['resumen_comparacion'] is not None:
        resumen = st.session_state['resumen_comparacion']

        st.markdown("""
            <style>
            .comparacion-table {
                margin-left: auto;
                margin-right: auto;
                width: 80%;
                background-color: white;
                color: black;
                border-collapse: collapse;
                font-size: 13px;
                margin-top: 15px;
            }
            .comparacion-table th, .comparacion-table td {
                border: 1px solid #ddd;
                padding: 10px;
                text-align: center;
            }
            .comparacion-table th {
                background-color: #E6F0FA;
                color: black;
                font-weight: bold;
                font-size: 14px;
            }
            div.stDownloadButton > button {
                background-color: #0072C6;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 8px;
                border: none;
                margin: 5px;
            }
            div.stDownloadButton > button:hover {
                background-color: #005999;
                color: white;
            }
            </style>
        """, unsafe_allow_html=True)

        st.markdown(resumen.to_html(index=False, classes="comparacion-table"), unsafe_allow_html=True)

        # Excel export
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            resumen.to_excel(writer, index=False, sheet_name='Comparacion')
        excel_data = output.getvalue()

        # PDF export
        pdf_output = io.BytesIO()
        c = canvas.Canvas(pdf_output, pagesize=landscape(letter))
        width, height = landscape(letter)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(200, height - 40, "Informe de Comparación de Predicción")

        data = [resumen.columns.tolist()] + resumen.values.tolist()
        table = Table(data, colWidths=[120] * len(data[0]))

        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ])
        table.setStyle(style)
        table.wrapOn(c, width, height)
        table_height = 20 * len(data)
        table.drawOn(c, 30, height - 80 - table_height)
        c.save()
        pdf_data = pdf_output.getvalue()

        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                label="📥 Descargar Excel",
                data=excel_data,
                file_name="informe_comparacion.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        with col2:
            st.download_button(
                label="📥 Descargar PDF",
                data=pdf_data,
                file_name="informe_comparacion.pdf",
                mime="application/pdf"
            )

def mostrar_reporte():
    st.title("Reporte")
    if "vista_reporte" not in st.session_state:
        st.session_state.vista_reporte = None
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Historial de anomalía detectada de mes actual", key="btn_historial_mes_actual"):
            st.session_state.vista_reporte = "historial"
    with col2:
        if st.button("Comparar Periodos", key="btn_mostrar_comparacion_periodos"):
            st.session_state.vista_reporte = "comparar"
    if st.session_state.vista_reporte == "historial":
        mostrar_historial_mes_actual()
    if st.session_state.vista_reporte == "comparar":
        mostrar_comparacion_periodos()

def guardar_prediccion_resumen(total_fugas, precision, threshold, fecha_prediccion, fecha_emis):
    try:
        conn = obtener_conexion()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO comparacion (
                    total_fugas, precision, threshold,
                    fecha_prediccion, fecha_emis
                ) VALUES (%s, %s, %s, %s, %s)
            """, (total_fugas, precision, threshold, fecha_prediccion, fecha_emis))
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Error al guardar el resumen de la predicción en la base de datos: {e}")

def actualizar_alertas_criticas():
    conn = obtener_conexion()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT fecha_prediccion, COUNT(*) AS total,
               SUM(CASE WHEN severidad = 'Alta' THEN 1 ELSE 0 END) AS alertas
        FROM HistorialActual
        GROUP BY fecha_prediccion
    """)
    resultados = cursor.fetchall()
    for fecha_prediccion, total, alertas in resultados:
        cursor.execute("""
            UPDATE comparacion
            SET alertas_criticas = %s
            WHERE fecha_prediccion = %s
        """, (alertas, fecha_prediccion))
    conn.commit()
    cursor.close()
    conn.close()
