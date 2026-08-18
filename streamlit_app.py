# -*- coding: utf-8 -*-
"""Simulateur de fan-out de requêtes, bilingue français / anglais.

Portage local de Qforia (iPullRank), backend API Gemini avec sortie
structurée contrainte par schéma.

Chaque utilisateur fournit sa propre clé API : le palier gratuit de Gemini
est limité par projet, une clé partagée serait épuisée par le premier
utilisateur de la journée.

Lancement local :
    python -m streamlit run streamlit_app.py
"""

from __future__ import annotations

import io
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import pandas as pd
import streamlit as st
from google import genai
from google.genai import types
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from prompts import (
    FORMAT_LABELS,
    MODES,
    RESPONSE_SCHEMA,
    TYPE_LABELS,
    build_prompt,
)

# ---------------------------------------------------------------------------
# Modèles servis en palier gratuit, vérifiés le 2026-08-18.
# Les modèles « pro » sont volontairement absents : leur quota gratuit est
# de zéro et tout appel échoue en 429 sans facturation activée.
# ---------------------------------------------------------------------------
AVAILABLE_MODELS = [
    "gemini-3.6-flash",
    "gemini-3.7-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
]

MAX_WORKERS = 4
CONSOLE_URL = "https://aistudio.google.com/apikey"

