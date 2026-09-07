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
    
    # 1. LISTA BLANCA DE RANGOS DE ALTA DIRECCIÓN (Obligatorio)
    rangos_ejecutivos = ["gerente", "ceo", "cfo", "subgerente", "director", "chief"]
    condicion_rango = df['title_lower'].apply(
        lambda x: any(rango in str(x) for rango in rangos_ejecutivos) if pd.notnull(x) else False
    )
    
    # 2. FILTRADO POR COINCIDENCIA DE NICHO ESTRICTO (CORRECCIÓN CRÍTICA)
    # Evaluamos condiciones por duplas exactas para que el área comercial u operacional no contamine el reporte
    es_general = df['title_lower'].str.contains("general", na=False)
    es_financiero = df['title_lower'].str.contains("finan", na=False) | df['title_lower'].str.contains("cfo", na=False)
    es_soporte_clave = df['title_lower'].str.contains("legal", na=False) | df['title_lower'].str.contains("ti", na=False)
    
    # El puesto debe pertenecer estrictamente a una de tus tres áreas de interés ejecutivo
    condicion_especialidad_estricta = es_general | es_financiero | es_soporte_clave
    
    # 3. LISTA NEGRA: Exclusión de cargos operativos y áreas no solicitadas (Veto a Comercial y Operaciones puros)
    lista_negra = ["jefe", "analista", "comercial", "operaciones", "ventas", "marketing", "produccion", "excellence"]
    
    # SALVOCONDUCTO EXTRA: Si el título dice "Gerente General" pero menciona comercial, lo salvamos; si es "Gerente Comercial" a secas, se va.
    condicion_excluir_automatica = df['title_lower'].apply(
        lambda x: any(neg in str(x) for neg in lista_negra) if pd.notnull(x) else False
    )
    condicion_salvoconducto_general = df['title_lower'].str.contains("general", na=False)
    
    condicion_exclusion_final = condicion_excluir_automatica & ~condicion_salvoconducto_general
    
    # 4. PROTECCIÓN ADMINISTRADOR
    condicion_es_administrador = df['title_lower'].str.contains("administrador", na=False)
    condicion_es_gerente_admin = df['title_lower'].str.contains("gerente", na=False) & df['title_lower'].str.contains("administracion", na=False)
    condicion_exclusion_admin = condicion_es_administrador & ~condicion_es_gerente_admin
    
    # Consolidación lógica final de alta exigencia directiva
    df_filtrado = df[condicion_rango & condicion_especialidad_estricta & ~condicion_exclusion_final & ~condicion_exclusion_admin].copy()
    df_filtrado = df_filtrado.drop_duplicates(subset=['title', 'company'], keep='first')
    
    print(f"Empleos finales que pasaron el filtro ejecutivo estricto: {len(df_filtrado)}")
    return df_filtrado.drop(columns=['title_lower'], errors='ignore')

def buscar_linkedin():
    try:
        print("Consultando LinkedIn (Filtro Ejecutivo)...")
        query_lk = '"Gerente General" OR "CEO" OR "CFO" OR "Gerente de Finanzas" OR "Gerente de Administracion" OR "Gerente Administracion"'
        jobs = scrape_jobs(
            site_name=["linkedin"],
            search_term=query_lk,
            location="Santiago, Chile",
            results_wanted=200,  
            hours_old=168,       
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
            hours_old=168,       
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
            hours_old=168,       
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
            <p>El sistema realizó el barrido masivo, pero no se publicaron nuevas vacantes puras de Gerencia General, CFO o Finanzas en el rango de tiempo seleccionado para Santiago.</p>
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
            <p>Reporte unificado depurado de áreas comerciales u operativas:</p>
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
    print("Iniciando extracción de vacantes unificada de alta pureza...")
    
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
