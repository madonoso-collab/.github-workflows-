import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pandas as pd
from jobspy import scrape_jobs

def limpiar_y_filtrar(df):
    if df is None or df.empty:
        print("El DataFrame original llegó vacío de la búsqueda.")
        return pd.DataFrame()
    
    # Imprimir en los logs de GitHub cuántos empleos se encontraron en bruto
    print(f"Empleos encontrados en bruto por JobSpy: {len(df)}")
    
    keywords = ["gerente", "ceo", "cfo", "administracion", "finanzas"]
    df['title_lower'] = df['title'].str.lower()
    
    condicion_puesto = df['title_lower'].apply(
        lambda x: any(kw in str(x) for kw in keywords) if pd.notnull(x) else False
    )
    
    # Flexibilizamos la ubicación: Si contiene Santiago, Chile, Metropolitana, Las Condes o Providencia
    df['location_lower'] = df['location'].str.lower()
    comunas_santiago = ['santiago', 'chile', 'metropolitana', 'condes', 'providencia']
    condicion_ciudad = df['location_lower'].apply(
        lambda x: any(com in str(x) for com in comunas_santiago) if pd.notnull(x) else False
    )
    
    df_filtrado = df[condicion_puesto & condicion_ciudad].copy()
    print(f"Empleos que pasaron el filtro final: {len(df_filtrado)}")
    return df_filtrado.drop(columns=['title_lower', 'location_lower'], errors='ignore')

def buscar_linkedin():
    try:
        jobs = scrape_jobs(
            site_name=["linkedin"],
            search_term='"Gerente General" OR "CEO" OR "CFO" OR "Gerente de Finanzas"',
            location="Santiago, Chile",
            results_wanted=30,
            hours_old=72,  # Dejamos 3 días para asegurar volumen en la prueba
            country_indeed="chile"
        )
        return jobs
    except Exception as e:
        print(f"Error extrayendo de LinkedIn: {e}")
        return pd.DataFrame()

def enviar_correo(df, mensaje_extra=""):
    sender_email = os.environ.get("SMTP_EMAIL")
    sender_password = os.environ.get("SMTP_PASSWORD")
    receiver_email = os.environ.get("RECEIVER_EMAIL")
    
    if not sender_email or not sender_password or not receiver_email:
        print(f"CRÍTICO: Faltan variables de entorno. SMTP_EMAIL: {bool(sender_email)}, SMTP_PASSWORD: {bool(sender_password)}, RECEIVER_EMAIL: {bool(receiver_email)}")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Reporte de Diagnóstico - Alerta de Empleos"
    msg["From"] = sender_email
    msg["To"] = receiver_email

    # FORZAMOS que envíe correo aunque esté vacío para verificar la conexión SMTP
    if df.empty:
        html = f"""
        <html>
        <body>
            <h2>Diagnóstico: Conexión SMTP Exitosa</h2>
            <p>El script funciona y se conecta a tu correo, pero la búsqueda en LinkedIn no arrojó resultados que pasaran los filtros hoy.</p>
            <p><b>Detalles adicionales:</b> {mensaje_extra}</p>
        </body>
        </html>
        """
    else:
        html = """
        <html>
        <head>
            <style>
                table { border-collapse: collapse; width: 100%; font-family: Arial, sans-serif; }
                th, td { text-align: left; padding: 12px; border-bottom: 1px solid #ddd; }
                th { background-color: #1A365D; color: white; }
            </style>
        </head>
        <body>
            <h2>Vacantes Encontradas (Prueba de Diagnóstico)</h2>
            <table>
                <tr><th>Puesto</th><th>Empresa</th><th>Ubicación</th><th>Enlace</th></tr>
        """
        for _, row in df.iterrows():
            html += f"""
                <tr>
                    <td>{row['title']}</td>
                    <td>{row['company']}</td>
                    <td>{row.get('location', 'No especificada')}</td>
                    <td><a href="{row['job_url']}" target="_blank">Ver Postulación</a></td>
                </tr>
            """
        html += "</table></body></html>"

    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("://gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, receiver_email, msg.as_string())
        print("Correo enviado exitosamente.")
    except Exception as e:
        print(f"Error de conexión SMTP al enviar: {e}")

if __name__ == "__main__":
    print("Iniciando extracción de vacantes...")
    df_linkedin = buscar_linkedin()
    
    msg_log = "Búsqueda finalizada."
    if df_linkedin is not None and not df_linkedin.empty:
        msg_log = f"Jobspy devolvió {len(df_linkedin)} filas globales."
        
    df_final = limpiar_y_filtrar(df_linkedin)
    enviar_correo(df_final, msg_log)
