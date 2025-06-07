import streamlit as st
def mostrar_manual():
    st.title("Manual")
    st.write("Aquí puedes ver el video del manual con los controles predeterminados.")

    # Cargar el video localmente usando Streamlit
    st.video('imagenes/Videoo.mp4')

