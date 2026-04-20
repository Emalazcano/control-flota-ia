import streamlit as st
import google.generativeai as genai
import os

# Configura tu clave aquí manualmente solo para probar
API_KEY = "AIzaSyD5K6otL2EWrRdXS6bxCNaw9R5Vv92GDMs" 
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

st.title("Test de Conexión IA")

if st.button("Probar conexión a Google"):
    with st.spinner("Conectando..."):
        try:
            response = model.generate_content("Hola, si ves esto es que la conexión funciona.")
            st.success("¡Conexión exitosa!")
            st.write(response.text)
        except Exception as e:
            st.error(f"Error técnico: {e}")
