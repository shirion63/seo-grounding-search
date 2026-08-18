# SEO Grounding Search

Simule les requêtes synthétiques qu'un moteur de recherche génératif peut dériver d'une requête source, et le format de contenu vers lequel chacune serait probablement routée. Interface bilingue français et anglais.

Inspiré des travaux d'iPullRank sur le fan-out de requêtes, publiés sous le nom [Qforia](https://github.com/ipullrank-dev/qforia). Le concept, la typologie des six transformations et la liste des formats de routage viennent de leur recherche, et leur reviennent.

Cette implémentation est réécrite et étendue : prompts français et anglais natifs, sortie contrainte par schéma côté API, champs marché et contexte métier, traitement par lot concurrent, exports CSV, NDJSON et Markdown, gestion multi-utilisateurs de la clé API.

## Ce que l'outil est, et ce qu'il n'est pas

C'est un **générateur d'hypothèses de couverture éditoriale**. Le modèle produit des requêtes *plausibles*. Ce ne sont pas les requêtes que Google génère réellement, et aucune donnée Google n'est consultée.

À utiliser pour cadrer un plan de contenu ou repérer des angles absents. Jamais pour affirmer à un client ce que fait le mode IA de Google.

## Chacun sa clé API

L'outil demande une clé API Gemini personnelle, gratuite, à créer sur [Google AI Studio](https://aistudio.google.com/apikey). Deux minutes, aucune carte bancaire.

Le quota gratuit est décompté **par compte et par modèle**, à hauteur d'une vingtaine de générations par jour. Une clé partagée entre plusieurs personnes serait donc épuisée par le premier utilisateur de la journée. C'est pour cette raison que l'application ne stocke aucune clé côté serveur et demande la sienne à chaque utilisateur. La clé saisie reste dans la session du navigateur et n'est jamais enregistrée.

Si le quota d'un modèle est atteint, il suffit d'en choisir un autre dans la liste : le compteur est indépendant pour chacun.

## Confidentialité, à lire avant de s'en servir sur un dossier client

Le palier gratuit de Gemini autorise Google à exploiter le contenu envoyé pour améliorer ses produits. C'est écrit dans leur grille tarifaire, où la colonne « contenu utilisé pour améliorer nos produits » vaut « oui » sur le gratuit et « non » sur le payant.

Conséquence pratique : le champ **Contexte métier** ne doit recevoir aucune information confidentielle. On y décrit un secteur, un positionnement, une gamme. Jamais un nom de client, un chiffre d'affaires, ni un élément couvert par un accord de confidentialité.

## Utilisation

Tout se pilote dans la colonne de gauche.

| Paramètre | Effet |
| --- | --- |
| Langue | Bascule l'interface **et** la langue de génération des requêtes. |
| Modèle | Uniquement des modèles servis en palier gratuit. |
| Saisie | Une requête, ou une liste à raison d'une requête par ligne. |
| Profondeur | Aperçu IA produit au moins 10 requêtes, Mode IA au moins 20. Le modèle fixe le nombre exact et le justifie. |
| Marché ciblé | Ancre le vocabulaire, les unités et les acteurs cités sur un marché donné. |
| Contexte métier | Le levier de pertinence le plus fort. Secteur, positionnement, gamme. |

Les résultats affichent chaque requête générée avec son type de transformation, l'intention supposée, le format de contenu de routage et les justifications, plus deux répartitions de synthèse.

## Exports

Trois formats, tous en UTF-8 :

- **CSV** avec BOM, pour ouverture directe dans Excel sans casser les accents.
- **NDJSON** sans BOM, accents préservés, pour tout retraitement en DuckDB ou polars.
- **Markdown** groupé par requête source, à verser dans Obsidian ou Notion.

## Lancement en local

```powershell
.\lancer.ps1
```

ou, avec un environnement Python disposant des dépendances :

```bash
pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

L'interface s'ouvre sur `http://localhost:8501`.

En local, une variable d'environnement `GEMINI_API_KEY` évite d'avoir à saisir la clé à chaque démarrage. Le champ de saisie n'apparaît que si cette variable est absente.

`lancer.ps1` cherche un interpréteur Python dans cet ordre : un `.venv` à la racine du projet, puis le chemin donné par la variable `SEO_GROUNDING_PYTHON`, puis le `python` du système.

## Déploiement

L'application est prévue pour Streamlit Community Cloud, à partir de ce dépôt, en application privée sur invitation par email.

**Ne posez aucune clé API dans les secrets de l'application.** Le code accepte une clé serveur si elle existe, mais ce serait remettre tout le monde sur le même quota de vingt générations par jour. Sans secret, chaque utilisateur saisit la sienne et dispose du sien.

## Modèles

Vérifié le 2026-08-18 : `gemini-3.6-flash` (défaut, le plus stable), `gemini-3.7-flash` (saturation fréquente en heures pleines), `gemini-3.5-flash`, `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`.

Les modèles « pro » sont absents de la liste : leur quota gratuit est de zéro et tout appel échoue, faute de facturation activée sur le projet Google Cloud.

Consommation mesurée : environ 5 000 tokens par génération complète, dont l'essentiel en raisonnement et en sortie.

## Rester en gratuit, et le vérifier

L'application ne peut pas basculer en facturé toute seule. Sans compte de facturation lié au projet Google Cloud, un dépassement de quota renvoie une erreur 429, jamais une facture. Le passage au payant suppose une activation explicite côté Google Cloud.

Deux points de vigilance en revanche.

**La liste de modèles va périmer.** Google retire régulièrement des modèles du service gratuit : `gemini-2.5-flash` et `gemini-2.5-pro` sont déjà refusés aux nouveaux comptes. Si un modèle se met à répondre en 404, rafraîchir la liste servie :

```bash
curl -s "https://generativelanguage.googleapis.com/v1beta/models?key=$GEMINI_API_KEY"   | python -c "import sys,json;[print(m['name']) for m in json.load(sys.stdin)['models'] if 'generateContent' in m.get('supportedGenerationMethods',[])]"
```

Puis mettre à jour `AVAILABLE_MODELS` dans `streamlit_app.py` en ne gardant que des modèles `flash`. Un modèle `pro` ajouté par mégarde échouerait en 429 pour tout le monde.

**Le gratuit a un coût de confidentialité.** Il autorise Google à exploiter le contenu envoyé. Activer la facturation ferait disparaître les quotas et cette clause, mais ce n'est pas le choix retenu. Tant qu'on reste en gratuit, la règle sur le champ de contexte métier s'applique sans exception.

## Fichiers

| Fichier | Rôle |
| --- | --- |
| `prompts.py` | Prompts français et anglais, taxonomies, schéma de sortie. C'est ici qu'on itère pour améliorer la qualité. |
| `streamlit_app.py` | Interface, appels API, exports. |
| `lancer.ps1` | Raccourci de lancement sous Windows. |
