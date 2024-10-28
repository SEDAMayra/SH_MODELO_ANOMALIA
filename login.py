import streamlit as st
from PIL import Image
import time
# Importar funciones desde las carpetas correspondientes
from manual.manual import mostrar_manual
from carga.carga import mostrar_carga_datos
from prediccion.prediccion import mostrar_prediccion
from mapa.mapa import mostrar_mapa_calor
from grafico.grafico import mostrar_grafico_barras
from reporte.reporte import mostrar_reporte
from seguimiento.seguimiento import mostrar_seguimiento
import psycopg2
import re


def obtener_conexion():
    return psycopg2.connect(
        host="localhost",
        database="Datos_Modelo",
        user="postgres",
        password="1234",
        port="5433"  # Especifica el puerto aquí, por ejemplo, "5433"
    )


# Configuración de la página
st.set_page_config(page_title="EPS SEDAM Huancayo", page_icon=":droplet:", layout="centered", initial_sidebar_state="collapsed")

# Función para cargar el archivo CSS
# Función para cargar el archivo CSS
def load_css(file_name):
    with open(file_name, 'r', encoding='utf-8') as f:  # Forzar la codificación utf-8
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Parámetro para manejar la navegación entre login y registro
if 'pagina' not in st.session_state:
    st.session_state.pagina = 'login'  # Página inicial es el login


# Función para registrar un nuevo usuario
def registrar_usuario(dni, nombre, password, email):
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    try:
        cursor.execute(
            "INSERT INTO usuarios (dni, nombre, password, email) VALUES (%s, %s, %s, %s)",
            (dni, nombre, password, email)
        )
        conexion.commit()
    except Exception as e:
        st.error(f"Error al registrar el usuario: {e}")
    finally:
        cursor.close()
        conexion.close()

# Función para autenticar un usuario
def autenticar_usuario(dni, password):
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    try:
        cursor.execute("SELECT * FROM usuarios WHERE dni = %s AND password = %s", (dni, password))
        resultado = cursor.fetchone()
        return resultado is not None
    except Exception as e:
        st.error(f"Error al autenticar el usuario: {e}")
        return False
    finally:
        cursor.close()
        conexion.close()

# Función para actualizar la contraseña
def actualizar_contrasena(email, nueva_contrasena):
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    try:
        cursor.execute(
            "UPDATE usuarios SET password = %s WHERE email = %s",
            (nueva_contrasena, email)
        )
        conexion.commit()
        return True
    except Exception as e:
        st.error(f"Error al actualizar la contraseña: {e}")
        return False
    finally:
        cursor.close()
        conexion.close()

# Función para verificar si un correo existe
def verificar_correo(correo):
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    try:
        cursor.execute("SELECT * FROM usuarios WHERE email = %s", (correo,))
        resultado = cursor.fetchone()
        return resultado is not None
    except Exception as e:
        st.error(f"Error al verificar el correo: {e}")
        return False
    finally:
        cursor.close()
        conexion.close()

# Función para mostrar la pantalla de inicio de sesión
def mostrar_login():
    load_css("style/login_style.css")
    with st.form(key='login_form'):
        logo = Image.open('imagenes/logo-sedam-huancayo.png')
        st.image(logo, width=250)
        dni = st.text_input('DNI', max_chars=8)
        password = st.text_input('Contraseña', type='password')
        submit_button = st.form_submit_button('Iniciar sesión')
        forgot_password_button = st.form_submit_button("¿Olvidaste tu contraseña?")
        register_button = st.form_submit_button("¿No tienes una cuenta? Regístrate")
        
        if submit_button:
            if autenticar_usuario(dni, password):
                st.success("¡Inicio de sesión exitoso!")
                time.sleep(1.3)  # Mostrar mensaje por 1.3 segundos
                st.session_state.pagina = 'menu_principal'
                st.rerun()
            else:
                st.error("DNI o contraseña incorrectos.")
                time.sleep(1.3)

        if forgot_password_button:
            st.session_state.pagina = 'olvidaste_contrasena'
            st.rerun()
        elif register_button:
            st.session_state.pagina = 'registro'
            st.rerun()

# Función para mostrar la pantalla de olvido de contraseña
def mostrar_olvidaste_contrasena():
    load_css("style/olvidaste_contrasena_style.css")
    with st.form(key='reset_password_form'):
        st.image('imagenes/logo-sedam-huancayo.png', width=250)
        correo = st.text_input('Correo', value='')

        cambiar_contrasena_button = st.form_submit_button("Cambiar Contraseña")
        cancelar_button = st.form_submit_button("Cancelar")
        
        if cambiar_contrasena_button:
            if verificar_correo(correo):
                st.session_state.email = correo
                st.success("Correo verificado. Ahora puede cambiar la contraseña.")
                time.sleep(1.3)  # Mostrar mensaje por 1.3 segundos
                st.session_state.pagina = "cambiar_contrasena"
                st.rerun()
            else:
                st.error("El correo no está registrado.")

        if cancelar_button:
            st.session_state.pagina = "login"
            st.rerun()

