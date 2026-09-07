import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pandas as pd
from jobspy import scrape_jobs

def limpiar_y_filtrar(df):
    if df.empty:
        return df
    
    # Términos solicitados obligatorios
    keywords = ["gerente", "ceo", "cfo", "administracion y finanzas", "finanzas"]
    
    # Filtrado lógico en minúsculas para normalizar
    df['title_lower'] = df['title'].str.lower()
    
    # Asegurar coincidencia exacta con tus palabras clave
    condicion_puesto = df['title_lower'].apply(
        lambda x: any(kw in x for kw in keywords) if pd.notnull(x) else False
    )
    
    # Filtrar estrictamente por Santiago de Chile
    df['location_lower'] = df['location'].str.lower()
    condicion_ciudad = df['location_lower'].str.contains('santiago', na=False)
    
    df_filtrado = df[condicion_puesto & condicion_ciudad].copy()
    return df_filtrado.drop(columns=['title_lower', 'location_lower'], errors='ignore')

def buscar_linkedin():
    try:
        # jobspy busca en LinkedIn sin autenticación de manera eficiente
        jobs = scrape_jobs(
            site_name=["linkedin"],
            search_term='"Gerente General" OR "CEO" OR "CFO" OR "Gerente de Finanzas"',
            location="Santiago, Chile",
            results_wanted=30,
            hours_old=24, # Solo lo del último día
            country_indeed="chile"
        )
        return jobs
    except Exception as e:
        print(f"Error extrayendo de LinkedIn: {e}")
        return pd.DataFrame()

def enviar_correo(df):
    sender_email = os.environ.get("SMTP_EMAIL")
    sender_password = os.environ.get("SMTP_PASSWORD")
    receiver_email = os.environ.get("RECEIVER_EMAIL")
    
    if not sender_email or !sender_password or !receiver_email:
        print("Faltan variables de entorno para enviar el correo.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Alerta Diaria de Vacantes Ejecutivas - Santiago"
    msg["] = sender_email
    msg["To"] = receiver_email

    if df.empty:
        html = "<p>No se encontraron nuevas vacantes directivas que cumplan los criterios en las últimas 24 horas.</p>"
    else:
        # Construcción de la tabla en HTML
        html = """
        <html>
        <head>
            <style>
                table { border-collapse: collapse; width: 100%; font-family: Arial, sans-serif; }
                th, td { text-align: left; padding: 12px; border-bottom: 1px solid #ddd; }
                th { background-color: #1A365D; color: white; }
                tr:hover { background-color: #f5f5f5; }
                a { color: #2B6CB0; text-decoration: none; font-weight: bold; }
            </style>
        </head>
        <body>
            <h2>Vacantes del día</h2>
            <table>
                <tr>
                    <th>Puesto</th>
                    <th>Empresa</th>
                    <th>Enlace</th>
                </tr>
        """
        for _, row in df.iterrows():
            html += f"""
                <tr>
                    <td>{row['title']}</td>
                    <td>{row['company']}</td>
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
        print(f"Error al enviar correo: {e}")

if __name__ == "__main__":
    print("Iniciando extracción de vacantes...")
    df_linkedin = buscar_linkedin()
    
    # Aquí puedes concatenar funciones adicionales para BeautifulSoup (Chiletrabajos/Laborum)
    df_total = df_linkedin 
    
    df_final = limpiar_y_filtrar(df_total)
    enviar_correo(df_final)
