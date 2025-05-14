import paramiko
import socket
import threading
from logutils.logger import get_logger

logger = get_logger('ssh')

# Clé serveur "faible" générée une fois pour la stabilité (à remplacer par une génération si nécessaire)
# ssh-keygen -t rsa -b 2048 -f server_key -N ""
# Vous DEVEZ générer votre propre clé et la placer dans le même répertoire
# ou adapter le chemin.
# Pour cet exemple, on suppose qu'une clé existe. Si elle n'existe pas, paramiko en générera une temporaire.
HOST_KEY_PATH = 'server_key'
try:
    host_key = paramiko.RSAKey(filename=HOST_KEY_PATH)
except FileNotFoundError:
    print(f"Clé serveur RSA ({HOST_KEY_PATH}) non trouvée. Paramiko en générera une temporaire.")
    # Alternative: Générer une clé si elle n'existe pas
    # try:
    #     host_key = paramiko.RSAKey.generate(2048)
    #     host_key.write_private_key_file(HOST_KEY_PATH)
    #     print(f"Nouvelle clé serveur RSA générée et sauvegardée: {HOST_KEY_PATH}")
    # except Exception as e:
    #     print(f"Impossible de générer ou sauvegarder la clé serveur: {e}")
    #     exit(1)
    # Pour l'instant, on laisse paramiko gérer la clé temporaire si elle manque.
    host_key = paramiko.RSAKey.generate(2048) # Utilise une clé en mémoire


SSH_BANNER = "SSH-2.0-OpenSSH_8.2p1 Ubuntu-4ubuntu0.1" # Bannière commune pour masquer

class SSHServerHandler (paramiko.ServerInterface):
    def __init__(self, client_address):
        self.client_ip = client_address[0]
        self.event = threading.Event()

    def check_channel_request(self, kind, chanid):
        if kind == 'session':
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_auth_password(self, username, password):
        logger.info(
            f"Tentative d'authentification SSH",
            extra={'extra_data': {'ip': self.client_ip, 'user': username, 'pass': password}}
        )
        # Toujours refuser l'authentification après l'avoir loggée
        self.event.set() # Signale que l'authentification a été tentée
        return paramiko.AUTH_FAILED

    def check_auth_publickey(self, username, key):
        logger.info(
            f"Tentative d'authentification SSH par clé publique",
            extra={'extra_data': {'ip': self.client_ip, 'user': username, 'key_type': key.get_name(), 'key_fingerprint': key.get_fingerprint().hex()}}
        )
        # Toujours refuser
        self.event.set()
        return paramiko.AUTH_FAILED

    def check_auth_none(self, username):
        # Certains clients (comme nmap) peuvent tenter une authentification 'none'
        logger.info(
            f"Tentative d'authentification SSH 'none'",
            extra={'extra_data': {'ip': self.client_ip, 'user': username}}
        )
        self.event.set()
        return paramiko.AUTH_FAILED

    def get_allowed_auths(self, username):
        # Annonce les méthodes supportées (même si elles échoueront toutes)
        return 'password,publickey'

    def check_channel_shell_request(self, channel):
        # Ne jamais autoriser un shell
        self.event.set()
        return False

    def check_channel_pty_request(self, channel, term, width, height, pixelwidth, pixelheight, modes):
        # Ne jamais autoriser de PTY
        self.event.set()
        return False


def start_ssh_honeypot(host='0.0.0.0', port=2222):
    """Démarre le serveur honeypot SSH."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.listen(100)
        print(f"[*] Honeypot SSH écoute sur {host}:{port}")
        logger.info(f"Honeypot SSH démarré sur {host}:{port}")

        while True:
            try:
                client_socket, client_address = sock.accept()
                print(f"[*] Connexion SSH reçue de {client_address[0]}:{client_address[1]}")
                transport = paramiko.Transport(client_socket)
                transport.local_version = SSH_BANNER # Définir la bannière
                transport.add_server_key(host_key)

                server_handler = SSHServerHandler(client_address)
                transport.start_server(server=server_handler)

                # Attendre la tentative d'authentification ou une déconnexion précoce
                channel = transport.accept(20) # Timeout pour accepter un canal
                if channel is None:
                    # Souvent, le client se déconnecte après avoir vu les méthodes d'auth ou la clé
                    logger.info(f"Client {client_address[0]} déconnecté avant authentification complète.")
                else:
                    # Si un canal est ouvert (ne devrait pas arriver avec notre config), logguer
                    logger.warning(f"Canal inattendu ouvert par {client_address[0]}", extra={'extra_data': {'ip': client_address[0], 'channel_type': channel.get_name()}})


                # Attendre que l'événement d'authentification soit signalé ou timeout
                server_handler.event.wait(10) # Attendre max 10s après la connexion pour une tentative d'auth

                transport.close() # Ferme la connexion proprement

            except Exception as e:
                ip = client_address[0] if 'client_address' in locals() else 'inconnu'
                logger.error(f"Erreur lors du traitement de la connexion SSH de {ip}: {e}", exc_info=True)
                if 'transport' in locals() and transport.is_active():
                    transport.close()

    except Exception as e:
        logger.critical(f"Erreur critique du Honeypot SSH : {e}", exc_info=True)
        print(f"[!] Erreur critique du Honeypot SSH : {e}")
    finally:
        if 'sock' in locals():
            sock.close()
        print("[*] Honeypot SSH arrêté.")
        logger.info("Honeypot SSH arrêté.")

# Pour tester ce module seul (sera lancé par run.py plus tard)
# if __name__ == "__main__":
#     start_ssh_honeypot() 