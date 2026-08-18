# -*- coding: utf-8 -*-
"""Prompts et taxonomies du simulateur de fan-out de requêtes (cabinet SEO Darwin).

Portage bilingue français / anglais de Qforia (iPullRank).
Le prompt est le coeur de l'outil : c'est ici qu'on itère, pas dans l'interface.

Rappel de méthode : ce que produit le modèle, ce sont des requêtes *plausibles*
que Google pourrait dériver d'une requête source. Ce n'est pas une mesure des
requêtes réellement générées par AI Mode. L'outil sert à cartographier une
couverture éditoriale, pas à constater un fait.
"""

# ---------------------------------------------------------------------------
# Taxonomies (identifiants machine stables, affichage localisé)
# ---------------------------------------------------------------------------

# Formats de contenu vers lesquels le système de routage peut orienter la
# récupération d'information. Identifiants conservés à l'identique de Qforia
# pour rester comparable avec les exports de l'outil d'origine.
ALLOWED_FORMATS = [
    "web_article",
    "faq_page",
    "how_to_steps",
    "comparison_table",
    "buyers_guide",
    "checklist",
    "product_spec_sheet",
    "glossary/definition",
    "pricing_page",
    "review_roundup",
    "tutorial_video/transcript",
    "podcast_transcript",
    "code_samples/docs",
    "api_reference",
    "calculator/tool",
    "dataset",
    "image_gallery",
    "map/local_pack",
    "forum/qna",
    "pdf_whitepaper",
    "case_study",
    "press_release",
    "interactive_widget",
]

FORMAT_LABELS = {
    "fr": {
        "web_article": "Article web",
        "faq_page": "Page FAQ",
        "how_to_steps": "Tutoriel par étapes",
        "comparison_table": "Tableau comparatif",
        "buyers_guide": "Guide d'achat",
        "checklist": "Check-list",
        "product_spec_sheet": "Fiche technique produit",
        "glossary/definition": "Glossaire ou définition",
        "pricing_page": "Page tarifs",
        "review_roundup": "Sélection d'avis et de tests",
        "tutorial_video/transcript": "Vidéo tutoriel ou transcription",
        "podcast_transcript": "Transcription de podcast",
        "code_samples/docs": "Exemples de code ou documentation",
        "api_reference": "Référence d'API",
        "calculator/tool": "Calculateur ou outil",
        "dataset": "Jeu de données",
        "image_gallery": "Galerie d'images",
        "map/local_pack": "Carte ou pack local",
        "forum/qna": "Forum ou questions-réponses",
        "pdf_whitepaper": "Livre blanc PDF",
        "case_study": "Étude de cas",
        "press_release": "Communiqué de presse",
        "interactive_widget": "Widget interactif",
    },
    "en": {fmt: fmt.replace("_", " ").replace("/", " / ").title() for fmt in ALLOWED_FORMATS},
}

# Types de transformation appliqués à la requête source.
QUERY_TYPES = [
    "reformulation",
    "related",
    "implicit",
    "comparative",
    "entity_expansion",
    "personalized",
]

TYPE_LABELS = {
    "fr": {
        "reformulation": "Reformulation",
        "related": "Requête connexe",
        "implicit": "Requête implicite",
        "comparative": "Requête comparative",
        "entity_expansion": "Expansion d'entité",
        "personalized": "Requête personnalisée",
    },
    "en": {
        "reformulation": "Reformulation",
        "related": "Related query",
        "implicit": "Implicit query",
        "comparative": "Comparative query",
        "entity_expansion": "Entity expansion",
        "personalized": "Personalized query",
    },
}

# Modes de recherche simulés. Les seuils reprennent ceux de Qforia.
MODES = {
    "overview": {"min_queries": 10, "fr": "Aperçu IA (simple)", "en": "AI Overview (simple)"},
    "aimode": {"min_queries": 20, "fr": "Mode IA (complexe)", "en": "AI Mode (complex)"},
}

# ---------------------------------------------------------------------------
# Schéma de sortie structurée (contrainte côté API, plus fiable que le parsing)
# ---------------------------------------------------------------------------

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "generation_details": {
            "type": "object",
            "properties": {
                "target_query_count": {"type": "integer"},
                "reasoning_for_count": {"type": "string"},
            },
            "required": ["target_query_count", "reasoning_for_count"],
            "propertyOrdering": ["target_query_count", "reasoning_for_count"],
        },
        "expanded_queries": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "type": {"type": "string", "enum": QUERY_TYPES},
                    "user_intent": {"type": "string"},
                    "reasoning": {"type": "string"},
                    "routing_format": {"type": "string", "enum": ALLOWED_FORMATS},
                    "format_reason": {"type": "string"},
                },
                "required": [
                    "query",
                    "type",
                    "user_intent",
                    "reasoning",
                    "routing_format",
                    "format_reason",
                ],
                "propertyOrdering": [
                    "query",
                    "type",
                    "user_intent",
                    "reasoning",
                    "routing_format",
                    "format_reason",
                ],
            },
        },
    },
    "required": ["generation_details", "expanded_queries"],
    "propertyOrdering": ["generation_details", "expanded_queries"],
}

