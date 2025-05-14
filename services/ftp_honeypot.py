from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer
from logutils.logger import get_logger
import os

logger = get_logger('ftp')

# Créer un répertoire "piège" si nécessaire, mais l'accès sera refusé
FAKE_FTP_ROOT = 'ftp_trap_dir'
os.makedirs(FAKE_FTP_ROOT, exist_ok=True)

class HoneypotFTPHandler(FTPHandler):
    # Bannière personnalisée
    banner = "220 ProFTPD 1.3.5 Server (Debian) [::ffff:127.0.0.1]"

    def on_connect(self):
        logger.info(f"Connexion FTP de {self.remote_ip}")

    def on_disconnect(self):
        logger.info(f"Déconnexion FTP de {self.remote_ip}")

    def on_login(self, username):
        password = self.password # Récupérer le mot de passe tenté
        logger.warning(
            f"Tentative de login FTP",
            extra={'extra_data': {'ip': self.remote_ip, 'user': username, 'pass': password}}
        )
        # Techniquement, l'authorizer gère le login, mais on logge ici
        # L'authorizer acceptera tout, mais ne donnera aucun droit.
        pass # Laisser l'authorizer DummyAuthorizer accepter

    def on_login_failed(self, username, password):
        logger.error(
            f"Échec de login FTP (ne devrait pas arriver avec DummyAuthorizer)",
            extra={'extra_data': {'ip': self.remote_ip, 'user': username, 'pass': password}}
        )

    def on_file_sent(self, file):
        logger.info(f"Fichier envoyé (ne devrait pas arriver): {file}", extra={'extra_data': {'ip': self.remote_ip}})

    def on_file_received(self, file):
        logger.info(f"Fichier reçu (ne devrait pas arriver): {file}", extra={'extra_data': {'ip': self.remote_ip}})

    def on_incomplete_file_sent(self, file):
        logger.warning(f"Envoi de fichier incomplet (ne devrait pas arriver): {file}", extra={'extra_data': {'ip': self.remote_ip}})

    def on_incomplete_file_received(self, file):
        logger.warning(f"Réception de fichier incomplète (ne devrait pas arriver): {file}", extra={'extra_data': {'ip': self.remote_ip}})

    # Surcharger les commandes pour les logger
    def ftp_USER(self, line):
        logger.info(f"Commande FTP reçue: USER {line}", extra={'extra_data': {'ip': self.remote_ip, 'command': 'USER', 'arg': line}})
        super().ftp_USER(line)

    def ftp_PASS(self, line):
        # Le mot de passe réel n'est pas dans 'line' ici, il est stocké dans self.password
        logger.info(f"Commande FTP reçue: PASS *****", extra={'extra_data': {'ip': self.remote_ip, 'command': 'PASS'}})
        super().ftp_PASS(line)

    def ftp_LIST(self, line):
        logger.info(f"Commande FTP reçue: LIST {line}", extra={'extra_data': {'ip': self.remote_ip, 'command': 'LIST', 'arg': line}})
        # Répondre avec un contenu vide ou un message d'erreur
        self.respond("550 Requested action not taken. File unavailable.")
        # Alternativement, pour simuler un dossier vide:
        # self.respond("150 Here comes the directory listing.")
        # self.respond("226 Directory send OK.")

    def ftp_NLST(self, line):
        logger.info(f"Commande FTP reçue: NLST {line}", extra={'extra_data': {'ip': self.remote_ip, 'command': 'NLST', 'arg': line}})
        self.respond("550 Requested action not taken. File unavailable.")

    def ftp_RETR(self, file):
        logger.warning(f"Commande FTP reçue: RETR {file}", extra={'extra_data': {'ip': self.remote_ip, 'command': 'RETR', 'arg': file}})
        self.respond("550 Requested action not taken. File unavailable.")

    def ftp_STOR(self, file):
        logger.warning(f"Commande FTP reçue: STOR {file}", extra={'extra_data': {'ip': self.remote_ip, 'command': 'STOR', 'arg': file}})
        self.respond("550 Requested action not taken. File unavailable.")

    # Intercepter d'autres commandes potentiellement intéressantes
    def ftp_CWD(self, line):
        logger.info(f"Commande FTP reçue: CWD {line}", extra={'extra_data': {'ip': self.remote_ip, 'command': 'CWD', 'arg': line}})
        # Toujours répondre comme si ça fonctionnait, mais rester à la racine (virtuelle)
        self.respond("250 Directory successfully changed.")

    def ftp_PWD(self, line):
        logger.info(f"Commande FTP reçue: PWD {line}", extra={'extra_data': {'ip': self.remote_ip, 'command': 'PWD', 'arg': line}})
        # Toujours répondre avec la racine
        self.respond('257 "/" is the current directory.')

    def ftp_TYPE(self, line):
        logger.info(f"Commande FTP reçue: TYPE {line}", extra={'extra_data': {'ip': self.remote_ip, 'command': 'TYPE', 'arg': line}})
        super().ftp_TYPE(line)

    def ftp_QUIT(self, line):
        logger.info(f"Commande FTP reçue: QUIT {line}", extra={'extra_data': {'ip': self.remote_ip, 'command': 'QUIT'}})
        super().ftp_QUIT(line)

def start_ftp_honeypot(host='0.0.0.0', port=2121, ftp_root='ftp_trap_dir'):
    """Démarre le serveur honeypot FTP avec un dossier racine piège."""
    try:
        os.makedirs(ftp_root, exist_ok=True)  # ✅ Crée le répertoire si absent

        authorizer = DummyAuthorizer()

        # Accepte tous les logins mais donne accès uniquement à un dossier piège
        authorizer.add_user("user", "password", homedir=ftp_root, perm="elr")
        authorizer.add_anonymous(homedir=ftp_root, perm="elr")  # 'elr' = list-only

        handler = HoneypotFTPHandler
        handler.authorizer = authorizer
        handler.passive_ports = range(60000, 60010)

        server = FTPServer((host, port), handler)
        print(f"[*] Honeypot FTP écoute sur {host}:{port}")
        logger.info(f"Honeypot FTP démarré sur {host}:{port}")
        server.serve_forever()

    except Exception as e:
        logger.critical(f"Erreur critique du Honeypot FTP : {e}", exc_info=True)
        print(f"[!] Erreur critique du Honeypot FTP : {e}")
    finally:
        if 'server' in locals():
            server.close_all()
        print("[*] Honeypot FTP arrêté.")
        logger.info("Honeypot FTP arrêté.")


# Pour tester ce module seul (sera lancé par run.py plus tard)
# if __name__ == "__main__":
#     start_ftp_honeypot() 