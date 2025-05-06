# conexion.py
import psycopg2

def obtener_conexion():
    return psycopg2.connect(
        host="svtp1primay.postgres.database.azure.com",
        database="Datos_Modelo",
        user="administrador",
        password="PriMay2002%",
        port="5432"  # Especifica el puerto aquí, por ejemplo, "5433"
    )
