import os
from dotenv import load_dotenv    # <<< Cambio: carga variables de entorno
import streamlit as st
import pandas as pd
from datetime import datetime
from conexion import obtener_conexion
import matplotlib.pyplot as plt
import io
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

load_dotenv()  # <<< Cambio: carga las vars de .env

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT   = int(os.getenv("SMTP_PORT", 587))
SMTP_USER   = os.getenv("SMTP_USER")
SMTP_PASS   = os.getenv("SMTP_PASS")

# Cargar CSS externo
def cargar_css(file_path):
    with open(file_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

cargar_css("style/seguimiento.css")

# 1) Sincronizar nuevas filtraciones
def sincronizar_datos():
    conn = obtener_conexion()
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT r.codcliente, r.fecha_prediccion, c.direccion
            FROM resultados_prediccion r
            JOIN clientes c ON r.codcliente = c.codcliente
            WHERE r.anomalia = 1
              AND NOT EXISTS (
                SELECT 1 FROM seguimiento_filtraciones sf
                 WHERE sf.codigo_filtracion = r.codcliente
              )
        """)
        nuevas = cursor.fetchall()
        for fila in nuevas:
            cursor.execute("""
                INSERT INTO seguimiento_filtraciones
                  (codigo_filtracion, fecha_deteccion, ubicacion,
                   estado, fecha_resolucion, comentarios)
                VALUES (%s, %s, %s, 'Pendiente', NULL, '')
            """, fila)
    conn.commit()
    conn.close()

# 2) Obtener datos para la tabla
def obtener_datos_filtraciones():
    conn = obtener_conexion()
    df = pd.read_sql("""
        SELECT codigo_filtracion, fecha_deteccion, ubicacion,
               estado, fecha_resolucion, comentarios
        FROM seguimiento_filtraciones
        ORDER BY fecha_deteccion DESC
    """, conn)
    conn.close()
    return df

# 3) Actualizar un registro
def insertar_actualizar_filtracion(codigo, fecha_deteccion, ubicacion, estado, fecha_resolucion, comentarios):
    conn = obtener_conexion()
    with conn.cursor() as cursor:
        cursor.execute("""
            UPDATE seguimiento_filtraciones
               SET estado = %s,
                   fecha_resolucion = %s,
                   comentarios = %s
             WHERE codigo_filtracion = %s
        """, (estado, fecha_resolucion, comentarios, codigo))
    conn.commit()
    conn.close()

# 4) Leer lista de correos de la tabla usuarios
def obtener_correos_destino():
    conn = obtener_conexion()
    df = pd.read_sql("SELECT email FROM usuarios", conn)
    conn.close()
    return df["email"].tolist()

# 5) Enviar correo de notificación individual
def enviar_notificacion(codigo, estado, comentario, destino):
    asunto = "Seguimiento de filtración actualizado"
    cuerpo = f"""
Se ha actualizado el seguimiento de filtración:

• Código: {codigo}
• Nuevo estado: {estado}
• Comentarios: {comentario or '—'}

Fecha y hora: {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
    msg = MIMEMultipart()
    msg["From"] = SMTP_USER
    msg["To"] = destino
    msg["Subject"] = asunto
    msg.attach(MIMEText(cuerpo, "plain"))

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)

# 6) Exportar DataFrame a Excel
def descargar_excel(df):
    buffer = io.BytesIO()
    writer = pd.ExcelWriter(buffer, engine="xlsxwriter")
    df.to_excel(writer, sheet_name="Filtraciones", index=False)
    writer.close()
    return buffer.getvalue()

# 7) Graficar tiempo promedio y ofrecer PDF
def grafico_tiempo_promedio(df):
    df2 = df[df["fecha_resolucion"].notna()].copy()
    if df2.empty:
        st.warning("No hay datos resueltos para graficar.")
        return

    df2["fecha_deteccion"]  = pd.to_datetime(df2["fecha_deteccion"])
    df2["fecha_resolucion"] = pd.to_datetime(df2["fecha_resolucion"])
    df2["dias_resolucion"]   = (df2["fecha_resolucion"] - df2["fecha_deteccion"]).dt.days
    df2["mes_resolucion"]    = df2["fecha_resolucion"].dt.month.map({
        1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",
        7:"Julio",8:"Agosto",9:"Septiembre",10:"Octubre",11:"Noviembre",12:"Diciembre"
    })

    resumen = df2.groupby("mes_resolucion")["dias_resolucion"].mean().reset_index()
    meses   = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
               "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
    resumen["mes_resolucion"] = pd.Categorical(resumen["mes_resolucion"], categories=meses, ordered=True)
    resumen = resumen.sort_values("mes_resolucion")

    fig, ax = plt.subplots(figsize=(8,4))
    ax.plot(resumen["mes_resolucion"], resumen["dias_resolucion"], marker="o", color="blue")
    ax.set_xlabel("Mes de Resolución")
    ax.set_ylabel("Días Promedio de Resolución")
    ax.set_title("Tiempo Promedio de Resolución de Filtraciones")
    ax.grid(True)
    plt.xticks(rotation=45)
    st.pyplot(fig)

    buf = io.BytesIO()
    fig.savefig(buf, format="pdf", bbox_inches="tight")
    buf.seek(0)
    st.download_button(
        label="📄 Descargar gráfico en PDF",
        data=buf,
        file_name="grafico_resolucion.pdf",
        mime="application/pdf"
    )

# 8) Función principal
def mostrar_seguimiento():
    st.subheader("Estado de filtraciones identificadas por la predicción")

    # ─── Checkbox “Activar Notificaciones” con texto blanco y fondo transparente ───
    activar_notificaciones = st.checkbox("🔔 Activar Notificaciones", value=True)
    # ─── CSS para forzar texto blanco en el label del checkbox ───
    st.markdown("""
    <style>
      /* El texto del segundo div dentro del label (donde está el texto) en blanco */
      .stCheckbox label > div:nth-child(2) {
        color: white !important;
        font-weight: bold !important;
      }
      /* El fondo y padding del checkbox transparentes */
      .stCheckbox > div {
        background-color: transparent !important;
        padding: 0 !important;
        margin: 0 !important;
      }
    </style>
    """, unsafe_allow_html=True)
    # ────────────────────────────────────────────────────────────────────────────────

    # Sincronizar y obtener datos
    sincronizar_datos()
    df = obtener_datos_filtraciones()
    if df.empty:
        st.info("No se encontraron registros.")
        return

    # Asegurar visibilidad de botones
    st.markdown("""
    <style>
      .stDownloadButton button, .stButton button {
        color: black !important;
        font-weight: bold;
      }
    </style>
    """, unsafe_allow_html=True)

    # Cabecera de la tabla
    st.markdown("""
    <style>
      .header-table {
        display: flex; background-color: #00b4d8; color: white;
        font-weight: bold; padding: 12px 5px; margin-top: 20px;
        border-radius: 5px; border: 1px solid white;
      }
      .cell-codigo { flex-basis:16%; text-align:center; }
      .cell-fecha { flex-basis:22%; text-align:center; }
      .cell-ubicacion { flex-basis:32%; text-align:center; }
      .cell-estado { flex-basis:26%; text-align:center; }
      .cell-fecha-resolucion { flex-basis:28%; text-align:center; }
      .cell-comentarios { flex-basis:26%; text-align:center; }
    </style>
    <div class="header-table">
      <div class="cell-codigo">Código</div>
      <div class="cell-fecha">Fecha de Detección</div>
      <div class="cell-ubicacion">Ubicación</div>
      <div class="cell-estado">Estado</div>
      <div class="cell-fecha-resolucion">Fecha de Resolución</div>
      <div class="cell-comentarios">Comentarios</div>
    </div>
    """, unsafe_allow_html=True)

    # Filas editables
    cambios = []
    for idx, row in df.iterrows():
        cols = st.columns([1.8,2.4,3.2,3.0,3.0,2.8])
        cols[0].markdown(f"<div style='text-align:center'>{row['codigo_filtracion']}</div>", unsafe_allow_html=True)
        cols[1].markdown(f"<div style='text-align:center'>{row['fecha_deteccion'].strftime('%Y-%m-%d')}</div>", unsafe_allow_html=True)
        cols[2].markdown(f"<div style='text-align:center'>{row['ubicacion']}</div>", unsafe_allow_html=True)
        nuevo_estado = cols[3].selectbox("", ["Pendiente","Proceso","Resuelta"],
            index=["Pendiente","Proceso","Resuelta"].index(row["estado"]), key=f"estado_{idx}")
        nueva_fecha = datetime.now().date() if nuevo_estado=="Resuelta" else None
        mostrar_fecha = row["fecha_resolucion"].strftime("%Y-%m-%d") if row["fecha_resolucion"] else "N/A"
        cols[4].markdown(f"<div style='text-align:center'>{mostrar_fecha}</div>", unsafe_allow_html=True)
        nuevo_comentario = cols[5].text_input("", value=row["comentarios"] or "", key=f"comentario_{idx}")

        cambios.append({
          "codigo": row["codigo_filtracion"],
          "fecha_deteccion": row["fecha_deteccion"],
          "ubicacion": row["ubicacion"],
          "estado": nuevo_estado,
          "fecha_resolucion": nueva_fecha,
          "comentarios": nuevo_comentario
        })

    # Botón de actualizar y notificaciones condicionales
    if st.button("Actualizar Estado"):
        correos = obtener_correos_destino()
        cambios_guardados = 0
        for idx, cambio in enumerate(cambios):
            orig = df.iloc[idx]
            if (cambio["estado"] != orig["estado"] or
                (orig["comentarios"] or "") != (cambio["comentarios"] or "") or
                (orig["fecha_resolucion"] != cambio["fecha_resolucion"])):
                insertar_actualizar_filtracion(**cambio)
                cambios_guardados += 1
                # Solo enviar correo si está activo
                if activar_notificaciones:
                    for dest in correos:
                        enviar_notificacion(cambio["codigo"], cambio["estado"], cambio["comentarios"], dest)

        if cambios_guardados:
            msg = f"¡{cambios_guardados} cambios guardados"
            if activar_notificaciones:
                msg += " y notificados!"
            else:
                msg += "!"
            st.success(msg)
            st.rerun()
        else:
            st.info("No se detectaron cambios.")

    # Separador y botones finales
    st.markdown("---")
    col1, _, col3 = st.columns([2,1,2])
    with col1:
        ver_grafico = st.button("📊 Ver gráfico de resolución")
    with col3:
        excel_data = descargar_excel(df)
        st.download_button(
          label="📥 Exportar reporte de filtraciones",
          data=excel_data,
          file_name="reporte_filtraciones.xlsx",
          mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    if ver_grafico:
        grafico_tiempo_promedio(df)
