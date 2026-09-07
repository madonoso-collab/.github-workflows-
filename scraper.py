import os
import smtplib
import time
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
        print("El DataFrame consolidado llegó vacío.")
        return pd.DataFrame()
    
    # Procesamiento unificado de texto en minúsculas y sin acentos
    df['title_lower'] = df['title'].apply(remover_tildes).str.lower()
    
    # 1. TÉRMINOS EJECUTIVOS EXCLUSIVOS SOLICITADOS (Tu foco de alta pureza)
    conceptos_clave = [
        "gerente general", "ceo", "cfo", "gerente finanzas", 
        "gerente de finanzas", "administracion y finanzas", "administracion & finanzas",
        "gerente administracion", "gerente de administracion", "director de finanzas"
    ]
    
    condicion_perfil_estricto = df['title_lower'].apply(
        lambda x: any(concepto in str(x) for concepto in conceptos_clave) if pd.notnull(x) else False
    )
    
    # 2. LISTA NEGRA AGRESIVA DE ÁREAS EXCLUIDAS (Cero ruido operativo)
    lista_negra_areas = [
        "jefe", "analista", "comercial", "ventas", "marketing", "produccion", 
        "personas", "cultura", "rrhh", "recursos humanos", "talent", "office", 
        "operaciones", "operations", "tiendas", "proyectos", "project"
    ]
    
    condicion_exclusion_areas = df['title_lower'].apply(
        lambda x: any(neg in str(x) for neg in lista_negra_areas) if pd.notnull(x) else False
    )
    
    # Filtro geográfico flexible para la Región Metropolitana
    df['location_lower'] = df['location'].apply(remover_tildes).str.lower()
    comunas_santiago = ['santiago', 'chile', 'metropolitana', 'condes', 'providencia', 'vitacura', 'lo barnechea']
    condicion_ciudad = df['location_lower'].apply(
        lambda x: any(com in str(x) for com in comunas_santiago) if pd.notnull(x) else False
    )
    
    # Consolidación lógica final
    df_filtrado = df[condicion_perfil_estricto & condicion_ciudad & ~condicion_exclusion_areas].copy()
    df_filtrado = df_filtrado.drop_duplicates(subset=['title', 'company'], keep='first')
    
    print(f"Empleos finales que pasaron el filtro ejecutivo puro (24h): {len(df_filtrado)}")
    return df_filtrado.drop(columns=['title_lower', 'location_lower'], errors='ignore')

def buscar_linkedin():
    try:
        print("Consultando LinkedIn (Filtro 24h)...")
        query_lk = '"Gerente General" OR "CEO" OR "CFO" OR "Gerente de Finanzas" OR "Gerente Administracion"'
        jobs = scrape_jobs(
            site_name=["linkedin"],
            search_term=query_lk,
            location="Santiago, Chile",
            results_wanted=200,  
            hours_old=24,       # AJUSTADO A 24 HORAS
            country_indeed="chile"
        )
        if jobs is not None and not jobs.empty:
            return jobs[['title', 'company', 'job_url', 'location']].copy()
    except Exception as e:
        print(f"Aviso en LinkedIn: {e}")
    return pd.DataFrame()

def buscar_indeed_especifico():
    try:
        print("Consultando Indeed Objetivo (Administración y Finanzas / CFO)...")
        jobs = scrape_jobs(
            site_name=["indeed"],
            search_term="Gerente Administracion Finanzas Santiago",
            location="Santiago, Chile",
            results_wanted=200,  
            hours_old=24,       # AJUSTADO A 24 HORAS
            country_indeed="chile"
        )
        if jobs is not None and not jobs.empty:
            return jobs[['title', 'company', 'job_url', 'location']].copy()
    except Exception as e:
        print(f"Aviso en Indeed Objetivo: {e}")
    return pd.DataFrame()

def buscar_portales_locales_generico():
    try:
        print("Consultando Agregador General (Búsqueda de respaldo General / Finanzas)...")
        jobs = scrape_jobs(
            site_name=["indeed"],
            search_term='"Gerente General" OR "Gerente Finanzas" Santiago',
            location="Santiago, Chile",
            results_wanted=200,  
            hours_old=24,       # AJUSTADO A 24 HORAS
            country_indeed="chile"
        )
        if jobs is not None and not jobs.empty:
            return jobs[['title', 'company', 'job_url', 'location']].copy()
    except Exception as e:
        print(f"Aviso en Agregador General: {e}")
    return pd.DataFrame()

def enviar_correo(df):
    sender_email = os.environ.get("SMTP_EMAIL")
    sender_password = os.environ.get("SMTP_PASSWORD")
    receiver_email = os.environ.get("RECEIVER_EMAIL")
    
    if not sender_email or not sender_password or not receiver_email:
        print("CRÍTICO: Faltan variables de entorno en los Secrets de GitHub.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Alerta Consolidada: Alta Gerencia y Finanzas Santiago"
    msg["From"] = sender_email
    msg["To"] = receiver_email

    if df.empty:
        html = """
        <html>
        <body>
            <h2>Alerta Ejecutiva Filtrada</h2>
            <p>El sistema realizó el barrido masivo, pero no se registraron nuevas vacantes puras de Gerencia General, CFO o Finanzas en las últimas 24 horas para Santiago.</p>
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
            <h2>Vacantes Exclusivas de Alta Dirección y Finanzas - Santiago</h2>
            <p>Reporte unificado de alta pureza ejecutivo de las últimas 24 horas (LinkedIn, Trabajando, Laborum, Chiletrabajos):</p>
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

    max_intentos = 3
    for intento in range(1, max_intentos + 1):
        try:
            print(f"Estableciendo conexión SSL directa por IP de Google 74.125.142.108:465 (Intento {intento}/{max_intentos})...")
            with smtplib.SMTP_SSL("74.125.142.108", 465, timeout=20) as server:
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, receiver_email, msg.as_string().encode('utf-8'))
                server.quit()
                print("¡Correo entregado con éxito a tu bandeja de entrada!")
                break
        except Exception as e:
            print(f"Intento {intento} falló debido a problemas de red: {e}")
            if intento < max_intentos:
                time.sleep(5)
            else:
                print("Error crítico definitivo en el canal de envío SMTP tras 3 intentos.")

if __name__ == "__main__":
    print("Iniciando extracción de vacantes unificada diaria...")
    
    df_lk = buscar_linkedin()
    df_ind_obj = buscar_indeed_especifico()
    df_ind_gen = buscar_portales_locales_generico()
    
    lista_dfs = []
    if not df_lk.empty:
        lista_dfs.append(df_lk)
    if not df_ind_obj.empty:
        lista_dfs.append(df_ind_obj)
    if not df_ind_gen.empty:
        lista_dfs.append(df_ind_gen)
        
    if lista_dfs:
        df_consolidado = pd.concat(lista_dfs, ignore_index=True)
        df_final = limpiar_y_filtrar(df_consolidado)
        enviar_correo(df_final)
    else:
        print("Todas las búsquedas finalizaron vacías.")
        enviar_correo(pd.DataFrame())