# ---------------------------------------------------------------------------
# Libellés d'interface
# ---------------------------------------------------------------------------
UI = {
    "fr": {
        "title": "Simulateur de fan-out de requêtes",
        "subtitle": (
            "Simule les requêtes synthétiques qu'un moteur génératif peut dériver d'une requête "
            "source, et le format de contenu vers lequel chacune serait routée."
        ),
        "config": "Configuration",
        "model": "Modèle",
        "model_help": (
            "Le quota gratuit est décompté par modèle. Si un modèle est épuisé, "
            "basculez sur un autre."
        ),
        "api_key": "Votre clé API Gemini",
        "api_key_help": "Elle reste dans votre session et n'est jamais enregistrée.",
        "api_from_env": "Clé lue dans la variable d'environnement.",
        "api_from_secrets": "Clé fournie par le serveur.",
        "onboarding_title": "Première utilisation",
        "onboarding_body": (
            "Cet outil a besoin d'une clé API Gemini, gratuite et personnelle. "
            "Chacun utilise la sienne, car le quota gratuit est compté par compte : "
            "une clé partagée serait épuisée par le premier utilisateur de la journée."
        ),
        "onboarding_steps": (
            "1. Ouvrez **[Google AI Studio](%s)** et connectez-vous avec un compte Google.\n"
            "2. Cliquez sur **Create API key**, puis copiez la clé.\n"
            "3. Collez-la dans le champ **Votre clé API Gemini**, dans la colonne de gauche.\n\n"
            "Comptez deux minutes. Aucune carte bancaire n'est demandée."
        ),
        "confidentiality": (
            "Le palier gratuit de Gemini autorise Google à exploiter le contenu envoyé pour "
            "améliorer ses produits. N'inscrivez donc aucune information client confidentielle "
            "dans le champ de contexte : décrivez un secteur et un positionnement, pas un nom "
            "de client ni un chiffre sous accord de confidentialité."
        ),
        "quota_note": (
            "Le palier gratuit autorise environ vingt générations par jour et par modèle. "
            "Au-delà, changez de modèle ou revenez le lendemain."
        ),
        "lang": "Langue des résultats",
        "input_mode": "Saisie",
        "single": "Une requête",
        "bulk": "Une liste",
        "query_label": "Requête source",
        "query_placeholder": "camping familial avec parc aquatique en Vendée",
        "bulk_label": "Requêtes, une par ligne",
        "bulk_placeholder": "camping familial en Vendée\nlocation mobil-home bord de mer",
        "search_mode": "Profondeur",
        "market": "Marché ciblé",
        "market_placeholder": "France",
        "market_help": "Ancre le vocabulaire, les unités et les acteurs cités sur ce marché.",
        "context": "Contexte métier",
        "context_placeholder": "Campings 4 et 5 étoiles, littoral atlantique, cible familles.",
        "context_help": "Secteur, positionnement, gamme. C'est le levier de pertinence le plus fort.",
        "run": "Lancer le fan-out",
        "no_key": "Renseignez votre clé API dans la colonne de gauche.",
        "no_query": "Renseignez au moins une requête.",
        "processing": "Génération en cours...",
        "done": "Terminé.",
        "ok_line": "{q} : {n} requêtes générées.",
        "err_line": "{q} : échec. {e}",
        "results": "Requêtes synthétiques",
        "plans": "Plan de génération par requête source",
        "errors": "Erreurs",
        "breakdown_type": "Répartition par type",
        "breakdown_format": "Répartition par format de routage",
        "dl_csv": "CSV",
        "dl_ndjson": "NDJSON",
        "dl_md": "Markdown",
        "exports": "Exports",
        "empty": "Aucune requête synthétique n'a été générée.",
        "caveat": (
            "Ces requêtes sont plausibles, pas mesurées. L'outil cartographie une couverture "
            "éditoriale à construire, il ne constate pas ce que Google génère réellement."
        ),
        "col_source": "Requête source",
        "col_query": "Requête générée",
        "col_type": "Type",
        "col_intent": "Intention",
        "col_reason": "Justification",
        "col_format": "Format de routage",
        "col_format_reason": "Justification du format",
        "col_count": "Nombre",
        "col_share": "Part",
        "col_target": "Nombre visé",
        "col_target_reason": "Justification du nombre",
        "total": "{n} requêtes générées à partir de {s} requêtes sources.",
    },
    "en": {
        "title": "Query fan-out simulator",
        "subtitle": (
            "Simulates the synthetic queries a generative engine may derive from a source query, "
            "and the content format each one would be routed to."
        ),
        "config": "Configuration",
        "model": "Model",
        "model_help": (
            "The free quota is counted per model. If one model is exhausted, switch to another."
        ),
        "api_key": "Your Gemini API key",
        "api_key_help": "It stays in your session and is never stored.",
        "api_from_env": "Key read from the environment variable.",
        "api_from_secrets": "Key provided by the server.",
        "onboarding_title": "First time here",
        "onboarding_body": (
            "This tool needs a Gemini API key, free and personal. Everyone uses their own, "
            "because the free quota is counted per account: a shared key would be exhausted "
            "by the first user of the day."
        ),
        "onboarding_steps": (
            "1. Open **[Google AI Studio](%s)** and sign in with a Google account.\n"
            "2. Click **Create API key**, then copy the key.\n"
            "3. Paste it into the **Your Gemini API key** field in the left column.\n\n"
            "It takes two minutes. No payment card is required."
        ),
        "confidentiality": (
            "Gemini's free tier allows Google to use submitted content to improve its products. "
            "Do not put confidential client information in the context field: describe a sector "
            "and a positioning, not a client name or a figure under a confidentiality agreement."
        ),
        "quota_note": (
            "The free tier allows roughly twenty generations per day per model. "
            "Beyond that, switch model or come back tomorrow."
        ),
        "lang": "Output language",
        "input_mode": "Input",
        "single": "One query",
        "bulk": "A list",
        "query_label": "Source query",
        "query_placeholder": "family campsite with water park in south west France",
        "bulk_label": "Queries, one per line",
        "bulk_placeholder": "family campsite near the beach\nmobile home rental south of france",
        "search_mode": "Depth",
        "market": "Target market",
        "market_placeholder": "United Kingdom",
        "market_help": "Anchors vocabulary, units and named players to that market.",
        "context": "Business context",
        "context_placeholder": "4 and 5 star campsites, Atlantic coast, families with young children.",
        "context_help": "Sector, positioning, range. This is the strongest lever on relevance.",
        "run": "Run fan-out",
        "no_key": "Enter your API key in the left column.",
        "no_query": "Please provide at least one query.",
        "processing": "Generating...",
        "done": "Complete.",
        "ok_line": "{q}: {n} queries generated.",
        "err_line": "{q}: failed. {e}",
        "results": "Synthetic queries",
        "plans": "Generation plan per source query",
        "errors": "Errors",
        "breakdown_type": "Breakdown by type",
        "breakdown_format": "Breakdown by routing format",
        "dl_csv": "CSV",
        "dl_ndjson": "NDJSON",
        "dl_md": "Markdown",
        "exports": "Exports",
        "empty": "No synthetic queries were generated.",
        "caveat": (
            "These queries are plausible, not measured. The tool maps editorial coverage to "
            "build, it does not observe what Google actually generates."
        ),
        "col_source": "Source query",
        "col_query": "Generated query",
        "col_type": "Type",
        "col_intent": "Intent",
        "col_reason": "Reasoning",
        "col_format": "Routing format",
        "col_format_reason": "Format reasoning",
        "col_count": "Count",
        "col_share": "Share",
        "col_target": "Target count",
        "col_target_reason": "Reasoning for count",
        "total": "{n} queries generated from {s} source queries.",
    },
}


