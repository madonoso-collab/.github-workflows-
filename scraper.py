import os
import smtplib
import unicodedata
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pandas as pd
from jobspy import scrape_jobs

def remover_tildes(texto):
    if not isinstance(texto, str):
        return ""
    # Normaliza y elimina acentos de forma nativa tanto para mayúsculas como minúsculas
    return "".join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')

def limpiar_y_filtrar(df):
    if df is None or df.empty:
        print("El DataFrame consolidado llegó vacío.")
        return pd.DataFrame()
    
    # Espectro ampliado de palabras clave ejecutivas de control
    keywords = ["gerente", "ceo", "cfo", "administracion", "finanzas", "director", "subgerente", "general", "chief"]
    
    # CORRECCIÓN CRÍTICA: Primero removemos tildes y luego pasamos a minúsculas
    df['title_lower'] = df['title'].apply(remover_tildes).str.lower()
    
    condicion_puesto = df['title_lower'].apply(
        lambda x: any(kw in str(x) for kw in keywords) if pd.notnull(x) else False
    )
    
    df['location_lower'] = df['location'].apply(remover_tildes).str.lower()
    comunas_santiago = ['santiago', 'chile', 'metropolitana', 'condes', 'providencia', 'vitacura', 'lo barnechea']
    condicion_ciudad = df['location_lower'].apply(
        lambda x: any(com in str(x) for com in comunas_santiago) if pd.notnull(x) else False
    )
    
    df_filtrado = df[condicion_puesto & condicion_ciudad].copy()
    
    # Eliminamos duplicados basados en título y empresa para mantener el reporte limpio
    df_filtrado = df_filtrado.drop_duplicates(subset=['title', 'company'], keep='first')
    
    print(f"Empleos finales que pasaron el filtro: {len(df_filtrado)}")
    return df_filtrado.drop(columns=['title_lower', 'location_lower'], errors='ignore')

def buscar_linkedin():
    try:
        print("Consultando LinkedIn (Filtro 24h)...")
        # Aseguramos todas las variantes clave en el buscador raíz de LinkedIn
        jobs = scrape_jobs(
            site_name=["linkedin"],
            search_term='"Gerente General" OR "CEO" OR "CFO" OR "Gerente de Finanzas" OR "Gerente de Administracion"',
            location="Santiago, Chile",
            results_wanted=50, # Aumentamos levemente el espectro de captura
            hours_old=24,
            country_indeed="chile"
        )
        if jobs is not None and not jobs.empty:
            return jobs[['title', 'company', 'job_url', 'location']].copy()
    except Exception as e:
        print(f"Aviso: LinkedIn no arrojó resultados en este ciclo: {e}")
    return pd.DataFrame()

def buscar_portales_locales():
    try:
        print("Consultando Indeed (Agregador de Laborum, Chiletrabajos, Trabajando)...")
        jobs = scrape_jobs(
            site_name=["indeed"],
            search_term='Gerente Santiago',
            location="Santiago, Chile",
            results_wanted=50,
            hours_old=48, 
            country_indeed="chile"
        )
        if jobs is not None and not jobs.empty:
            return jobs[['title', 'company', 'job_url', 'location']].copy()
    except Exception as e:
        print(f"Aviso: El motor regional Indeed no respondió: {e}")
    return pd.DataFrame()

def enviar_correo(df):
    sender_email = os.environ.get("SMTP_EMAIL")
    sender_password = os.environ.get("SMTP_PASSWORD")
    receiver_email = os.environ.get("RECEIVER_EMAIL")
    
    if not sender_email or not sender_password or not receiver_email:
        print("CRÍTICO: Faltan variables de entorno en los Secrets de GitHub.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Alerta Diaria Consolidada: Vacantes Ejecutivas Santiago"
    msg["From"] = sender_email
    msg["To"] = receiver_email

    if df.empty:
        html = """
        <html>
        <body>
            <h2>Alerta Ejecutiva Diaria</h2>
            <p>El sistema se ejecutó correctamente, pero no se registraron nuevas vacantes bajo tus criterios en las últimas 24 horas en Santiago.</p>
        </body>
        </html>
        """
    else:
        html = """
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                table { border-collapse: collapse; width: 100%; font-family: Arial, sans-serif; }
                th, td { text-align: left; padding: 12px; border-bottom: 1px solid #ddd; }
                th { background-color: #1A365D; color: white; }
                tr:hover { background-color: #f5f5f5; }
                a { color: #2B6CB0; text-decoration: none; font-weight: bold; }
            </style>
        </head>
        <body>
            <h2>Vacantes Ejecutivas Consolidadas - Santiago</h2>
            <p>Reporte unificado (LinkedIn, Trabajando, Laborum, Chiletrabajos):</p>
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
                    <td><b>{row['title']}</b></td>
                    <td>{row['company']}</td>
                    <td>{row.get('location', 'Santiago, Chile')}</td>
                    <td><a href="{row['job_url']}" target="_blank">Ver Postulación</a></td>
                </tr>
            """
        html += "</table></body></html>"

    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        print("Estableciendo conexión SSL directa por puerto 465...")
        with smtplib.SMTP_SSL("://gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, receiver_email, msg.as_string().encode('utf-8'))
        print("¡Correo entregado con éxito a tu bandeja de entrada!")
    except Exception as e:
        print(f"Error crítico en el canal de envío SMTP: {e}")

if __name__ == "__main__":
    print("Iniciando extracción de vacantes...")
    
    df_lk = buscar_linkedin()
    df_locales = buscar_portales_locales()
    
    lista_dfs = []
    if not df_lk.empty:
        lista_dfs.append(df_lk)
    if not df_locales.empty:
        lista_dfs.append(df_locales)
        
    if lista_dfs:
        df_consolidado = pd.concat(lista_dfs, ignore_index=True)
        df_final = limpiar_y_filtrar(df_consolidado)
        enviar_correo(df_final)
    else:
        print("Todas las búsquedas finalizaron vacías.")
        enviar_correo(pd.DataFrame())
