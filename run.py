import json
import multiprocessing
import time
import signal
import sys
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.console import Console

# Importer les fonctions de démarrage des honeypots
# Gérer les ImportError si un module est désactivé ou non implémenté
try:
    from services.ssh_honeypot import start_ssh_honeypot
except ImportError:
    start_ssh_honeypot = None

try:
    from services.http_honeypot import start_http_honeypot
except ImportError:
    start_http_honeypot = None

try:
    from services.ftp_honeypot import start_ftp_honeypot
except ImportError:
    start_ftp_honeypot = None

# Charger la configuration
def load_config(config_path='config/honeypot_config.json'):
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Erreur : Fichier de configuration '{config_path}' non trouvé.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Erreur : Fichier de configuration '{config_path}' mal formé.")
        sys.exit(1)

config = load_config()

# Liste pour garder une trace des processus démarrés
processes = []

def shutdown(signum, frame):
    """Arrête proprement tous les processus honeypot."""
    print("\n[*] Arrêt des honeypots...")
    for p_info in processes:
        if p_info['process'].is_alive():
            print(f"    - Arrêt de {p_info['name']} (PID: {p_info['process'].pid})...")
            # Envoyer SIGTERM d'abord
            p_info['process'].terminate()
    
    # Attendre un peu que les processus se terminent
    time.sleep(2)
    
    # Forcer l'arrêt si nécessaire (SIGKILL)
    for p_info in processes:
        if p_info['process'].is_alive():
            print(f"    - Forcer l'arrêt de {p_info['name']} (PID: {p_info['process'].pid})...")
            p_info['process'].kill()
    
    print("[*] Tous les honeypots sont arrêtés.")
    sys.exit(0)

# Enregistrer les handlers de signaux pour un arrêt propre
signal.signal(signal.SIGINT, shutdown)  # Ctrl+C
signal.signal(signal.SIGTERM, shutdown) # kill

# Configuration de l'affichage avec Rich
console = Console()
layout = Layout()

# Définir les zones du layout (par exemple, une pour chaque honeypot)
layout.split_column(
    Layout(name="header", size=3),
    Layout(name="status", size=5), # Ajuster la taille si nécessaire
    Layout(name="footer", size=1)
)

layout["header"].update(Panel("[bold cyan]Honeypot Lab Status[/]", title="Honeypot Control Panel", border_style="green"))
layout["footer"].update(Panel("[italic grey50]Appuyez sur Ctrl+C pour arrêter[/]", border_style="red"))

def generate_status_table() -> Table:
    """Génère la table Rich affichant le statut des honeypots."""
    table = Table(title="Statut des Modules Honeypot", show_header=True, header_style="bold magenta")
    table.add_column("Module", style="dim", width=12)
    table.add_column("Activé", justify="center")
    table.add_column("Statut", justify="center")
    table.add_column("PID", justify="right")

    statuses = {}
    for p_info in processes:
        is_alive = p_info['process'].is_alive()
        statuses[p_info['name']] = {
            'status': "[bold green]Actif[/]" if is_alive else "[bold red]Arrêté[/]",
            'pid': str(p_info['process'].pid) if is_alive else "-"
        }

    # SSH
    ssh_enabled = config.get('enable_ssh', False)
    ssh_status = statuses.get('SSH', {'status': "[yellow]Non démarré[/]", 'pid': "-"})
    table.add_row(
        "SSH",
        "[green]Oui[/]" if ssh_enabled else "[red]Non[/]",
        ssh_status['status'] if ssh_enabled else "[grey50]Désactivé[/]",
        ssh_status['pid'] if ssh_enabled else "-"
    )

    # HTTP
    http_enabled = config.get('enable_http', False)
    http_status = statuses.get('HTTP', {'status': "[yellow]Non démarré[/]", 'pid': "-"})
    table.add_row(
        "HTTP",
        "[green]Oui[/]" if http_enabled else "[red]Non[/]",
        http_status['status'] if http_enabled else "[grey50]Désactivé[/]",
        http_status['pid'] if http_enabled else "-"
    )

    # FTP
    ftp_enabled = config.get('enable_ftp', False)
    ftp_status = statuses.get('FTP', {'status': "[yellow]Non démarré[/]", 'pid': "-"})
    table.add_row(
        "FTP",
        "[green]Oui[/]" if ftp_enabled else "[red]Non[/]",
        ftp_status['status'] if ftp_enabled else "[grey50]Désactivé[/]",
        ftp_status['pid'] if ftp_enabled else "-"
    )

    return table

if __name__ == "__main__":
    print("[*] Démarrage des honeypots configurés...")

    honeypot_targets = {
        'SSH': {'enabled': config.get('enable_ssh', False), 'target': start_ssh_honeypot, 'args': (config.get('ssh_host', '0.0.0.0'), config.get('ssh_port', 2222))},
        'HTTP': {'enabled': config.get('enable_http', False), 'target': start_http_honeypot, 'args': (config.get('http_host', '0.0.0.0'), config.get('http_port', 8080))},
        'FTP': {'enabled': config.get('enable_ftp', False), 'target': start_ftp_honeypot, 'args': (config.get('ftp_host', '0.0.0.0'), config.get('ftp_port', 2121), config.get('ftp_root', 'ftp_trap_dir'))}
    }

    for name, info in honeypot_targets.items():
        if info['enabled']:
            if info['target']:
                print(f"    - Démarrage du honeypot {name}...")
                p = multiprocessing.Process(target=info['target'], args=info['args'], daemon=True)
                p.start()
                processes.append({'name': name, 'process': p})
                time.sleep(0.5) # Petit délai pour laisser le temps au processus de démarrer
            else:
                print(f"    - Honeypot {name} activé mais le module n'a pas pu être importé.")
        else:
            print(f"    - Honeypot {name} désactivé dans la configuration.")

    if not processes:
        print("[!] Aucun honeypot n'a été démarré. Vérifiez la configuration.")
        sys.exit(0)

    print("[*] Tous les honeypots actifs sont démarrés.")

    # Affichage du statut en direct avec Rich
    with Live(layout, refresh_per_second=1, screen=True, transient=True) as live:
        while True:
            # Mettre à jour la table de statut
            layout["status"].update(generate_status_table())
            # Vérifier si des processus se sont arrêtés inopinément
            for p_info in processes:
                if not p_info['process'].is_alive():
                    # On pourrait ajouter une logique de redémarrage ici si nécessaire
                    pass # Le tableau indiquera qu'il est arrêté
            time.sleep(1) 