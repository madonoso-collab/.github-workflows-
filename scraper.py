import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pandas as pd
from jobspy import scrape_jobs

def limpiar_y_filtrar(df):
    if df is None or df.empty:
        print("El DataFrame original llegó vacío.")
        return pd.DataFrame()
    
    print(f"Empleos encontrados en bruto: {len(df)}")
    
    keywords = ["gerente", "ceo", "cfo", "administracion", "finanzas"]
    df['title_lower'] = df['title'].str.lower()
    
    condicion_puesto = df['title_lower'].apply(
        lambda x: any(kw in str(x) for kw in keywords) if pd.notnull(x) else False
    )
    
    df['location_lower'] = df['location'].str.lower()
    comunas_santiago = ['santiago', 'chile', 'metropolitana', 'condes', 'providencia']
    condicion_ciudad = df['location_lower'].apply(
        lambda x: any(com in str(x) for com in comunas_santiago) if pd.notnull(x) else False
    )
    
    df_filtrado = df[condicion_puesto & condicion_ciudad].copy()
    print(f"Empleos finales que pasaron el filtro: {len(df_filtrado)}")
    return df_filtrado.drop(columns=['title_lower', 'location_lower'], errors='ignore')

def buscar_linkedin():
    try:
        jobs = scrape_jobs(
            site_name=["linkedin"],
            search_term='"Gerente General" OR "CEO" OR "CFO" OR "Gerente de Finanzas"',
            location="Santiago, Chile",
            results_wanted=30,
            hours_old=24,  # Filtro estándar de las últimas 24 horas
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
    
    if not sender_email or not sender_password or not receiver_email:
        print("CRÍTICO: Faltan variables de entorno en los Secrets de GitHub.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Alerta Diaria de Vacantes Ejecutivas - Santiago"
    msg["From"] = sender_email
    msg["To"] = receiver_email

    if df.empty:
        html = """
        <html>
        <body>
            <h2>Alerta Ejecutiva Diaria</h2>
            <p>El sistema se ejecutó correctamente, pero no se registraron nuevas vacantes en LinkedIn bajo tus criterios en las últimas 24 horas en Santiago.</p>
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
                tr:hover { background-color: #f5f5f5; }
                a { color: #2B6CB0; text-decoration: none; font-weight: bold; }
            </style>
        </head>
        <body>
            <h2>Vacantes Ejecutivas del Día - Santiago</h2>
            <table>
                <tr>
                    <th>Puesto</th>
                    <th>Empresa</th>
                    <th>Ubicación</th>
                    <th>Enlace</th>
                </tr>
        """
        for _, row in df.iterrows():
            html += f"""
                <tr>
                    <td>{row['title']}</td>
                    <td>{row['company']}</td>
                    <td>{row.get('location', 'Santiago, Chile')}</td>
                    <td><a href="{row['job_url']}" target="_blank">Ver Postulación</a></td>
                </tr>
            """
        html += "</table></body></html>"

    msg.attach(MIMEText(html, "html"))

    try:
        print("Estableciendo conexión SSL directa por puerto 465...")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            print("Autenticando con Google Mail...")
            server.login(sender_email, sender_password)
            print("Enviando correo...")
            server.sendmail(sender_email, receiver_email, msg.as_string())
        print("¡Correo entregado con éxito a tu bandeja de entrada!")
    except Exception as e:
        print(f"Error crítico en el canal de envío SMTP: {e}")

if __name__ == "__main__":
    print("Iniciando extracción de vacantes...")
    df_linkedin = buscar_linkedin()
    df_final = limpiar_y_filtrar(df_linkedin)
    enviar_correo(df_final)
