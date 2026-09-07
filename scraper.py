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
    return "".join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')

def limpiar_y_filtrar(df):
    if df is None or df.empty:
        print("El DataFrame de búsqueda llegó vacío.")
        return pd.DataFrame()
    
    # Palabras clave solicitadas para cargos ejecutivos
    keywords = ["gerente", "ceo", "cfo", "administracion", "finanzas", "general"]
    
    # Filtrado por puesto (limpiando tildes y pasando a minúsculas)
    df['title_clean'] = df['title'].apply(remover_tildes).str.lower()
    condicion_puesto = df['title_clean'].apply(
        lambda x: any(kw in str(x) for kw in keywords) if pd.notnull(x) else False
    )
    
    # Filtrado por ubicación (flexible para comunas de Santiago y RM)
    df['location_clean'] = df['location'].apply(remover_tildes).str.lower()
    comunas_santiago = ['santiago', 'chile', 'metropolitana', 'condes', 'providencia', 'vitacura', 'lo barnechea']
    condicion_ciudad = df['location_clean'].apply(
        lambda x: any(com in str(x) for com in comunas_santiago) if pd.notnull(x) else False
    )
    
    df_filtrado = df[condicion_puesto & condicion_ciudad].copy()
    
    # Eliminar duplicados si una vacante aparece en más de un portal simultáneamente
    df_filtrado = df_filtrado.drop_duplicates(subset=['title', 'company'], keep='first')
    
    print(f"Vacantes definitivas que pasaron el filtro: {len(df_filtrado)}")
    return df_filtrado.drop(columns=['title_clean', 'location_clean'], errors='ignore')

def buscar_linkedin():
    try:
        print("Consultando LinkedIn (Filtro 24h estricto)...")
        jobs = scrape_jobs(
            site_name=["linkedin"],
            search_term='"Gerente General" OR "CEO" OR "CFO" OR "Gerente de Finanzas" OR "Gerente Administracion"',
            location="Santiago, Chile",
            results_wanted=40,
            hours_old=24,
            country_indeed="chile"
        )
        if jobs is not None and not jobs.empty:
            return jobs[['title', 'company', 'job_url', 'location', 'site']].copy()
        return pd.DataFrame()
    except Exception as e:
        print(f"Error en extracción de LinkedIn: {e}")
        return pd.DataFrame()

def buscar_portales_locales():
    try:
        print("Consultando Indeed (Agregador de Laborum, Chiletrabajos y Trabajando)...")
        # Usamos 48h para Indeed para evitar que su formato ambiguo de fechas deje en cero la búsqueda
        jobs = scrape_jobs(
            site_name=["indeed"],
            search_term='"Gerente General" OR "CEO" OR "CFO" OR "Gerente de Finanzas" OR "Gerente Administracion"',
            location="Santiago, Chile",
            results_wanted=50,
            hours_old=48, 
            country_indeed="chile"
        )
        if jobs is not None and not jobs.empty:
            return jobs[['title', 'company', 'job_url', 'location', 'site']].copy()
        return pd.DataFrame()
    except Exception as e:
        print(f"Error en extracción de portales locales: {e}")
        return pd.DataFrame()

def enviar_correo(df):
    sender_email = os.environ.get("SMTP_EMAIL")
    sender_password = os.environ.get("SMTP_PASSWORD")
    receiver_email = os.environ.get("RECEIVER_EMAIL")
    
    if not sender_email or not sender_password or not receiver_email:
        print("CRÍTICO: Faltan variables de entorno en GitHub Secrets.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Alerta Diaria Consolidada: Vacantes Ejecutivas Santiago"
    msg["From"] = sender_email
    msg["To"] = receiver_email

    if df.empty:
        html = """
        <html>
        <body>
            <h2 style="color: #1A365D;">Reporte Ejecutivo Diario</h2>
            <p>El sistema se ejecutó correctamente, pero no se registraron nuevas vacantes en los portales monitoreados en el último ciclo para Santiago.</p>
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
                th, td { text-align: left; padding: 12px; border-bottom: 1px solid #ddd; font-size: 13px; }
                th { background-color: #1A365D; color: white; font-size: 14px; }
                tr:hover { background-color: #f5f5f5; }
                a { color: #2B6CB0; text-decoration: none; font-weight: bold; }
                .portal-badge { padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; text-transform: uppercase; }
                .linkedin-badge { background-color: #EBF8FF; color: #2B6CB0; }
                .indeed-badge { background-color: #E2E8F0; color: #2D3748; }
            </style>
        </head>
        <body>
            <h2 style="color: #1A365D;">Vacantes Ejecutivas Consolidadas - Santiago</h2>
            <p>Reporte unificado multiportal (LinkedIn, Trabajando, Laborum, Chiletrabajos):</p>
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
            
            if "linkedin" in origin:
                badge_html = '<span class="portal-badge linkedin-badge">linkedin</span>'
            else:
                badge_html = '<span class="portal-badge indeed-badge">portal local</span>'

            html += f"""
                <tr>
                    <td><b>{row['title']}</b></td>
                    <td>{row['company']}</td>
                    <td>{row.get('location', 'Santiago, RM')}</td>
                    <td>{badge_html}</td>
                    <td><a href="{row['job_url']}" target="_blank">Ver Postulación</a></td>
                </tr>
            """
        html += "</table></body></html>"

    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("://gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, receiver_email, msg.as_string().encode('utf-8'))
        print("¡Correo consolidado enviado con éxito!")
    except Exception as e:
        print(f"Error crítico en el canal de envío SMTP: {e}")

if __name__ == "__main__":
    print("Iniciando extracción unificada independiente...")
    
    # Forzamos las búsquedas por separado para que Indeed no rompa las fechas de LinkedIn
    df_lk = buscar_linkedin()
    df_locales = buscar_portales_locales()
    
    # Consolidamos de manera segura
    df_total = pd.concat([df_lk, df_locales], ignore_index=True)
    
    df_final = limpiar_y_filtrar(df_total)
    enviar_correo(df_final)
