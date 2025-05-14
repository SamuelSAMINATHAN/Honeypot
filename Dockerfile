FROM python:3.11-slim-bullseye

# Définir le répertoire de travail
WORKDIR /app

# Copier le fichier des dépendances
COPY requirements.txt requirements.txt

# Installer les dépendances
# --no-cache-dir réduit la taille de l'image
# --upgrade pip assure une version récente de pip
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copier le reste du code de l'application
COPY . .

# (Optionnel mais recommandé) Générer la clé SSH si elle n'existe pas.
# Ceci est fait au runtime dans ce cas pour éviter de stocker une clé dans l'image.
# On pourrait aussi le faire ici avec RUN ssh-keygen ... mais ce n'est pas idéal.
# Assurez-vous que le script `run.py` ou les modules gèrent l'absence de clé.

# Créer le répertoire de logs si besoin (bien que le logger.py le fasse déjà)
RUN mkdir -p logs

# Exposer les ports utilisés par les honeypots (ajuster si les ports par défaut sont changés)
# SSH
EXPOSE 2222
# HTTP
EXPOSE 8080
# FTP (contrôle + plage passive)
EXPOSE 2121
EXPOSE 60000-60010

# Commande pour lancer l'application
# Utilisation de `CMD` pour pouvoir surcharger facilement
CMD ["python", "run.py"] 