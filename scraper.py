import os
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pandas as pd
from jobspy import scrape_jobs

def limpiar_y_filtrar(df):
    if df is None or df.empty:
        return pd.DataFrame()
    
    # Términos específicos solicitados
    keywords = ["gerente", "ceo", "cfo", "administracion", "finanzas", "general"]
    df['title_lower'] = df['title'].str.lower()
    
    condicion_puesto = df['title_lower'].apply(
        lambda x: any(kw in str(x) for kw in keywords) if pd.notnull(x) else False
    )
    
    # Filtro geográfico flexible para la Región Metropolitana
    df['location_lower'] = df['location'].str.lower()
    comunas_santiago = ['santiago', 'chile', 'metropolitana', 'condes', 'providencia', 'vitacura', 'lo barnechea']
    condicion_ciudad = df['location_lower'].apply(
        lambda x: any(com in str(x) for com in comunas_santiago) if pd.notnull(x) else False
    )
    
    df_filtrado = df[condicion_puesto & condicion_ciudad].copy()
    
    # Eliminar duplicados exactos si se cruzan ofertas entre portales
    df_filtrado = df_filtrado.drop_duplicates(subset=['title', 'company'], keep='first')
    
    return df_filtrado.drop(columns=['title_lower', 'location_lower'], errors='ignore')

def buscar_linkedin_y_agregadores():
    try:
        print("Consultando LinkedIn e Indeed (Agregador de Laborum, Chiletrabajos y Trabajando)...")
        jobs = scrape_jobs(
            site_name=["linkedin", "indeed"],
            search_term='"Gerente General" OR "CEO" OR "CFO" OR "Gerente de Finanzas" OR "Gerente Administracion"',
            location="Santiago, Chile",
            results_wanted=80,
            hours_old=24,
            country_indeed="chile"
        )
        return jobs
    except Exception as e:
        print(f"Error en motores principales: {e}")
        return pd.DataFrame()

def buscar_firstjob():
    """Scraper a la API de FirstJob Chile para capturar vacantes corporativas en las últimas 24h"""
    print("Consultando FirstJob Chile...")
    lista_empleos = []
    try:
        # Endpoint público de la API de FirstJob filtrado para Chile
        url = "https://firstjob.me &per_page=50"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            # Estructura típica de respuesta de FirstJob
            jobs_data = data.get('data', []) if isinstance(data, dict) else data
            
            for job in jobs_data:
                title = job.get('title', '')
                company = job.get('company', {}).get('name', 'Empresa Confidencial')
                # Enlace dinámico directo para postular en FirstJob
                slug = job.get('slug', '')
                job_url = f"https://firstjob.me{slug}" if slug else "https://firstjob.me"
                location = job.get('city', 'Santiago, Chile')
                
                lista_empleos.append({
                    'title': title,
                    'company': company,
                    'job_url': job_url,
                    'location': location,
                    'site': 'firstjob'
                })
        return pd.DataFrame(lista_empleos)
    except Exception as e:
        print(f"Error extrayendo de FirstJob: {e}")
        return pd.DataFrame()

def enviar_correo(df):
    sender_email = os.environ.get("SMTP_EMAIL")
    sender_password = os.environ.get("SMTP_PASSWORD")
    receiver_email = os.environ.get("RECEIVER_EMAIL")
    
    if not sender_email or not sender_password or not receiver_email:
        print("CRÍTICO: Faltan variables de entorno en GitHub Secrets.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Alerta Consolidada Multiportal: Vacantes Ejecutivas Santiago"
    msg["From"] = sender_email
    msg["To"] = receiver_email

    if df.empty:
        html = """
        <html>
        <body>
            <h2 style="color: #1A365D;">Reporte Ejecutivo Diario</h2>
            <p>No se registraron nuevas vacantes de Alta Gerencia en LinkedIn, Laborum, Chiletrabajos, Trabajando.com ni FirstJob en las últimas 24 horas para Santiago.</p>
        </body>
        </html>
        """
    else:
        html = """
        <html>
        <head>
            <style>
                table { border-collapse: collapse; width: 100%; font-family: Arial, sans-serif; }
                th, td { text-align: left; padding: 12px; border-bottom: 1px solid #ddd; font-size: 13px; }
                th { background-color: #1A365D; color: white; font-size: 14px; }
                tr:hover { background-color: #f5f5f5; }
                a { color: #2B6CB0; text-decoration: none; font-weight: bold; }
                .portal-badge { background-color: #E2E8F0; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; color: #4A5568; text-transform: uppercase; }
                .firstjob-badge { background-color: #FED7D7; color: #9B2C2C; }
                .linkedin-badge { background-color: #EBF8FF; color: #2B6CB0; }
            </style>
        </head>
        <body>
            <h2 style="color: #1A365D;">Vacantes Ejecutivas Consolidadas - Santiago</h2>
            <p>Reporte unificado de las últimas 24 horas:</p>
            <table>
                <tr>
                    <th>Puesto</th>
                    <th>Empresa</th>
                    <th>Ubicación</th>
                    <th>Origen</th>
                    <th>Acción</th>
                </tr>
        """
        for _, row in df.iterrows():
            origin = str(row.get('site', 'Enlace')).lower()
            badge_class = "portal-badge"
            if "linkedin" in origin:
                badge_class += " linkedin-badge"
            elif "firstjob" in origin:
                badge_class += " firstjob-badge"

            html += f"""
                <tr>
                    <td><b>{row['title']}</b></td>
                    <td>{row['company']}</td>
                    <td>{row.get('location', 'Santiago, RM')}</td>
                    <td><span class="{badge_class}">{origin}</span></td>
                    <td><a href="{row['job_url']}" target="_blank">Postular</a></td>
                </tr>
            """
        html += "</table></body></html>"

    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("://gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, receiver_email, msg.as_string())
        print("¡Correo consolidado multiportal enviado con éxito!")
    except Exception as e:
        print(f"Error crítico en el canal de envío SMTP: {e}")

if __name__ == "__main__":
    print("Iniciando extracción unificada multiportal (Chile)...")
    
    # 1. Ejecutar búsquedas en paralelo
    df_motores = buscar_linkedin_y_agregadores()
    df_firstjob = buscar_firstjob()
    
    # 2. Consolidar ambas fuentes de datos
    df_consolidado = pd.concat([df_motores, df_firstjob], ignore_index=True)
    
    # 3. Filtrar y limpiar resultados
    df_final = limpiar_y_filtrar(df_consolidado)
    
    # 4. Enviar reporte ejecutivo
    enviar_correo(df_final)
