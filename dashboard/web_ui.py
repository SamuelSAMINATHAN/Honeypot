import streamlit as st

st.set_page_config(layout="wide", page_title="Honeypot Dashboard")

from streamlit_autorefresh import st_autorefresh
import pandas as pd
import json
import os
from collections import Counter
import glob
from datetime import datetime

# Rafraîchit automatiquement toutes les 10 secondes
st_autorefresh(interval=10000, key="refresh")

# Charger la configuration
CONFIG_PATH = 'config/honeypot_config.json'
LOG_DIRECTORY = 'logs'
LOG_FILE_PREFIX = 'honeypot'

try:
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)
    LOG_DIRECTORY = config.get('log_directory', LOG_DIRECTORY)
    LOG_FILE_PREFIX = config.get('log_file_prefix', LOG_FILE_PREFIX)
except FileNotFoundError:
    st.warning(f"Fichier de configuration {CONFIG_PATH} non trouvé. Utilisation des valeurs par défaut.")
except json.JSONDecodeError:
    st.error(f"Erreur dans {CONFIG_PATH}. Vérifiez la syntaxe JSON.")

LOG_FILE_PATTERN = os.path.join(LOG_DIRECTORY, f"{LOG_FILE_PREFIX}.json*")

@st.cache_data(ttl=60)
def load_log_data():
    all_log_entries = []
    log_files = sorted(glob.glob(LOG_FILE_PATTERN), reverse=True)

    if not log_files:
        return pd.DataFrame()

    for log_file in log_files:
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        if 'extra_data' in entry:
                            entry.update(entry['extra_data'])
                            del entry['extra_data']
                        all_log_entries.append(entry)
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            st.error(f"Erreur de lecture dans {log_file}: {e}")

    if not all_log_entries:
        return pd.DataFrame()

    df = pd.DataFrame(all_log_entries)
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df

# --- Interface Streamlit ---
st.title("📊 Honeypot Activity Dashboard")
st.markdown("Visualisation des événements enregistrés par les honeypots.")

df = load_log_data()

if df.empty:
    st.info("Aucune donnée de log à afficher pour le moment.")
else:
    st.sidebar.header("Filtres")
    modules = df['module'].unique() if 'module' in df.columns else []
    selected_module = st.sidebar.multiselect("Filtrer par Module", modules, default=modules)

    levels = df['level'].unique() if 'level' in df.columns else []
    selected_level = st.sidebar.multiselect("Filtrer par Niveau", levels, default=levels)

    if 'ip' in df.columns:
        ips = df['ip'].dropna().unique()
        selected_ip = st.sidebar.selectbox("Filtrer par IP (Optionnel)", ["Toutes"] + list(ips))
    else:
        selected_ip = "Toutes"
        st.sidebar.info("Aucune colonne 'ip' trouvée dans les logs.")

    filtered_df = df.copy()
    if 'module' in df.columns:
        filtered_df = filtered_df[filtered_df['module'].isin(selected_module)]
    if 'level' in df.columns:
        filtered_df = filtered_df[filtered_df['level'].isin(selected_level)]
    if selected_ip != "Toutes" and 'ip' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['ip'] == selected_ip]

    st.header("Résumé de l'activité")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Événements Loggués", len(filtered_df))
    col2.metric("Nombre d'IP uniques", filtered_df['ip'].nunique() if 'ip' in filtered_df.columns else "N/A")
    if 'timestamp' in filtered_df.columns:
        latest_event_time = filtered_df['timestamp'].max()
        col3.metric("Dernier Événement", latest_event_time.strftime("%Y-%m-%d %H:%M:%S") if pd.notnull(latest_event_time) else "N/A")
    else:
        col3.metric("Dernier Événement", "N/A")

    st.header("Top Activités")
    col1_top, col2_top, col3_top = st.columns(3)

    with col1_top:
        st.subheader("Top 10 IPs Attaquantes")
        if 'ip' in filtered_df.columns:
            st.dataframe(filtered_df['ip'].value_counts().head(10))
        else:
            st.info("Pas de données IP disponibles.")

    with col2_top:
        st.subheader("Top 10 Usernames Tentés")
        if 'user' in filtered_df.columns:
            st.dataframe(filtered_df['user'].dropna().value_counts().head(10))
        else:
            st.info("Pas de données 'user' disponibles.")

    with col3_top:
        st.subheader("Top 10 Passwords Tentés")
        if 'pass' in filtered_df.columns:
            st.dataframe(filtered_df['pass'].dropna().value_counts().head(10))
        else:
            st.info("Pas de données 'pass' disponibles.")

    st.header("Événements Récents")
    display_columns = ['timestamp', 'level', 'module', 'ip', 'message']
    for col in ['user', 'pass', 'path', 'method', 'command', 'query', 'user_agent']:
        if col in filtered_df.columns and col not in display_columns:
            display_columns.append(col)

    visible_columns = [c for c in display_columns if c in filtered_df.columns]
    st.dataframe(filtered_df[visible_columns].sort_values(by='timestamp', ascending=False).head(100))

    st.header("Exploration des Données Brutes")
    if st.checkbox("Afficher les données brutes filtrées"):
        st.dataframe(filtered_df)
