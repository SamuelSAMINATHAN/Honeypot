from flask import Flask, request, Response, make_response
from logutils.logger import get_logger
import html
import logging

logger = get_logger('http')

app = Flask(__name__)

# Bannière serveur trompeuse
SERVER_BANNER = "Apache/2.4.41 (Ubuntu)"

@app.before_request
def log_request_info():
    """Loggue chaque requête reçue avant de la traiter."""
    # Éviter de logger les requêtes pour favicon.ico trop souvent si désiré
    # if request.path == '/favicon.ico':
    #     return

    log_data = {
        'ip': request.remote_addr,
        'method': request.method,
        'path': request.path,
        'headers': dict(request.headers),
        'args': request.args.to_dict(),
        'form': request.form.to_dict(),
        'data': request.get_data(as_text=True) # Attention si données binaires
    }
    logger.info(f"Requête HTTP reçue: {request.method} {request.path}", extra={'extra_data': log_data})

@app.after_request
def add_server_header(response):
    """Ajoute une fausse bannière serveur à chaque réponse."""
    response.headers['Server'] = SERVER_BANNER
    return response

@app.route('/', methods=['GET', 'POST'])
def index():
    """Page d'accueil simple."""
    return f"<h1>Welcome</h1><p>Server running: {SERVER_BANNER}</p>"

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Fausse page de login qui loggue les identifiants."""
    message = ""
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        # Logguer les identifiants soumis (déjà loggué dans before_request, mais on peut ajouter un message spécifique)
        logger.warning(f"Tentative de login HTTP via /login", extra={'extra_data': {'ip': request.remote_addr, 'user': username, 'pass': password}})
        # Simuler un message d'erreur vague
        message = "<p style='color:red;'>Login failed. Please try again.</p>"

    # Le formulaire lui-même - PAS de protection XSS ici volontairement
    # Utilisation de html.escape pour afficher ce qui a été potentiellement injecté
    # sans l'exécuter dans le contexte de la réponse (mais c'est loggué brut)
    form_html = f'''
    <h2>Login Portal</h2>
    {message}
    <form method="post">
        Username: <input type="text" name="username" value="{html.escape(request.form.get('username', ''))}"><br>
        Password: <input type="password" name="password"><br>
        <input type="submit" value="Login">
    </form>
    '''
    return form_html

@app.route('/search', methods=['GET'])
def search():
    """Fausse page de recherche vulnérable à XSS réflected."""
    query = request.args.get('q', '')
    # Refléter directement le paramètre 'q' dans la page (vulnérabilité XSS)
    # Logger spécifiquement la tentative de recherche
    if query:
        logger.warning(f"Recherche effectuée sur /search", extra={'extra_data': {'ip': request.remote_addr, 'query': query}})

    return f'''
    <h2>Search</h2>
    <form method="get">
        Search for: <input type="text" name="q" value="{html.escape(query)}">
        <input type="submit" value="Search">
    </form>
    <hr>
    <h3>Results for: {query}</h3>
    <p>No results found.</p> 
    '''

@app.route('/admin')
@app.route('/wp-login.php')
@app.route('/phpmyadmin')
def common_scan_paths():
    """Intercepte les scans sur des chemins communs."""
    logger.warning(f"Accès à un chemin sensible potentiel: {request.path}", extra={'extra_data': {'ip': request.remote_addr}})
    # Répondre par un 404 Not Found pour ne pas trop en révéler
    return "Not Found", 404

# Fausse vulnérabilité Shellshock (exemple)
@app.route('/cgi-bin/status')
def shellshock_cgi():
    user_agent = request.headers.get('User-Agent', '')
    if '() {' in user_agent:
        logger.critical(f"Tentative potentielle d'exploitation Shellshock détectée!",
                       extra={'extra_data': {'ip': request.remote_addr, 'user_agent': user_agent}})
        # Répondre de manière générique
        return "Internal Server Error", 500
    return "OK", 200


def start_http_honeypot(host='0.0.0.0', port=8080):
    """Démarre le serveur honeypot HTTP avec Flask."""
    print(f"[*] Honeypot HTTP écoute sur {host}:{port}")
    logger.info(f"Honeypot HTTP démarré sur {host}:{port}")
    try:
        # Utiliser waitress ou gunicorn serait mieux en "production" de honeypot
        # mais pour la simplicité, le serveur de dev Flask suffit ici.
        # Désactiver le logger de Flask pour ne pas dupliquer les logs déjà gérés
        log = logging.getLogger('werkzeug')
        log.disabled = True
        app.logger.disabled = True
        # Lancer le serveur Flask
        app.run(host=host, port=port, debug=False)
    except Exception as e:
        logger.critical(f"Erreur critique du Honeypot HTTP : {e}", exc_info=True)
        print(f"[!] Erreur critique du Honeypot HTTP : {e}")
    finally:
        print("[*] Honeypot HTTP arrêté.")
        logger.info("Honeypot HTTP arrêté.")

# Pour tester ce module seul (sera lancé par run.py plus tard)
# if __name__ == "__main__":
#     # Besoin de réimporter logging pour désactiver werkzeug car il est importé par app.run
#     import logging
#     start_http_honeypot() 