# ---------------------------------------------------------------------------
# Construction du prompt
# ---------------------------------------------------------------------------


def _count_instruction_fr(query: str, mode_key: str) -> str:
    minimum = MODES[mode_key]["min_queries"]
    if mode_key == "overview":
        return (
            f"Analyse d'abord la requête de l'utilisateur : « {query} ». "
            f"En fonction de sa complexité et du mode « {MODES[mode_key]['fr']} », "
            f"détermine le nombre optimal de requêtes à générer. "
            f"Ce nombre doit être au minimum de {minimum}. "
            f"Pour une requête simple, vise {minimum} à {minimum + 2}. "
            f"Si la requête comporte plusieurs facettes distinctes ou appelle des questions de suivi fréquentes, "
            f"vise {minimum + 3} à {minimum + 5}. "
            f"Justifie brièvement ce nombre."
        )
    return (
        f"Analyse d'abord la requête de l'utilisateur : « {query} ». "
        f"En fonction de sa complexité et du mode « {MODES[mode_key]['fr']} », "
        f"détermine le nombre optimal de requêtes à générer. "
        f"Ce nombre doit être au minimum de {minimum}. "
        f"Pour une requête à facettes multiples couvrant des comparaisons, des procédures, "
        f"des caractéristiques techniques ou des arbitrages, génère {minimum + 5} à {minimum + 10} requêtes, voire davantage. "
        f"Justifie brièvement ce nombre."
    )


def _count_instruction_en(query: str, mode_key: str) -> str:
    minimum = MODES[mode_key]["min_queries"]
    if mode_key == "overview":
        return (
            f"First, analyse the user's query: \"{query}\". "
            f"Based on its complexity and the \"{MODES[mode_key]['en']}\" mode, "
            f"decide on the optimal number of queries to generate. "
            f"This number must be at least {minimum}. "
            f"For a straightforward query, aim for {minimum} to {minimum + 2}. "
            f"If the query has several distinct aspects or common follow-ups, "
            f"aim for {minimum + 3} to {minimum + 5}. "
            f"Give brief reasoning for the number you chose."
        )
    return (
        f"First, analyse the user's query: \"{query}\". "
        f"Based on its complexity and the \"{MODES[mode_key]['en']}\" mode, "
        f"decide on the optimal number of queries to generate. "
        f"This number must be at least {minimum}. "
        f"For multifaceted queries spanning comparisons, procedures, specifications or trade-offs, "
        f"generate {minimum + 5} to {minimum + 10} queries, or more. "
        f"Give brief reasoning for the number you chose."
    )


