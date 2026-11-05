# app/services/rag/type_detection_service.py
# ============================================================
# DÉTECTION DU TYPE DE MESSAGE (RAG, Étape E §2)
# ============================================================
# 3 niveaux, dans l'ordre : (1) filtre Python (re) pour le conversationnel
# ÉVIDENT, (2) LLM en json_mode, (3) repli sur des règles Python par
# mots-clés si le LLM échoue. Une question de connaissance n'est JAMAIS
# classée conversationnelle, même précédée d'une salutation.
# ============================================================

import json
import logging
import re
import unicodedata
from pathlib import Path
from typing import Any, Optional

import yaml

from app.services.llm import LLMNotAvailableError, get_llm_provider

logger = logging.getLogger(__name__)

TYPES_VALIDES = (
    "catalogue", "inventaire", "contenu_formation", "synthese_thematique",
    "localisation", "question_fond", "aide_plateforme", "conversationnel",
    "hors_sujet", "incomprehensible",
)

_DOSSIER_PROMPTS = Path(__file__).resolve().parents[2] / "prompts" / "rag"

# ── Niveau 1 : filtre Python pour le conversationnel évident ──
# Ne matche que des messages COURTS et PURS (rien d'autre dans le message) :
# une vraie question après une salutation doit être classée ailleurs.
_PATTERNS_CONVERSATIONNEL = [
    r"(quel(le)?s? (est|sont) (ton|tes) roles?|quelles ton roles?|ton role|tes roles)",
    r"(tu es creer? (pourquoi|pour quoi|pouauoi)|pourquoi as[ -]tu ete cree)",
    # Salutations orthographiées + abréviations courantes (bjr, slt, slut=salut, bsr, cc, bonne journée)
    r"(bonjour|salut|bonsoir|coucou|hello|hi|bonne journ[ée]e|bonne soir[ée]e|bjr|bsr|slt|slut|salu|cc|wesh|hey)",
    r"(merci( beaucoup| bien)?|mrc|thks|thank(s| you))",
    r"(au revoir|[àa] bient[ôo]t|bye|[àa] plus|a \+|a plus|tchao|tchau|ciao)",
    r"(qui es[ -]tu|que (sais|peux)[ -]tu faire|comment (tu fonctionnes|[çc]a marche)|"
    r"(c'est quoi|qu'est-ce que) (toi|cet assistant))",
]
_REGEX_CONVERSATIONNEL = re.compile(
    "^(" + "|".join(_PATTERNS_CONVERSATIONNEL) + r")[\s!?.,]*$", re.IGNORECASE,
)

# Messages trop courts / inintelligibles (≤ 3 mots, aucun mot reconnaissable)
# On détecte : séquences de touches aléatoires, abréviations inconnues seules.
_REGEX_ININTELLIGIBLE = re.compile(
    r"^[a-z]{1,4}(\s[a-z]{1,4}){0,2}[!?.,\s]*$", re.IGNORECASE,
)


def _normaliser(texte: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texte)
    sans_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sans_accents.lower().strip()


def filtre_conversationnel_evident(message: str) -> bool:
    """True si le message est PUREMENT une salutation/remerciement/question
    sur l'assistant — rien d'autre dedans."""
    return bool(_REGEX_CONVERSATIONNEL.match(_normaliser(message)))