# ---------------------------------------------------------------------------
# Clé API
# ---------------------------------------------------------------------------


def resolve_server_key() -> tuple[str, str]:
    """Cherche une clé fournie par l'hébergeur, sinon laisse l'utilisateur saisir la sienne."""
    try:
        from_secrets = str(st.secrets.get("GEMINI_API_KEY", "")).strip()
    except Exception:  # noqa: BLE001 - aucun fichier de secrets, cas normal en local
        from_secrets = ""
    if from_secrets:
        return from_secrets, "secrets"

    from_env = os.environ.get("GEMINI_API_KEY", "").strip()
    if from_env:
        return from_env, "env"

    return "", "user"


# ---------------------------------------------------------------------------
# Appel API
# ---------------------------------------------------------------------------


@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(min=2, max=45),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def call_model(api_key: str, model: str, prompt: str) -> dict:
    # Le client n'est pas mis en cache : il porterait la clé d'un utilisateur
    # dans un cache partagé par toutes les sessions. Sa construction est locale
    # et ne coûte aucun appel réseau.
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=RESPONSE_SCHEMA,
            temperature=1.0,
            # Aucun outil n'est exposé au modèle : on coupe l'appel de fonction
            # automatique, qui sinon émet un avertissement à chaque requête.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        ),
    )
    return json.loads(response.text)


def generate_fanout(api_key, model, query, mode_key, lang, market, context):
    """Retourne (plan de génération, liste de requêtes) pour une requête source."""
    data = call_model(api_key, model, build_prompt(query, mode_key, lang, market, context))
    return data.get("generation_details", {}), data.get("expanded_queries", [])


def friendly_error(exc: Exception, model: str, lang: str) -> str:
    """Traduit les pannes d'API récurrentes en message actionnable."""
    text = str(exc)
    if "RESOURCE_EXHAUSTED" in text or "429" in text:
        return {
            "fr": (
                f"Quota gratuit épuisé sur {model}, environ vingt générations par jour. "
                f"Choisissez un autre modèle dans la colonne de gauche, ou réessayez demain."
            ),
            "en": (
                f"Free quota exhausted on {model}, roughly twenty generations per day. "
                f"Pick another model in the left column, or try again tomorrow."
            ),
        }[lang]
    if "API key not valid" in text or "API_KEY_INVALID" in text or "400" in text:
        return {
            "fr": "Clé API refusée. Vérifiez que vous avez collé la clé en entier.",
            "en": "API key rejected. Check that you pasted the whole key.",
        }[lang]
    if "UNAVAILABLE" in text or "503" in text:
        return {
            "fr": "Le modèle est momentanément saturé. Relancez, ou changez de modèle.",
            "en": "The model is temporarily overloaded. Retry, or switch model.",
        }[lang]
    if "NOT_FOUND" in text or "404" in text:
        return {
            "fr": f"Le modèle {model} n'est pas accessible avec cette clé.",
            "en": f"Model {model} is not available with this key.",
        }[lang]
    return text


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------


def to_ndjson(rows: list[dict]) -> bytes:
    """NDJSON UTF-8 sans BOM, accents préservés."""
    buffer = io.StringIO()
    for row in rows:
        buffer.write(json.dumps(row, ensure_ascii=False) + "\n")
    return buffer.getvalue().encode("utf-8")


