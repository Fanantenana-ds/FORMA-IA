"""Garde-fous M1 réel : aucune confirmation à partir du texte généré seul."""
import re
import unicodedata
from datetime import UTC, datetime, timedelta, timezone
from urllib.parse import urlparse

from app.services.veille.prefilter_service import _TECH_TITLE
from app.utils.url_utils import normalize_url
from app.services.veille.source_registry import domain_matches, load_registry

_NEED = re.compile(
    r"formation|formateur|renforcement.*capacit|training|consultant|prestataire|"
    r"appel.*offre|manifestation.*int[ée]r[êe]t|request for proposal", re.IGNORECASE,
)
_LOCAL = re.compile(
    r"madagascar|malgache|malagasy|antananarivo|toamasina|antsirabe|"
    r"mahajanga|fianarantsoa|toliara|antsiranana", re.IGNORECASE,
)
_MONTHS = {"janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4,
           "mai": 5, "juin": 6, "juillet": 7, "août": 8, "aout": 8,
           "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12}
MADAGASCAR = timezone(timedelta(hours=3), "Indian/Antananarivo")


def deadline_details(value, quote, source, now=None):
    """L'heure doit accompagner la date dans le contenu de CET avis."""
    now = now or datetime.now(UTC)
    local_now = now.astimezone(MADAGASCAR)
    day = datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    text = compact(source.get("content"))
    host = urlparse(str(source.get("url"))).hostname or ""
    dates = [re.escape(day.isoformat()), rf"0?{day.day}[/-]0?{day.month}[/-]{day.year}"]
    dates.extend(rf"0?{day.day}\s+{name}\s+{day.year}" for name, month in _MONTHS.items() if month == day.month)
    # Date et heure dans la même courte clause ; pas l'heure d'un autre avis.
    match = re.search(r"(?:" + "|".join(dates) + r")[^.;\n]{0,35}?\b(?:à|a|at)\s+(\d{1,2})\s*(?:h|:)(\d{2})?", text)
    deadline_at = None
    if match and int(match.group(1)) <= 23 and int(match.group(2) or 0) <= 59:
        nearby = text[max(0, match.start() - 80):match.end() + 60]
        tz = UTC if re.search(r"\butc\b|\bgmt\b", nearby) else MADAGASCAR if (
            host.endswith(".mg") or re.search(r"heure locale|heure de madagascar|antananarivo", nearby)) else None
        if tz is not None:
            deadline_at = datetime(day.year, day.month, day.day, int(match.group(1)), int(match.group(2) or 0), tzinfo=tz)
    expired = deadline_at <= now if deadline_at else day < local_now.date()
    days = (day - local_now.date()).days
    return {"deadline_at": deadline_at.isoformat() if deadline_at else None,
            "deadline_precision": "datetime" if deadline_at else "date",
            "deadline_timezone": str(deadline_at.tzinfo) if deadline_at else None,
            "freshness_status": "expirée" if expired else "bientôt_clôturée" if days <= 7 else "ouverte",
            "needs_closing_time": day == local_now.date() and deadline_at is None}


def compact(text):
    value = unicodedata.normalize("NFKC", str(text or ""))
    return " ".join(value.replace("’", "'").replace("‘", "'").split()).casefold()


def source_need(source):
    """Titre demandeur réellement lu ; jamais les mots de la recherche."""
    if source.get("verification_method") != "direct_public_page" or not source.get("last_verified_at"):
        return None
    title = str(source.get("title") or "").strip()
    body = str(source.get("content") or "")
    if (len(title) >= 20 and compact(title) in compact(body) and _TECH_TITLE.search(title)
            and re.search(r"recrutement|recherche|cherche|appel.*offre|manifestation.*int[ée]r[êe]t|mission|request for", title, re.IGNORECASE)):
        return title
    return None


def source_literal(proposed, body):
    """Retrouve une chaîne citée dans le corps, sans rapprochement sémantique."""
    if not isinstance(proposed, str) or len(proposed.strip()) < 3:
        return None
    pattern = "".join(r"\s+" if char.isspace() else "['’‘]" if char in "'’‘" else re.escape(char)
                      for char in proposed.strip())
    match = re.search(pattern, body, re.IGNORECASE)
    return match.group() if match else None


def source_closing_date(source):
    """Date précédée d'un marqueur de clôture ; jamais une publication seule."""
    months = "|".join(_MONTHS)
    dates = rf"\d{{4}}-\d{{2}}-\d{{2}}|\d{{1,2}}[/-]\d{{1,2}}[/-]\d{{4}}|\d{{1,2}}\s+(?:{months})\s+\d{{4}}"
    matches = re.finditer(rf"(?:cl[ôo]ture|date limite|deadline|au plus tard)[^.;\n]{{0,100}}?(?P<day>{dates})",
                          str(source.get("content") or ""), re.IGNORECASE)
    found = {}
    for match in matches:
        value = match.group("day")
        try:
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                parsed = datetime.fromisoformat(value).date()
            else:
                parts = re.split(r"[\s/-]+", value.casefold())
                month = int(parts[1]) if parts[1].isdigit() else _MONTHS[parts[1]]
                parsed = datetime(int(parts[2]), month, int(parts[0])).date()
            found[parsed.isoformat()] = match.group()
        except (ValueError, KeyError):
            continue
    return next(iter(found.items())) if len(found) == 1 else (None, None)


def date_supported(value, evidence):
    """Une date extraite doit être lisible dans l'extrait qui la justifie."""
    if not value or not evidence:
        return False
    try:
        day = datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        return False
    text = compact(evidence)
    if day.isoformat() in text:
        return True
    for pattern in (rf"\b0?{day.day}[/-]0?{day.month}[/-]{day.year}\b",):
        if re.search(pattern, text):
            return True
    return any(month == day.month and re.search(rf"\b0?{day.day}\s+{name}\s+{day.year}\b", text)
               for name, month in _MONTHS.items())


def qualify_candidate(candidate, sources):
    """Retourne (candidat étayé, points à vérifier). Ne fait aucun appel réseau."""
    item = dict(candidate)
    url = normalize_url(item.get("url"))
    source = next((s for s in sources if normalize_url(s.get("url")) == url), None)
    gaps = []
    if source is None:
        gaps.append("URL sans correspondance dans les sources réellement collectées")
        source = {}
    source_text = " ".join([str(source.get("title") or ""), str(source.get("content") or "")])
    evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
    checked = {}
    for key in ("need", "organizer", "location", "deadline", "budget"):
        quote = evidence.get(key)
        if isinstance(quote, str) and len(quote.strip()) >= (3 if key == "organizer" else 4) and compact(quote) in compact(source_text):
            checked[key] = quote.strip()
    origins = {key: "validated_model_quote" for key in checked}
    if (len(checked.get("need", "")) < 20 or not _NEED.search(checked.get("need", ""))
            or not _TECH_TITLE.search(checked.get("need", ""))):
        observed_need = source_need(source)
        if observed_need:
            checked["need"] = observed_need
            origins["need"] = "direct_source_heading"
    if source.get("verification_method") == "direct_public_page" and source.get("last_verified_at"):
        body = str(source.get("content") or "")
        # Une citation peut être présente dans la page mais correspondre au
        # besoin plutôt qu'au nom de l'organisme (cas observé sur le FID).
        proposed_org = str(item.get("organizer") or "")
        observed_org = source_literal(proposed_org, body) or source_literal(re.sub(r"\s*\([^)]*\)", "", proposed_org).strip(), body)
        if observed_org:
            item["organizer"] = observed_org
            checked["organizer"] = observed_org
            origins["organizer"] = "direct_source_match"
        observed_day, closing_quote = source_closing_date(source)
        if observed_day and (not item.get("deadline") or not date_supported(item.get("deadline"), checked.get("deadline"))):
            item["deadline"] = observed_day
            checked["deadline"] = closing_quote
            origins["deadline"] = "direct_closing_clause"
    if len(checked.get("need", "")) < 20 or not _NEED.search(checked.get("need", "")) or not _TECH_TITLE.search(checked.get("need", "")):
        gaps.append("Besoin de prestation informatique non étayé par un extrait source")
    organizer = str(item.get("organizer") or "").strip()
    organizer_quote = checked.get("organizer", "")
    named_organizer = re.sub(r"\s*\([^)]*\)", "", organizer).strip()
    organizer_matches = bool(organizer and organizer_quote and (
        compact(organizer) in compact(organizer_quote) or
        (len(named_organizer) >= 12 and compact(named_organizer) in compact(organizer_quote))
    ))
    if not organizer_matches:
        # Accepter l'acronyme effectivement cité sans inventer son expansion.
        acronyms = re.findall(r"\b[A-Z]{3,10}\b", organizer)
        alias = next((a for a in acronyms if re.search(r"\b" + re.escape(a) + r"\b", organizer_quote)), None)
        if alias:
            item["organizer"] = alias
            organizer_matches = True
    if not organizer_matches:
        gaps.append("Organisme demandeur à identifier dans l'avis original")
    host = (urlparse(str(source.get("url") or "")).hostname or "").lower()
    local = _LOCAL.search(checked.get("location", "")) or host.endswith(".mg")
    if not local:
        gaps.append("Localisation Madagascar non étayée par la source")
    path = urlparse(url).path.lower()
    if not _TECH_TITLE.search(str(source.get("title") or "")) and not _TECH_TITLE.search(path.replace("-", " ").replace("_", " ")):
        gaps.append("Objet informatique de l'annonce à confirmer ; éviter les encarts et articles associés")
    if not any(domain_matches(host, domain) for domain in load_registry().domains()):
        gaps.append("Source hors registre : vérification humaine nécessaire")
    if "#avis-" in url or "adminshowbuyer" in path or path.endswith("list.do") or path.rstrip("/") in {
        "/appels-doffres", "/appels-a-manifestations-dinterets"
    } or "/category/" in path:
        gaps.append("Lien individuel de l'annonce à retrouver ; la source est une liste")
    deadline = item.get("deadline")
    if not date_supported(deadline, checked.get("deadline")):
        item["deadline"] = None
        gaps.append("Échéance absente ou non justifiée dans le texte source")
    deadline_info = {"freshness_status": "date_inconnue", "deadline_at": None,
                     "deadline_precision": None, "deadline_timezone": None}
    if item.get("deadline"):
        deadline_info = deadline_details(item["deadline"], checked.get("deadline"), source)
        if deadline_info.pop("needs_closing_time"):
            gaps.append("Échéance aujourd'hui à Madagascar : heure et fuseau de clôture à confirmer")
        if deadline_info["freshness_status"] == "expirée":
            gaps.append("Échéance de candidature dépassée : ne pas préparer de nouvelle candidature")
    try:
        confidence = float(item.get("confidence", 0))
    except (ValueError, TypeError):
        confidence = 0
    if not 0.75 <= confidence <= 1.0:
        gaps.append("Confiance IA insuffisante pour une confirmation")
    if re.search(r"\bCDI\b|\bCDD\b", source_text, re.IGNORECASE) and not re.search(
        r"prestataire|prestation|freelance|consultant ind[ée]pendant|cabinet.*formation",
        source_text, re.IGNORECASE,
    ):
        gaps.append("Annonce d'emploi salarié : prestation externe à établir")
    if not checked.get("budget"):
        item["budget"] = "Non précisé"
    reference = item.get("reference")
    item["reference"] = reference if isinstance(reference, str) and compact(reference) in compact(source_text) else None
    item.update(
        url=url, source_title=source.get("title"), evidence=checked, evidence_origin=origins,
        published_at=source.get("published_at"), captured_at=source.get("captured_at"),
        last_checked_at=datetime.now(UTC).isoformat(), last_verified_at=source.get("last_verified_at"),
        verification_method=source.get("verification_method", "tavily_excerpt"), verification_status="to_review" if gaps else "documented",
        is_actionable=not gaps, country_scope="Madagascar" if local else "Inconnu",
        **deadline_info,
    )
    if gaps:
        item.update(status="to_review", score=0, reason="Score métier non attribué : preuves insuffisantes.",
                    score_evaluated=False, score_label="Non évalué",
                    ai_risk_level="élevé", next_step="verify_source",
                    title=str(source.get("title") or "Candidat sans source correspondante"),
                    summary="Source à vérifier avant de conclure à une opportunité : " + "; ".join(gaps),
                    ai_summary=str(source.get("title") or "Candidat sans source correspondante"),
                    ai_relevance="Compatibilité à confirmer à partir de l'annonce originale.",
                    ai_recommendation="Consulter l'annonce originale et vérifier : " + "; ".join(gaps) + ".",
                    ai_points_to_verify=gaps)
    else:
        item.update(ai_risk_level="moyen", next_step="human_review", score_evaluated=True,
                    ai_points_to_verify=["Vérifier l'éligibilité d'ALTIORA et le dossier complet avant toute offre"],
                    ai_recommendation="Examiner le dossier et l'éligibilité d'ALTIORA ; après validation humaine, préparer le TDR ou l'offre correspondant au besoin : " + checked["need"])
    return item, gaps
