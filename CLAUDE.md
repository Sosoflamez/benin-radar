# CLAUDE.md — Benin-radar

## Vue d'ensemble

Benin-radar est un système de détection de vitesse par vision par ordinateur destiné au contrôle routier au Bénin. Il analyse un flux caméra en temps réel pour :

1. Détecter et suivre les véhicules (detection + tracking)
2. Calculer leur vitesse réelle (calibration caméra → coordonnées monde)
3. Lire les plaques d'immatriculation (ANPR/LAPI)
4. Enregistrer les infractions avec preuves (image, vitesse, horodatage, plaque)

Langue du projet : **code et identifiants en anglais**, commentaires, docstrings, messages de commit et UI en **français**.

## Stack technique

- **Backend** : Django 5.x + Django REST Framework (Python 3.12)
- **Base de données** : PostgreSQL 16
- **Vision** : OpenCV, Ultralytics YOLOv8 (détection véhicules), ByteTrack ou supervision pour le tracking
- **OCR plaques** : EasyOCR (fallback : PaddleOCR). Plaques béninoises : format `AB 1234 RB` ou similaire — voir `apps/anpr/plates.py`
- **Traitement asynchrone** : Celery + Redis (l'analyse vidéo ne se fait JAMAIS dans le cycle requête/réponse Django)
- **Temps réel dashboard** : Django Channels + WebSocket (notifications d'infractions live)
- **Conteneurisation** : Docker + docker-compose (services : web, worker, redis, db, éventuellement un service `vision` séparé)
- **Frontend dashboard** : Django templates + Tailwind CSS + Alpine.js (pas de SPA pour le MVP)

## Commandes

```bash
# Environnement
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# Base de données
docker compose up -d db redis
python manage.py migrate
python manage.py createsuperuser

# Développement
python manage.py runserver
celery -A config worker -l info          # worker vision/OCR
celery -A config beat -l info            # tâches planifiées (purge, rapports)

# Qualité
ruff check . --fix
ruff format .
pytest                                    # tous les tests
pytest apps/detection -x                  # un module, arrêt au 1er échec
pytest --cov=apps --cov-report=term-missing

# Docker complet
docker compose up --build
```

## Architecture du projet

```
benin-radar/
├── config/                  # settings, urls, celery, asgi (split settings: base/dev/prod)
├── apps/
│   ├── cameras/             # Camera, CalibrationProfile, gestion des flux (RTSP/fichier)
│   ├── detection/           # pipeline vision : capture, détection YOLO, tracking, estimation vitesse
│   ├── anpr/                # lecture de plaques : détection plaque, OCR, normalisation format béninois
│   ├── infractions/         # Infraction, Evidence, workflow de validation (auto → agent → validée)
│   ├── dashboard/           # vues web, temps réel (Channels), statistiques
│   └── api/                 # DRF : endpoints REST versionnés (/api/v1/)
├── ml_models/               # poids YOLO/OCR (gitignorés, téléchargés via script)
├── media/evidence/          # images de preuve (organisées par date : YYYY/MM/DD/)
├── scripts/                 # download_models.py, calibrate_camera.py, benchmark_pipeline.py
└── tests/                   # tests d'intégration inter-apps (les tests unitaires vivent dans chaque app)
```

## Modèle de données (cœur)

- **Camera** : nom, localisation (lat/lng), url_flux, limite_vitesse (km/h), active
- **CalibrationProfile** (FK Camera) : matrice d'homographie (JSON), points de référence, distance réelle mesurée, date de calibration
- **VehicleDetection** : camera, track_id, timestamps entrée/sortie de zone, vitesse_calculée, confiance, bbox
- **PlateReading** : detection (FK), plaque_brute, plaque_normalisée, confiance_ocr, image_crop
- **Infraction** : detection, camera, vitesse_retenue, limite, plaque, statut (`detectee` → `verifiee` → `validee` / `rejetee`), agent_validateur, preuves
- **Evidence** : infraction (FK), image pleine, crop plaque, métadonnées EXIF-like (hash SHA-256 pour l'intégrité)

Règle : une infraction n'est **jamais supprimée**, seulement rejetée (audit trail complet via `django-simple-history` sur Infraction et PlateReading).

## Pipeline vision (apps/detection)

1. **Capture** : lecture du flux (RTSP ou fichier vidéo en dev) frame par frame, échantillonnage configurable (ex. 15 FPS traités)
2. **Détection** : YOLOv8 (classes : car, motorcycle, bus, truck — les motos/zémidjans sont majoritaires au Bénin, ne pas les négliger)
3. **Tracking** : ByteTrack, un `track_id` stable par véhicule
4. **Vitesse** : méthode des deux lignes virtuelles + homographie. La vitesse = distance réelle calibrée / Δt entre franchissements. Moyenner sur plusieurs frames, rejeter si confiance tracking < seuil
5. **Déclenchement** : si vitesse > limite + tolérance (paramètre `SPEED_TOLERANCE_KMH`, défaut 5), capturer les frames de preuve et lancer la tâche Celery ANPR
6. **ANPR** : crop de la plaque → prétraitement OpenCV (redressement, contraste) → OCR → normalisation format béninois → score de confiance

Contraintes de performance : le pipeline doit tenir le temps réel sur CPU en dev (MacBook M2) ; l'inférence GPU est une optimisation, pas un prérequis. Toujours mesurer avec `scripts/benchmark_pipeline.py` avant/après une modification du pipeline.

## Conventions

- **Style** : ruff (line-length 100), type hints obligatoires sur les fonctions publiques
- **Django** : fat models / thin views, logique métier dans `services.py` par app, pas de logique dans les templates
- **Migrations** : une migration = un changement cohérent, jamais éditer une migration déjà mergée
- **Tests** : pytest + pytest-django, factory_boy pour les fixtures. Tout service métier a des tests. Les tests vision utilisent des vidéos courtes de fixtures dans `tests/fixtures/videos/` (jamais de flux réseau en test)
- **Git** : branches `feature/xxx`, commits en français à l'impératif ("Ajoute le calcul de vitesse par homographie"), merge vers `dev` puis `main`
- **Secrets** : jamais en dur. `django-environ` + `.env` (gitignoré), `.env.example` maintenu à jour
- **API** : DRF versionnée `/api/v1/`, pagination par défaut, throttling activé

## Sécurité et protection des données (IMPORTANT)

Les plaques d'immatriculation sont des **données personnelles** (loi n° 2017-20 sur le numérique au Bénin, autorité : APDP). Règles non négociables :

- Rétention limitée : purge automatique (tâche Celery beat) des détections **sans infraction** après N jours (`DETECTION_RETENTION_DAYS`, défaut 7)
- Accès aux preuves et plaques : réservé aux agents authentifiés avec permission dédiée, chaque consultation est journalisée
- Hash SHA-256 de chaque image de preuve calculé à la création (intégrité pour valeur probante)
- Aucune donnée réelle (plaques, visages) dans les fixtures de test ou le repo
- HTTPS obligatoire en prod, `SECURE_*` settings Django activés

## Ce qu'il ne faut PAS faire

- Ne pas traiter la vidéo dans une vue Django ou un signal — toujours Celery
- Ne pas stocker les frames vidéo brutes en base — seulement les preuves d'infraction sur disque/objet storage
- Ne pas inventer un format de plaque : si l'OCR ne matche pas un format béninois connu, statut `plaque_illisible`, jamais de correction "devinée"
- Ne pas coupler le pipeline vision aux modèles Django : `detection/pipeline/` doit être utilisable en standalone (entrées/sorties = dataclasses), la persistance se fait dans `services.py`
- Ne pas committer les poids de modèles ni les vidéos de fixtures lourdes (Git LFS ou script de téléchargement)

## Phases de développement

1. **Phase 1 — Socle** : projet Django, docker-compose, modèles Camera/Infraction, admin, auth agents
2. **Phase 2 — Pipeline vision offline** : détection + tracking + vitesse sur fichiers vidéo, script de calibration
3. **Phase 3 — ANPR** : lecture de plaques + normalisation format béninois + gestion des cas illisibles
4. **Phase 4 — Temps réel** : ingestion RTSP, Celery, dashboard live (Channels), workflow de validation agent
5. **Phase 5 — Durcissement** : purge RGPD/APDP, audit trail, rapports PDF, benchmarks, déploiement

À la fin de chaque phase : tests verts, `ruff check` propre, mise à jour de ce fichier si l'architecture évolue.