def _charger_prompt() -> str:
    with open(_DOSSIER_PROMPTS / "detection_type.yaml", "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    sections = [data.get(cle, "") for cle in ("role", "tache", "format", "exemples")]
    return "\n\n".join(s for s in sections if s)


async def _detecter_via_llm(
    message: str, conv: Any = None, session_id: str | None = None,
) -> str | None:
    try:
        llm = get_llm_provider()
    except LLMNotAvailableError:
        return None

    try:
        # Injecter le contexte de la conversation pour éviter les déclassements
        # (ex : "explique l'étape 4" après une réponse aide_plateforme)
        contexte_conv = ""
        if conv and conv.echanges:
            derniers = conv.echanges[-4:]  # 2 derniers tours max
            lignes = []
            for e in derniers:
                role = "Utilisateur" if e.role == "utilisateur" else "Assistant"
                lignes.append(f"{role} : {e.texte[:200]}")
            if lignes:
                contexte_conv = (
                    "\n\nCONTEXTE DE LA CONVERSATION (pour bien classer la suite) :\n"
                    + "\n".join(lignes)
                    + "\n\nSi le message actuel est une relance ou un approfondissement "
                    "du sujet précédent, classe-le dans le même type que la réponse précédente. "
                    "Les lignes assistant incluent le type de réponse précédent."
                )
        if session_id:
            contexte_conv += (
                "\n\nCONTEXTE RAG : une session de formation précise est sélectionnée dans l'interface. "
                "Une demande cohérente de l'utilisateur porte probablement sur les supports de cette session. "
                "Ne classe pas une demande compréhensible comme incompréhensible ; utilise question_fond "
                "si elle demande une explication, un exemple, un exercice ou une application pédagogique. "
                "Garde inventaire/catalogue uniquement si ces demandes sont explicites."
            )

        reponse = await llm.generate_with_retry(
            system_prompt=_charger_prompt() + contexte_conv,
            user_prompt=f"Message : {message}",
            temperature=0.0,
            max_tokens=300,  # modèle de raisonnement Groq : 50 était insuffisant (voir resume_service.py)
            json_mode=True,
            max_retries=2,
            reasoning_effort="low",
        )
        type_detecte = json.loads(reponse["content"]).get("type")
        return type_detecte if type_detecte in TYPES_VALIDES else None
    except Exception as exc:
        logger.warning(f"⚠️ Détection de type LLM échouée : {type(exc).__name__} — {exc}")
        return None


# ── Niveau 3 : repli par mots-clés (LLM indisponible/échoué) ──
_MOTS_CLES = {
    "hors_sujet": ("météo", "meteo", "température à", "temperature a", "recette de", "horoscope", "résultat du match", "resultat du match", "actualité politique"),
    "catalogue": ("catalogue", "quelles formations", "liste des formations", "formations disponibles", "formations proposez"),
    "inventaire": ("inventaire", "documents indexes", "supports indexes", "combien de documents", "combien de supports"),
    "synthese_thematique": (
        "resume", "resumer", "fais un resume", "faire un resume",
        "donne moi le resume", "donne moi la resume", "synthese",
        "formations concernant", "thematique",
    ),
    "localisation": ("ou est", "ou se trouve", "ou est explique", "quelle page", "quelle diapositive"),
    "contenu_formation": (
        "contenu de", "contenus de", "supports de la formation",
        "support du cours", "supports du cours", "supports de cours",
        "documents du cours", "que contient la formation",
    ),
    "aide_plateforme": ("valider", "hitl", "relance", "facture", "plateforme", "forma-ia", "comment faire pour"),
}


def detecter_type_regles(message: str) -> str:
    """Repli déterministe si le LLM est indisponible ou échoue. Par défaut :
    question_fond (la recherche vectorielle + le mode strict géreront
    naturellement les cas hors sujet en l'absence de contexte pertinent)."""
    normalise = _normaliser(message)
    termes_support = ("support", "supports", "cours", "document", "documents")
    termes_resume = ("resume", "resumer", "synthese", "contenu", "contient")
    termes_exercices = ("exercice", "exercices", "question", "questions", "quiz", "oral", "participant")
    demande_inventaire = (
        "inventaire" in normalise
        or "combien" in normalise and any(terme in normalise for terme in termes_support)
        or "liste des supports" in normalise
        or "liste des documents" in normalise
        or "quels documents sont indexes" in normalise
        or "quels supports sont indexes" in normalise
    )
    if demande_inventaire:
        return "inventaire"
    if any(terme in normalise for terme in termes_support) and any(
        terme in normalise for terme in termes_exercices
    ):
        return "question_fond"
    if any(terme in normalise for terme in termes_support) and any(
        terme in normalise for terme in termes_resume
    ):
        return "contenu_formation"
    if any(terme in normalise for terme in termes_support) and any(
        terme in normalise for terme in ("indexer", "indexe", "indexee", "je vous parle", "je veux dire", "ces documents", "ces supports")
    ):
        return "contenu_formation"
    for type_cible, mots in _MOTS_CLES.items():
        if any(mot in normalise for mot in mots):
            return type_cible
    return "question_fond"


def _est_inintelligible(message: str) -> bool:
    """True si le message est trop court ou ne contient que des séquences
    de lettres sans signification après normalisation (sans accents, minuscules).

    Un message ≤ 4 caractères hors espaces qui n'est pas une abréviation connue
    (ni salutation, ni remerciement) est probablement une faute de frappe grave
    ou une séquence aléatoire.
    """
    normalise = _normaliser(message)
    stripped = normalise.strip()
    # Vide ou mono-caractère
    if len(stripped) <= 1:
        return True
    # Correspondance avec les patterns de salutation → pas inintelligible
    if _REGEX_CONVERSATIONNEL.match(stripped):
        return False
    # Contient un chiffre → probablement une vraie demande (référence, code, année)
    if re.search(r"\d", stripped):
        return False
    # Si le message est court (≤ 3 tokens) et ne contient que de petits mots
    tokens = stripped.split()
    # Court (≤ 3 tokens) avec tous les tokens ≤ 6 lettres (azerty=6, lkjhg=5…)
    if len(tokens) <= 3 and all(len(t) <= 6 for t in tokens):
        # Vérifie qu'aucun token ne ressemble à un mot du domaine métier ou une
        # abréviation de salutation déjà gérée
        mots_domaine = {
            "rag", "tdr", "pdf", "llm", "ia", "m1", "m2", "m3", "m5", "m6", "m7",
            "hitl", "doc", "ocr", "api",
        }
        mots_salutation = {
            "bjr", "bsr", "slt", "slut", "salu", "cc", "wesh", "hey", "hi",
            "mrc", "thks", "tchao", "tchau", "ciao", "bonjour", "salut",
            "merci", "bonsoir", "coucou", "hello", "bye",
        }
        if not any(t in mots_domaine or t in mots_salutation for t in tokens):
            # Teste aussi que le message ne correspond pas à un pattern connu
            mots_courants = {
                "aide", "aide-moi", "help", "oui", "non", "ok", "super",
                "bien", "voila", "voilà", "parfait", "compris",
                "refaire", "retry", "reessai", "again", "encore", "suite",
                "resume", "resumer", "detail", "continuer",
            }
            if not any(t in mots_courants for t in tokens):
                return True
    return False


def _dernier_type_conversation(conv: Any) -> str | None:
    """Retourne le type_reponse du dernier échange assistant dans la conversation."""
    if not conv or not conv.echanges:
        return None
    for echange in reversed(conv.echanges):
        if echange.role == "assistant" and hasattr(echange, "type_reponse") and echange.type_reponse:
            return echange.type_reponse
    return None


def _est_relance_contextuelle(message: str) -> bool:
    """True si le message est un approfondissement sans sujet propre
    (numéro seul, 'explique', 'détaille', 'et le X', 'parle moi du X')."""
    normalise = _normaliser(message)
    tokens = normalise.strip().split()
    if len(tokens) > 8:
        return False
    patterns_relance = re.compile(
        r"^(explique|detaille|developpe|parle moi (de|du)|qu.est[ -]ce que|c.est quoi|"
        r"et (le|la|les|l.)|dis moi (plus sur|comment)|comment (fonctionne|marche)|"
        r"c.est (quoi|quoi exactement)|refaire|reessai|retry|recommence|encore|suite|"
        r"resumer?|faire un resume|donne (moi )?(la |le |un |une )?resume)[\s\w]{0,40}$",
        re.IGNORECASE,
    )
    # Message court avec un chiffre seul ou "étape X"
    if re.match(r"^(etape\s*)?\d+[\s!?.,]*$", normalise.strip()):
        return True
    return bool(patterns_relance.match(normalise.strip()))


async def detecter_type(
    message: str, conv: Any = None, session_id: str | None = None,
) -> str:
    """Point d'entrée : filtre Python -> contexte conversation -> LLM -> repli par règles.

    Le paramètre ``conv`` (Conversation) est utilisé pour détecter les relances
    contextuelles (ex : « explique l'étape 4 » après une réponse aide_plateforme).
    """
    if filtre_conversationnel_evident(message):
        return "conversationnel"

    # Message inintelligible (frappe aléatoire, trop court, incompréhensible) :
    # ne pas appeler Voyage ni le LLM — demander poliment une reformulation.
    if _est_inintelligible(message):
        return "incomprehensible"

    # Relance contextuelle : si le dernier échange était aide_plateforme et que
    # le message est un approfondissement sans sujet propre → rester aide_plateforme.
    if conv and _est_relance_contextuelle(message):
        dernier = _dernier_type_conversation(conv)
        if dernier in ("aide_plateforme", "conversationnel"):
            return "aide_plateforme"
        if dernier in ("question_fond", "localisation", "synthese_thematique", "contenu_formation"):
            return dernier  # reste dans le même domaine

    # Les questions de fonctionnement de FORMA-IA sont fréquentes à l'oral,
    # parfois transcrites « platforme ». Elles ne nécessitent pas de LLM pour
    # être orientées vers le guide de la plateforme.
    normalise = _normaliser(message)
    if "platform" in normalise or "forma-ia" in normalise or "forma ia" in normalise:
        return "aide_plateforme"

    # Une demande documentaire claire ne doit pas être rétrogradée en
    # « incompréhensible » ou inventaire par une classification LLM variable.
    type_documentaire = detecter_type_regles(message)
    termes_documentaires = ("support", "supports", "cours", "document", "documents")
    if any(terme in normalise for terme in termes_documentaires) and type_documentaire in {
        "contenu_formation", "question_fond", "synthese_thematique", "inventaire",
    }:
        return type_documentaire

    type_llm = await _detecter_via_llm(message, conv=conv, session_id=session_id)
    if type_llm:
        if session_id and type_llm in {
            "incomprehensible", "inventaire", "catalogue", "conversationnel", "hors_sujet",
        }:
            # Une salutation pure a déjà été traitée avant l'appel au LLM.
            # Dans une session choisie, une classification vague ou erronée ne
            # doit pas détourner une demande documentaire du corpus. Les demandes
            # explicites catalogue/inventaire restent distinctes.
            type_regle = detecter_type_regles(message)
            if type_regle in {"catalogue", "inventaire"}:
                return type_regle
            if type_regle in {"contenu_formation", "question_fond", "synthese_thematique", "localisation"}:
                return type_regle
            return "question_fond"
        return type_llm

    return detecter_type_regles(message)