def to_markdown(rows: list[dict], plans: list[dict], lang: str, meta: dict) -> bytes:
    """Markdown lisible, groupé par requête source."""
    t = UI[lang]
    lines = [
        f"# {t['title']}",
        "",
        f"- {t['model']} : {meta['model']}",
        f"- {t['search_mode']} : {MODES[meta['mode_key']][lang]}",
    ]
    if meta.get("market"):
        lines.append(f"- {t['market']} : {meta['market']}")
    lines += [f"- Date : {meta['stamp']}", "", f"> {t['caveat']}", ""]

    by_source: dict[str, list[dict]] = {}
    for row in rows:
        by_source.setdefault(row["lookup_query"], []).append(row)
    plan_by_source = {p["lookup_query"]: p for p in plans}

    for source, items in by_source.items():
        lines += [f"## {source}", ""]
        plan = plan_by_source.get(source)
        if plan and plan.get("reasoning_for_count"):
            lines += [f"*{plan['reasoning_for_count']}*", ""]
        lines += [
            f"| {t['col_query']} | {t['col_type']} | {t['col_intent']} | {t['col_format']} |",
            "| --- | --- | --- | --- |",
        ]
        for item in items:
            type_label = TYPE_LABELS[lang].get(item["type"], item["type"])
            fmt_label = FORMAT_LABELS[lang].get(item["routing_format"], item["routing_format"])
            lines.append(
                f"| {item['query']} | {type_label} | "
                f"{item['user_intent'].replace('|', '/')} | {fmt_label} |"
            )
        lines.append("")

    return "\n".join(lines).encode("utf-8")


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Fan-out de requêtes",
    page_icon=":material/account_tree:",
    layout="wide",
)

st.session_state.setdefault("results", None)

server_key, key_source = resolve_server_key()

with st.sidebar:
    lang = st.segmented_control(
        "Langue / Language",
        options=["fr", "en"],
        default="fr",
        required=True,
        format_func=lambda code: {"fr": "Français", "en": "English"}[code],
        key="lang",
    )
    t = UI[lang]

    if key_source == "user":
        api_key = st.text_input(
            t["api_key"],
            type="password",
            help=t["api_key_help"],
            key="api_key",
            icon=":material/key:",
        ).strip()
    else:
        api_key = server_key
        st.caption(t["api_from_env"] if key_source == "env" else t["api_from_secrets"])

    model = st.selectbox(t["model"], AVAILABLE_MODELS, help=t["model_help"])

    input_mode = st.segmented_control(
        t["input_mode"],
        options=["single", "bulk"],
        default="single",
        required=True,
        format_func=lambda key: t[key],
    )
    if input_mode == "single":
        raw_input_text = st.text_area(
            t["query_label"], height=100, placeholder=t["query_placeholder"]
        )
    else:
        raw_input_text = st.text_area(
            t["bulk_label"], height=170, placeholder=t["bulk_placeholder"]
        )

    mode_key = st.segmented_control(
        t["search_mode"],
        options=list(MODES.keys()),
        default="overview",
        required=True,
        format_func=lambda key: MODES[key][lang],
    )

    market = st.text_input(t["market"], placeholder=t["market_placeholder"], help=t["market_help"])
    context = st.text_area(
        t["context"], height=90, placeholder=t["context_placeholder"], help=t["context_help"]
    )

    run = st.button(t["run"], type="primary", icon=":material/graph_3:", width="stretch")

st.title(t["title"])
st.caption(t["subtitle"])

# Accueil affiché tant qu'aucune clé n'est disponible.
if not api_key:
    with st.container(border=True):
        st.subheader(t["onboarding_title"], anchor=False)
        st.write(t["onboarding_body"])
        st.markdown(t["onboarding_steps"] % CONSOLE_URL)
    st.info(t["quota_note"], icon=":material/schedule:")
    st.warning(t["confidentiality"], icon=":material/lock:")

