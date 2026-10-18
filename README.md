# 🍰 Cheesecake Battle - Semaine du Cheesecake & Mario Kart Battle

Site vitrine, système de commande en direct et classement des colocations avec panneau de validation administrateur pour l'association.

---

## 🎮 Le Concept
- **Objectif** : Vente de parts de cheesecake artisanal pour la semaine de l'association.
- **Le Grand Prix** : La colocation qui cumule le plus de parts validées remporte une **Nintendo Switch OLED + Mario Kart 8 Deluxe** !
- **Fonctionnalités** :
  - Vitrine gourmande des différentes recettes artisanales (Framboise, Caramel Spéculoos, Oreo...).
  - Formulaire de commande interactif avec panier flottant et calcul automatique.
  - Classement en direct (Podium Top 3 + liste complète) avec recherche par nom de coloc.
  - **Espace Admin Asso** (`/admin`) : Validation en 1 clic des commandes, calcul automatique des parts et mise à jour instantanée du classement.

---

## 🚀 Lancement en Local (Mac / Linux)

Le projet dispose déjà de son environnement virtuel `venv` préconfiguré.

```bash
# 1. Aller dans le dossier
cd ~/Desktop/Code/cheesecake-battle

# 2. Activer le venv
source venv/bin/activate

# 3. Lancer le serveur
uvicorn app:app --reload --port 8000
```

Accédez ensuite à :
- **Site public** : `http://localhost:8000`
- **Espace Admin** : `http://localhost:8000/admin` (Code secret : `cheesecake2026`)

---

## 🌐 Options de Déploiement

### Option 1 (Recommandée : GitHub + Render / Koyeb / Railway - 100% Gratuit)
Comme le site gère une base de données d'achats et un back-office de validation pour l'asso en Python (FastAPI + SQLite), le déploiement le plus simple et gratuit est :
1. Crée un dépôt GitHub (ex: `cheesecake-battle`) et pousse le code.
2. Connecte-toi sur [Render.com](https://render.com) (gratuit) avec ton compte GitHub.
3. Clique sur **"New Web Service"**, sélectionne ton dépôt GitHub.
4. Commande de build : `pip install -r requirements.txt`  
   Commande de start : `uvicorn app:app --host 0.0.0.0 --port $PORT`
5. Tu obtiens immédiatement une URL publique sécurisée (ex: `https://cheesecake-battle.onrender.com`) que tu peux partager à tous les étudiants !
   - À chaque `git push` sur GitHub, le site se met à jour automatiquement.

### Option 2 (100% GitHub Pages + Base Serverless)
Si tu souhaites une URL stricte `https://ton-asso.github.io/...` sans aucun hébergeur externe :
- GitHub Pages héberge uniquement des fichiers statiques (HTML/CSS/JS).
- On peut déporter la base de données vers **Supabase** (gratuit) ou une Google Sheet connectée.

---

## 🔑 Configuration Admin
- **URL** : `/admin`
- **Mot de passe par défaut** : `cheesecake2026`
- Peut être personnalisé via la variable d'environnement `ADMIN_SECRET`.