# Función para mostrar la pantalla de cambio de contraseña
def mostrar_cambiar_contrasena():
    load_css("style/cambiar_contrasena_style.css")
    with st.form(key='change_password_form'):
        st.image('imagenes/logo-sedam-huancayo.png', width=250)
        nueva_contrasena = st.text_input("Nueva contraseña", type="password")
        confirmar_contrasena = st.text_input("Confirmar nueva contraseña", type="password")
        cambiar_button = st.form_submit_button("Cambiar la contraseña")

        if cambiar_button:
            if nueva_contrasena == confirmar_contrasena:
                if actualizar_contrasena(st.session_state.email, nueva_contrasena):
                    st.success("Contraseña cambiada con éxito.")
                    time.sleep(1.3)  # Mostrar mensaje por 1.3 segundos
                    st.session_state.pagina = 'login'
                    st.rerun()
                else:
                    st.error("Error al cambiar la contraseña.")
            else:
                st.error("Las contraseñas no coinciden.")

# Función para validar el formato del correo electrónico
def es_correo_valido(email):
    # Expresión regular para validar correos electrónicos
    regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return re.match(regex, email) is not None

# Función para mostrar la pantalla de registro
def mostrar_registro():
    load_css("style/usuarioNuevo_style.css")
    # Formulario de registro
    with st.form(key='registro_form'):
        logo = Image.open('imagenes/logo-sedam-huancayo.png')
        st.image(logo, width=250)
        dni = st.text_input('DNI', max_chars=8)
        nombre = st.text_input('Nombre')
        password = st.text_input('Contraseña', type='password')
        email = st.text_input('Email')

        # Casilla de verificación de Términos y Condiciones con enlace
        acepta_terminos = st.checkbox("He leído y acepto los Términos y Condiciones", help="Debes aceptar los términos para registrarte.")
        st.markdown(
            "<div style='text-align: left; margin-top: -25px;'>"
            "<a href='https://drive.google.com/file/d/1_0sjGEjjoSZe1Wg-7ZPczIE3THRusZGE/view?usp=drive_link' target='_blank' style='color: #007BFF; text-decoration: none;'>Leer Términos y Condiciones</a>"
            "</div>",
            unsafe_allow_html=True
        )

        # Botón de registro
        registrarse_button = st.form_submit_button(label="Registrarse")

        # Validar campos antes de registrar
        if registrarse_button:
            if not dni or not nombre or not password or not email:
                st.error("Por favor, completa todos los campos del formulario.")
            elif not es_correo_valido(email):
                st.error("Por favor, ingresa un correo electrónico válido.")
            elif not acepta_terminos:
                st.error("Debes aceptar los Términos y Condiciones para registrarte.")
            else:
                registrar_usuario(dni, nombre, password, email)
                st.success("¡Registro exitoso!")

        # Botón para volver al login
        volver_login_button = st.form_submit_button(label="¿Ya tienes cuenta? Inicia sesión")
        if volver_login_button:
            st.session_state.pagina = 'login'
            st.rerun()


            
            
def menu_principal():
    load_css("style/menu_style.css")  # Cargar el CSS personalizado
    # Aplicar clase específica al sidebar
    st.markdown("""
        <style>
        [data-testid="stSidebar"] {
            background-color: #ffffff; /* Blanco para la barra lateral */
        }
        </style>
    """, unsafe_allow_html=True)

    st.sidebar.image('imagenes/logo-sedam-huancayo.png', use_column_width=True)
    # Definir las secciones del menú con iconos (pueden ser emojis o etiquetas HTML)
    secciones = {
        "💻 Manual": mostrar_manual,
        "📤 Carga de datos": mostrar_carga_datos,
        "📈 Predicción": mostrar_prediccion,
        "🗺️ Mapa de calor de filtraciones": mostrar_mapa_calor,
        "📊 Gráfico de barras": mostrar_grafico_barras,
        "📑 Reporte": mostrar_reporte,
        "🔄 Seguimiento": mostrar_seguimiento
    }

    # Si no hay ninguna sección seleccionada, iniciar con 'Manual'
    if 'seccion_seleccionada' not in st.session_state:
        st.session_state.seccion_seleccionada = '💻 Manual'

    # Mostrar los botones en la barra lateral con estilos dinámicos
    for seccion in secciones.keys():
        # Si la sección es la seleccionada, le damos la clase "selected"
        if seccion == st.session_state.seccion_seleccionada:
            st.sidebar.markdown(f'<button class="selected">{seccion}</button>', unsafe_allow_html=True)
        else:
            if st.sidebar.button(seccion, key=seccion, on_click=lambda s=seccion: cambiar_seccion(s)):
                pass

    # Mostrar la sección seleccionada
    secciones[st.session_state.seccion_seleccionada]()

    # Espacio en la barra lateral antes del botón de salir
    st.sidebar.markdown("<br><br>", unsafe_allow_html=True)

    # Botón para salir 
    if st.sidebar.button("🔙 Salir", key="salir"):
        cerrar_sesion()
        st.rerun()
         
def cambiar_seccion(seccion):
    # Cambiar el estado de la sección seleccionada
    st.session_state.seccion_seleccionada = seccion
def cerrar_sesion():
    st.session_state.pagina = 'login'

        
        
# Controlador de las pantallas
if st.session_state.pagina == 'login':
    mostrar_login()
elif st.session_state.pagina == 'menu_principal':
    menu_principal()
elif st.session_state.pagina == 'olvidaste_contrasena':
    mostrar_olvidaste_contrasena()
elif st.session_state.pagina == 'cambiar_contrasena':
    mostrar_cambiar_contrasena() 
elif st.session_state.pagina == 'registro':
    mostrar_registro()