if run:
    if not api_key:
        st.error(t["no_key"], icon=":material/key_off:")
        st.stop()

    lookups = [line.strip() for line in raw_input_text.splitlines() if line.strip()]
    if not lookups:
        st.warning(t["no_query"], icon=":material/edit_note:")
        st.stop()

    rows: list[dict] = []
    plans: list[dict] = []
    errors: list[dict] = []

    status = st.status(t["processing"], expanded=True)
    progress = st.progress(0.0)

    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(lookups))) as pool:
        futures = {
            pool.submit(
                generate_fanout, api_key, model, query, mode_key, lang, market, context
            ): query
            for query in lookups
        }
        for done_count, future in enumerate(as_completed(futures), start=1):
            query = futures[future]
            try:
                details, expanded = future.result()
                plans.append(
                    {
                        "lookup_query": query,
                        "target_query_count": details.get("target_query_count"),
                        "reasoning_for_count": details.get("reasoning_for_count", ""),
                    }
                )
                for obj in expanded:
                    rows.append({"lookup_query": query, **{
                        field: obj.get(field, "")
                        for field in (
                            "query",
                            "type",
                            "user_intent",
                            "reasoning",
                            "routing_format",
                            "format_reason",
                        )
                    }})
                status.write(t["ok_line"].format(q=query, n=len(expanded)))
            except Exception as exc:  # noqa: BLE001 - toute panne API doit rester lisible
                message = friendly_error(exc, model, lang)
                status.write(t["err_line"].format(q=query, e=message))
                errors.append({"lookup_query": query, "error": message})
            progress.progress(done_count / len(lookups))

    status.update(label=t["done"], state="complete")

    # Ordre des sources conservé tel que saisi, l'exécution étant concurrente.
    order = {query: i for i, query in enumerate(lookups)}
    rows.sort(key=lambda r: order.get(r["lookup_query"], 0))
    plans.sort(key=lambda p: order.get(p["lookup_query"], 0))

    st.session_state.results = {
        "rows": rows,
        "plans": plans,
        "errors": errors,
        "lang": lang,
        "meta": {
            "model": model,
            "mode_key": mode_key,
            "market": market,
            "stamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        },
    }

results = st.session_state.results

if results and results["rows"]:
    rows = results["rows"]
    lang_out = results["lang"]
    t_out = UI[lang_out]

    st.info(t_out["caveat"], icon=":material/info:")
    st.markdown(
        f"**{t_out['total'].format(n=len(rows), s=len({r['lookup_query'] for r in rows}))}**"
    )

    df = pd.DataFrame(rows)
    display = pd.DataFrame(
        {
            t_out["col_source"]: df["lookup_query"],
            t_out["col_query"]: df["query"],
            t_out["col_type"]: df["type"].map(lambda v: TYPE_LABELS[lang_out].get(v, v)),
            t_out["col_intent"]: df["user_intent"],
            t_out["col_format"]: df["routing_format"].map(
                lambda v: FORMAT_LABELS[lang_out].get(v, v)
            ),
            t_out["col_reason"]: df["reasoning"],
            t_out["col_format_reason"]: df["format_reason"],
        }
    )

    st.subheader(t_out["results"], anchor=False)
    st.dataframe(display, hide_index=True, height=460)

    left, right = st.columns(2)
    for column, field, heading, labels in (
        (left, "type", t_out["breakdown_type"], TYPE_LABELS[lang_out]),
        (right, "routing_format", t_out["breakdown_format"], FORMAT_LABELS[lang_out]),
    ):
        counts = df[field].value_counts()
        with column:
            st.subheader(heading, anchor=False)
            st.dataframe(
                pd.DataFrame(
                    {
                        heading: [labels.get(v, v) for v in counts.index],
                        t_out["col_count"]: counts.values,
                        t_out["col_share"]: [f"{v / len(df):.0%}" for v in counts.values],
                    }
                ),
                hide_index=True,
            )

    st.subheader(t_out["plans"], anchor=False)
    st.dataframe(
        pd.DataFrame(results["plans"]).rename(
            columns={
                "lookup_query": t_out["col_source"],
                "target_query_count": t_out["col_target"],
                "reasoning_for_count": t_out["col_target_reason"],
            }
        ),
        hide_index=True,
    )

    st.subheader(t_out["exports"], anchor=False)
    slug = datetime.now().strftime("%Y%m%d-%H%M")
    with st.container(horizontal=True):
        st.download_button(
            t_out["dl_csv"],
            data=display.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"fanout-{slug}.csv",
            mime="text/csv",
            icon=":material/table_view:",
        )
        st.download_button(
            t_out["dl_ndjson"],
            data=to_ndjson(rows),
            file_name=f"fanout-{slug}.ndjson",
            mime="application/x-ndjson",
            icon=":material/data_object:",
        )
        st.download_button(
            t_out["dl_md"],
            data=to_markdown(rows, results["plans"], lang_out, results["meta"]),
            file_name=f"fanout-{slug}.md",
            mime="text/markdown",
            icon=":material/description:",
        )

    if results["errors"]:
        st.subheader(t_out["errors"], anchor=False)
        st.dataframe(pd.DataFrame(results["errors"]), hide_index=True)

elif results:
    st.warning(UI[results["lang"]]["empty"], icon=":material/search_off:")
    if results["errors"]:
        st.dataframe(pd.DataFrame(results["errors"]), hide_index=True)