def _build_fr(query: str, mode_key: str, market: str, context: str) -> str:
    formats = ", ".join(ALLOWED_FORMATS)
    types_block = "\n".join(
        f"{i}. {TYPE_LABELS['fr'][t]} ({t})" for i, t in enumerate(QUERY_TYPES, start=1)
    )
    market_line = (
        f"Le marché ciblé est : {market}. Ancre le vocabulaire, les unités, les acteurs cités "
        f"et les habitudes de recherche sur ce marché.\n"
        if market.strip()
        else ""
    )
    context_line = (
        f"Contexte métier fourni par le consultant, à prendre en compte :\n{context.strip()}\n\n"
        if context.strip()
        else ""
    )

    return (
        "Tu simules le fan-out de requêtes du mode IA de Google pour les moteurs de recherche génératifs.\n"
        f"La requête source de l'utilisateur est : « {query} ». Le mode retenu est : « {MODES[mode_key]['fr']} ».\n"
        f"{market_line}"
        "\n"
        f"{context_line}"
        "Première tâche, déterminer le nombre total de requêtes à générer et le justifier :\n"
        f"{_count_instruction_fr(query, mode_key)}\n\n"
        "Une fois ce nombre arrêté, génère exactement ce nombre de requêtes synthétiques uniques.\n"
        "Chacun des types de transformation suivants doit être représenté au moins une fois, "
        "si le total le permet :\n"
        f"{types_block}\n\n"
        "Le champ « reasoning » de chaque requête explique pourquoi cette requête a été générée : "
        "rattache-la à la requête source, à son type et à l'intention de l'utilisateur.\n"
        "N'inclus aucune requête dépendant de l'historique de navigation en temps réel ou de la géolocalisation "
        "de l'utilisateur.\n\n"
        "Pour CHAQUE requête générée, identifie également le type de contenu le plus probablement privilégié "
        "par le système de routage pour la récupération et la synthèse. Un tutoriel oriente vers « how_to_steps » "
        "ou une transcription vidéo, une comparaison vers « comparison_table » ou « buyers_guide », et ainsi de suite. "
        "Choisis exactement UNE étiquette dans cette liste fermée :\n"
        f"{formats}\n"
        "Renseigne-la dans le champ « routing_format », et donne un « format_reason » d'une phrase.\n\n"
        "Contraintes de rédaction, impératives :\n"
        "- Rédige l'intégralité de la réponse en français, requêtes comprises.\n"
        "- Les requêtes doivent être formulées comme un internaute les exprimerait réellement, "
        "sans majuscule superflue ni ponctuation décorative.\n"
        "- Emploie les accents français corrects PARTOUT, y compris dans le champ « query » et sur les majuscules. "
        "Même si beaucoup d'internautes tapent sans accent, ces requêtes servent de livrable client : "
        "écris « Vendée » et non « vendee », « étoiles » et non « etoiles ». Aucune exception.\n"
        "- N'utilise jamais le tiret cadratin « — » ni le tiret demi-cadratin « – ». "
        "Utilise une virgule, un deux-points ou une phrase séparée.\n"
        "- Aucun anglicisme évitable dans les champs rédigés.\n"
        "- Les valeurs des champs « type » et « routing_format » restent en anglais, "
        "ce sont des identifiants techniques issus des listes fermées ci-dessus."
    )


def _build_en(query: str, mode_key: str, market: str, context: str) -> str:
    formats = ", ".join(ALLOWED_FORMATS)
    types_block = "\n".join(
        f"{i}. {TYPE_LABELS['en'][t]} ({t})" for i, t in enumerate(QUERY_TYPES, start=1)
    )
    market_line = (
        f"The target market is: {market}. Anchor vocabulary, units, named players "
        f"and search habits to that market.\n"
        if market.strip()
        else ""
    )
    context_line = (
        f"Business context provided by the consultant, to be taken into account:\n{context.strip()}\n\n"
        if context.strip()
        else ""
    )

    return (
        "You are simulating Google's AI Mode query fan-out for generative search systems.\n"
        f"The user's original query is: \"{query}\". The selected mode is: \"{MODES[mode_key]['en']}\".\n"
        f"{market_line}"
        "\n"
        f"{context_line}"
        "Your first task is to determine the total number of queries to generate, and the reasoning behind it:\n"
        f"{_count_instruction_en(query, mode_key)}\n\n"
        "Once you have settled on that number, generate exactly that many unique synthetic queries.\n"
        "Each of the following transformation types must be represented at least once, "
        "if the total allows:\n"
        f"{types_block}\n\n"
        "The \"reasoning\" field for each query explains why that query was generated: "
        "tie it back to the original query, its type and the user's intent.\n"
        "Do not include queries that depend on real-time browsing history or on the user's geolocation.\n\n"
        "For EACH generated query, also identify the content type the routing system would most likely prefer "
        "for retrieval and synthesis. A how-to routes to \"how_to_steps\" or a video transcript, "
        "a comparison routes to \"comparison_table\" or \"buyers_guide\", and so on. "
        "Choose exactly ONE label from this fixed list:\n"
        f"{formats}\n"
        "Return it in a field named \"routing_format\", and give a one-sentence \"format_reason\".\n\n"
        "Writing constraints:\n"
        "- Write the whole response in English, queries included.\n"
        "- Queries must read the way a real searcher would type or dictate them, "
        "with no superfluous capitalisation or decorative punctuation.\n"
        "- Use British English spelling.\n"
        "- Values of the \"type\" and \"routing_format\" fields stay as the exact identifiers "
        "from the fixed lists above."
    )


def build_prompt(query: str, mode_key: str, lang: str, market: str = "", context: str = "") -> str:
    """Construit le prompt de fan-out.

    query    : la requête source.
    mode_key : « overview » ou « aimode ».
    lang     : « fr » ou « en ».
    market   : marché ciblé, en texte libre (France, Royaume-Uni, Espagne...).
    context  : contexte métier optionnel fourni par le consultant.
    """
    if mode_key not in MODES:
        raise ValueError(f"Mode inconnu : {mode_key}")
    if lang == "fr":
        return _build_fr(query, mode_key, market, context)
    if lang == "en":
        return _build_en(query, mode_key, market, context)
    raise ValueError(f"Langue non prise en charge : {lang}")
