import logging
import logging.handlers
import json
import os
from datetime import datetime

# Charger la configuration pour déterminer où logger
try:
    with open('config/honeypot_config.json', 'r') as f:
        config = json.load(f)
    LOG_DIRECTORY = config.get('log_directory', 'logs')
    LOG_FILE_PREFIX = config.get('log_file_prefix', 'honeypot')
except FileNotFoundError:
    print("Fichier de configuration config/honeypot_config.json non trouvé. Utilisation des valeurs par défaut.")
    LOG_DIRECTORY = 'logs'
    LOG_FILE_PREFIX = 'honeypot'
except json.JSONDecodeError:
    print("Erreur lors de la lecture de config/honeypot_config.json. Utilisation des valeurs par défaut.")
    LOG_DIRECTORY = 'logs'
    LOG_FILE_PREFIX = 'honeypot'

# Créer le répertoire de logs s'il n'existe pas
os.makedirs(LOG_DIRECTORY, exist_ok=True)

# Configuration du logger principal
log_file_path = os.path.join(LOG_DIRECTORY, f"{LOG_FILE_PREFIX}.json")

# Utiliser TimedRotatingFileHandler pour la rotation quotidienne
handler = logging.handlers.TimedRotatingFileHandler(
    log_file_path,
    when="midnight",
    interval=1,
    backupCount=30, # Garde les logs des 30 derniers jours
    encoding='utf-8'
)

# Formatter pour écrire en JSON
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + 'Z',
            "level": record.levelname,
            "module": record.name, # Nom du logger (ex: 'ssh', 'http')
            "message": record.getMessage(),
            **getattr(record, 'extra_data', {}) # Ajoute les données supplémentaires
        }
        return json.dumps(log_record, ensure_ascii=False)

handler.setFormatter(JsonFormatter())

def get_logger(name):
    """Obtient une instance de logger configurée."""
    logger = logging.getLogger(name)
    # Éviter d'ajouter plusieurs fois le même handler si get_logger est appelé plusieurs fois
    if not logger.handlers:
        logger.addHandler(handler)
        logger.setLevel(logging.INFO) # Niveau de log par défaut
        # Empêcher la propagation vers le logger root pour éviter les doublons si root est configuré
        logger.propagate = False
    return logger

# Exemple d'utilisation (sera retiré plus tard)
# if __name__ == "__main__":
#     ssh_logger = get_logger('ssh')
#     http_logger = get_logger('http')
#
#     ssh_logger.info("Tentative de connexion SSH", extra={'extra_data': {'ip': '192.168.1.100', 'user': 'root', 'pass': 'password123'}})
#     http_logger.warning("Requête suspecte", extra={'extra_data': {'ip': '10.0.0.5', 'path': '/admin', 'user_agent': 'EvilBot/1.0'}})
#     http_logger.info("Requête normale", extra={'extra_data': {'ip': '10.0.0.6', 'path': '/', 'user_agent': 'Chrome/90'}}) 