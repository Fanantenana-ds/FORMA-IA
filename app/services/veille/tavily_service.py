# app/services/veille/tavily_service.py
# ============================================================
# SERVICE TAVILY — VERSION CORRIGÉE (V3.0)
# ============================================================
# Corrections :
# 1. Utilise site: operators dans la query (plus fiable que include_domains)
# 2. Filtre POST-Tavily : rejette URLs non autorisées
# 3. Rejette contenu non-latin (chinois, cyrillique, arabe)
# 4. Rejette mots-clés bruit (krym, pilates, sports, etc.)
# 5. Fallback intelligent : si 0 résultats, essaie sans site:
# 6. Cache simple pour éviter conflits sur recherches répétées
# 7. Timeout adaptatif selon search_depth
# ============================================================

import asyncio
import hashlib
import logging
import os
import re
import time
from contextvars import ContextVar
from copy import deepcopy
from datetime import UTC, datetime
from datetime import date as datetime_date
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from app.services.veille import tavily_quota_service
from app.services.veille.tavily_quota_service import QuotaTavilyDepasseError
from app.services.veille.source_registry import SEARCH_GROUP, domain_matches, load_registry
from app.utils.retry import retry_with_backoff
from app.utils.url_utils import normalize_url
from app.services.veille.notice_resolution_service import NoticeResolver, deduplicate_notices
from app.services.veille.progress_service import emit_progress

logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURATION (depuis .env)
# ============================================================
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
MAX_RESULTS_TAVILY = int(os.getenv("TAVILY_MAX_RESULTS", "15"))
TAVILY_TIMEOUT = float(os.getenv("TAVILY_TIMEOUT", "12"))
RETRY_MAX_ATTEMPTS = int(os.getenv("RETRY_MAX_ATTEMPTS", "3"))
RETRY_BASE_DELAY = float(os.getenv("RETRY_BASE_DELAY", "1.0"))
# Budget total de la recherche, repli inclus. Il borne la latence sans
# transformer un échec réseau en faux résultat vide.
TAVILY_SEARCH_BUDGET_S = float(os.getenv("TAVILY_SEARCH_BUDGET_S", "25"))
_SEARCH_TRACE = ContextVar("m1_search_trace", default=None)


class SearchResults(list):
    """Compatible liste ; diagnostics liés à cet appel, pas à l'instance partagée."""
    def __init__(self, items, diagnostics):
        super().__init__(items)
        self.diagnostics = diagnostics

# Domaines autorisés (utilisés pour site: ET post-filtrage).
# Surchargeables par TAVILY_INCLUDE_DOMAINS (liste séparée par des virgules) ;
# les TAVILY_SITES_MAX premiers servent aux opérateurs site: de la requête.
_DEFAULT_TRUSTED_DOMAINS = [
    "app.armp.mg",
    "armp.mg",
    "asako.mg",
    "job2mada.com",
    "portaljob-madagascar.com",
    "codeko.tech",
    "optioncarriere.mg",
    "emploi.mg",
    "recrutement.mg",
    "developa.net",
    "linkedin.com",
    "facebook.com",
    "indeed.com",
]


def _domains_from_env(raw: str | None) -> list[str]:
    domains = [d.strip().lower() for d in (raw or "").split(",") if d.strip()]
    return domains or list(_DEFAULT_TRUSTED_DOMAINS)


TRUSTED_DOMAINS = _domains_from_env(os.getenv("TAVILY_INCLUDE_DOMAINS"))
TAVILY_SITES_MAX = max(1, int(os.getenv("TAVILY_SITES_MAX", "6")))

# Mots-clés bruit à rejeter (contenu non-pertinent)
NOISE_KEYWORDS = [
    # Conflits géopolitiques
    "krym", "crimea", "ukraine", "russia", "rosja", "wojna",
    "guerre", "war", "missile", "drone", "sanctions",
    # Lifestyle / non-tech
    "pilates", "yoga", "fitness", "skincare", "cosmetic", "beauty",
    # (pas "travel"/"voyage" : fréquents dans les TDR — "frais de voyage")
    "recipe", "cuisine", "restaurant", "tourisme",
    "sports", "football", "tennis", "movie", "film", "cinema",
    # Finance générale
    "bourse", "crypto", "bitcoin", "trading", "forex",
    # Bien-être (pas "santé"/"health" : un ministère de la Santé peut
    # lancer un appel d'offres de formation)
    "wellness", "spa", "massage",
    # Études (pas "université"/"university" : une université peut être
    # l'acheteur d'un appel d'offres de formation)
    "sapienza", "étudiant", "student",
    "bachelor", "master académique", "thèse", "phd",
]

# Regex pour détecter les caractères non-latins
NON_LATIN_REGEX = re.compile(
    r"[\u4E00-\u9FFF"   # CJK (chinois, japonais)
    r"\u3040-\u30FF"    # Hiragana/Katakana
    r"\u0600-\u06FF"    # Arabe
    r"\u0400-\u04FF"    # Cyrillique
    r"\u0590-\u05FF]"   # Hébreu
)

# Patterns de bruit (murs de connexion, etc.)
NOISE_PATTERNS = [
    r"Log In\s*",
    r"Forgot Account\?\s*",
    r"Image \d+:\s*",
    r"Se connecter\s*",
    r"Mot de passe oubli[ée]\s*",
    r"S'inscrire\s*",
]


def clean_scraped_content(text: str) -> str:
    """Retire le bruit connu du contenu scrapé."""
    if not text:
        return text

    cleaned = text
    for pattern in NOISE_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned.strip()


def is_latin_content(text: str) -> bool:
    """Retourne True si le contenu est en alphabet latin (pas CJK/cyrillique/arabe)."""
    if not text:
        return True
    # Si > 5% de caractères non-latins → considérer comme non-latin
    non_latin_count = len(NON_LATIN_REGEX.findall(text))
    return non_latin_count < (len(text) * 0.05)


# Mots entiers uniquement : en sous-chaîne, "war" rejetait "software",
# "spa" rejetait "espace", etc.
_NOISE_REGEX = re.compile(
    r"\b(?:" + "|".join(re.escape(kw) for kw in NOISE_KEYWORDS) + r")\b",
    re.IGNORECASE,
)


def contains_noise(text: str) -> bool:
    """Retourne True si le texte contient des mots-clés bruit (mots entiers)."""
    return bool(_NOISE_REGEX.search(text or ""))


# Contenu enrichi (point E) : texte brut de la page, réduit à un extrait utile
TAVILY_RAW_CONTENT = os.getenv("TAVILY_RAW_CONTENT", "false").lower() == "true"
TAVILY_EXTRAIT_MAX = max(300, int(os.getenv("TAVILY_EXTRAIT_MAX", "1500")))

# Repères qui portent l'information utile d'un avis (échéance, objet, budget)
_REPERES_AVIS = re.compile(
    r"date\s+limite|cl[ôo]ture|d[ée]p[ôo]t\s+des|remise\s+des|deadline|"
    r"appel\s+d'offres?|manifestation\s+d'int[ée]r[êe]t|termes\s+de\s+r[ée]f[ée]rence|"
    r"budget|montant|objet\s*:",
    re.IGNORECASE,
)


# Découpage des pages de liste (ARMP « Avis spécifiques », tableaux dgMarket)
# en avis individuels : le LLM rejetait la page entière comme « liste sans
# annonce précise » alors qu'elle contenait de vrais avis malgaches.
TAVILY_AVIS_MAX_PAR_PAGE = max(1, int(os.getenv("TAVILY_AVIS_MAX_PAR_PAGE", "10")))

# Début d'un avis : "| ORGANISME EN MAJUSCULES ----- Ref:" (ARMP)
# ou "| Nov 28, 2024 |" (ligne datée d'un tableau dgMarket)
_DEBUT_AVIS = re.compile(
    r"\|\s*(?=[A-ZÀ-Ý][A-ZÀ-Ý'’ ,.&()\-]{5,}?\s*-{3,}\s*R[ée]f\s*:)"
    r"|\|\s*(?=[A-Z][a-z]{2,8}\.?\s+\d{1,2},\s+\d{4}\s*\|)",
)
_ANNEE = re.compile(r"\b(20\d{2})\b")

# Ancienneté maximale d'un avis daté (date de publication en tête de ligne
# dgMarket). 0 = pas de limite. Les avis sans date gardent le filtre par année.
VEILLE_AGE_MAX_JOURS = max(0, int(os.getenv("VEILLE_AGE_MAX_JOURS", "14")))
_DATE_TETE = re.compile(r"^([A-Za-zÀ-ÿ]{3,9})\.?\s+(\d{1,2}),\s+(\d{4})")
_MOIS = {
    "jan": 1, "fev": 2, "fév": 2, "feb": 2, "mar": 3, "avr": 4, "apr": 4,
    "mai": 5, "may": 5, "jun": 6, "jui": 6, "jul": 7, "aou": 8, "aoû": 8,
    "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12, "déc": 12,
}


def date_publication(segment: str) -> datetime_date | None:
    """Date en tête d'un avis ("Mar 26, 2026", "Aou 13, 2026", "Juil 2, 2026")."""
    m = _DATE_TETE.match(segment)
    if not m:
        return None
    mot = m.group(1).lower()
    mois = 7 if mot.startswith("juil") else _MOIS.get(mot[:3])
    if not mois:
        return None
    try:
        return datetime_date(int(m.group(3)), mois, int(m.group(2)))
    except ValueError:
        return None


def decouper_liste_avis(
    title: str,
    url: str,
    raw: str | None,
    annee_courante: int | None = None,
    maximum: int = TAVILY_EXTRAIT_MAX,
    aujourd_hui: datetime_date | None = None,
) -> list[dict[str, Any]] | None:
    """
    Si `raw` est une page de liste (≥ 2 débuts d'avis reconnus), retourne un
    résultat par avis encore d'actualité ; sinon None (page traitée telle quelle).

    L'ancienneté est un critère de classement, pas une preuve d'expiration.
    Une date de tableau n'est appelée publication que si son en-tête le dit.
    """
    texte = " ".join((raw or "").split())
    debuts = [m.start() for m in _DEBUT_AVIS.finditer(texte)]
    if len(debuts) < 2:
        return None

    aujourd_hui = aujourd_hui or datetime_date.today()
    annee_courante = annee_courante or aujourd_hui.year
    avis: list[dict[str, Any]] = []
    for numero, (debut, fin) in enumerate(zip(debuts, debuts[1:] + [len(texte)]), start=1):
        segment = texte[debut:fin].strip(" |")
        publie_le = date_publication(segment)
        outside_window = False
        if publie_le is not None:
            if VEILLE_AGE_MAX_JOURS and (aujourd_hui - publie_le).days > VEILLE_AGE_MAX_JOURS:
                outside_window = True
        else:
            annees = [int(a) for a in _ANNEE.findall(segment)]
            if annees and max(annees) < annee_courante:
                outside_window = True
        intitule = " ".join(p.strip() for p in segment.split("|") if p.strip())
        # Le tableau contient souvent le lien de l'avis. Le conserver évite
        # d'envoyer une page générale et son pied de page au lieu de l'annonce.
        lien = re.search(r"\[([^\]]+)\]\(([^\s)]+)\)", segment)
        notice_url = urljoin(url, lien.group(2)) if lien else f"{url}#avis-{numero}"
        if urlparse(notice_url).scheme not in {"http", "https"}:
            notice_url = f"{url}#avis-{numero}"
        avis.append({
            "title": lien.group(1) if lien else f"{title} — {intitule[:120]}",
            "url": notice_url,
            "listing_url": url,
            "published_at": publie_le.isoformat() if publie_le and publie_le <= aujourd_hui and re.search(r"publi|published", texte[:debuts[0]], re.IGNORECASE) else None,
            "observed_table_date": publie_le.isoformat() if publie_le else None,
            "outside_publication_window": outside_window,
            "content": segment[:maximum],
            "score": 0.0,
        })
    avis.sort(key=lambda item: item["outside_publication_window"])
    return avis[:TAVILY_AVIS_MAX_PAR_PAGE]


def extrait_utile(snippet: str, raw: str | None, maximum: int = TAVILY_EXTRAIT_MAX) -> str:
    """
    Snippet Tavily + fenêtre du texte brut autour du premier repère d'avis
    (sinon le début du texte brut). Jamais plus de `maximum` caractères.
    """
    snippet = (snippet or "").strip()
    raw = " ".join((raw or "").split())
    if not raw:
        return snippet[:maximum]

    reste = maximum - len(snippet) - 5
    if reste <= 100:
        return snippet[:maximum]

    match = _REPERES_AVIS.search(raw)
    debut = max(0, match.start() - reste // 4) if match else 0
    fenetre = raw[debut:debut + reste]
    if not snippet:
        return fenetre[:maximum]
    return f"{snippet}\n[…] {fenetre}"[:maximum]


def is_trusted_url(url: str) -> bool:
    """Retourne True si l'URL vient d'un domaine autorisé."""
    hostname = (urlparse(url).hostname or "").lower().rstrip(".")
    return any(hostname == domain or hostname.endswith(f".{domain}") for domain in TRUSTED_DOMAINS)


class TavilySearchError(RuntimeError):
    """Recherche non aboutie : distincte d'une recherche sans résultat."""


class TavilyService:
    """Recherche web via Tavily avec filtrage robuste + cache simple."""

    # Cache en mémoire pour éviter conflits (TTL 5 min)
    _cache: dict[str, tuple] = {}
    _cache_ttl = 300  # 5 minutes

    def __init__(self):
        self.registry = load_registry()
        if TAVILY_API_KEY:
            logger.info("🔎 TAVILY configuré (V3.0 - filtrage robuste)")
        else:
            logger.warning("⚠️ TAVILY_API_KEY absente")

    def _cache_key(self, query: str) -> str:
        """Génère une clé de cache pour une query."""
        registry = getattr(self, "registry", None)
        config = registry.model_dump_json() if registry else ""
        key = f"{SEARCH_GROUP.get()}:{config}:{query.lower().strip()}"
        return hashlib.sha256(key.encode()).hexdigest()

    def _get_from_cache(self, query: str) -> list[dict[str, Any]] | None:
        """Récupère depuis le cache si non expiré."""
        key = self._cache_key(query)
        if key in self._cache:
            data, timestamp = self._cache[key]
            if time.time() - timestamp < self._cache_ttl:
                logger.info("💾 Cache HIT pour: %s", query[:60])
                return deepcopy(data)
            else:
                del self._cache[key]
        return None

    def _set_cache(self, query: str, results: list[dict[str, Any]]) -> None:
        """Stocke dans le cache."""
        key = self._cache_key(query)
        self._cache[key] = (deepcopy(results), time.time())

    async def _do_request(
        self, payload: dict[str, Any], categorie: str = "manuel",
    ) -> httpx.Response:
        """Un seul essai HTTP — rejouable par retry_with_backoff. Compte
        CET appel (échec/retry compris) — jamais appelé sur un cache hit,
        donc jamais de sur-comptage (correction Étape B)."""
        if categorie in {"manuel", "collecte"} and tavily_quota_service.plafond_dur_atteint():
            raise QuotaTavilyDepasseError("Plafond Tavily atteint avant une nouvelle tentative HTTP.")
        tavily_quota_service.enregistrer_appel(categorie)
        group = self.registry.group(SEARCH_GROUP.get())
        started = time.perf_counter()
        await emit_progress("analyse", "web_search", f"Recherche web — {group.id} : interrogation des sources configurées.", family=group.id)
        record = {"domains": payload.get("include_domains", []), "status": "pending"}
        trace = _SEARCH_TRACE.get()
        if trace is not None:
            trace.append(record)
        try:
            timeout = group.request_timeout_seconds or TAVILY_TIMEOUT
            async with httpx.AsyncClient(timeout=timeout) as client:
                # httpx borne chaque phase ; ce plafond borne aussi l'appel entier.
                async with asyncio.timeout(timeout):
                    response = await client.post("https://api.tavily.com/search", json=payload)
                record.update(status="response", http_status=response.status_code)
                if response.status_code == 200:
                    data = response.json()
                    record.update(response_time=data.get("response_time"), request_id=data.get("request_id"),
                                  raw_results=len(data.get("results", [])))
                if response.status_code >= 500:
                    response.raise_for_status()
                return response
        except asyncio.CancelledError:
            record["status"] = "budget_exceeded"
            raise
        except TimeoutError as exc:
            record.update(status="failed", reason="request_timeout")
            raise httpx.ReadTimeout("Budget de la tentative Tavily dépassé") from exc
        except httpx.HTTPError as exc:
            record.update(status="failed", reason=type(exc).__name__)
            raise
        finally:
            record["elapsed_seconds"] = round(time.perf_counter() - started, 3)

    async def search(
        self, query: str, categorie: str = "manuel",
    ) -> list[dict[str, Any]]:
        budget = self.registry.group(SEARCH_GROUP.get()).search_budget_seconds or TAVILY_SEARCH_BUDGET_S
        attempts = []
        token = _SEARCH_TRACE.set(attempts)
        coverage = []
        started = time.perf_counter()
        try:
            try:
                async with asyncio.timeout(budget):
                    items = await self._search(query, categorie)
                    if isinstance(items, SearchResults):
                        cached = deepcopy(items)
                        cached.diagnostics["cache_hit"] = True
                        return cached
                    # Un moteur multi-domaines ne garantit pas un résultat par site.
                    if SEARCH_GROUP.get() == "missions_privees":
                        domains = self.registry.domains("missions_privees")
                        covered = {d for d in domains if any(domain_matches(
                            urlparse(item.get("url", "")).hostname or "", d) for item in items)}
                        coverage.extend({"domain": d, "status": "indexed_results"} for d in domains if d in covered)
                        semaphore = asyncio.Semaphore(2)
                        quota_stop = asyncio.Event()
                        async def search_site(domain):
                            async with semaphore:
                                remaining = budget - (time.perf_counter() - started)
                                if remaining < 3 or quota_stop.is_set():
                                    return [], {"domain": domain, "status": "not_searched", "reason": "quota" if quota_stop.is_set() else "time_budget"}
                                payload = {"api_key": TAVILY_API_KEY, "query": "formation informatique formateur Madagascar",
                                           "search_depth": "basic", "max_results": 4, "include_domains": [domain],
                                           "exclude_domains": self.registry.excluded_domains, "include_raw_content": False,
                                           "include_answer": False, "include_published_date": True}
                                try:
                                    async with asyncio.timeout(min(10, max(0.1, remaining - 0.5))):
                                        response = await self._do_request(payload, categorie)
                                    if response.status_code in {429, 432, 433}:
                                        quota_stop.set()
                                        return [], {"domain": domain, "status": "quota_atteint"}
                                    if response.status_code != 200:
                                        return [], {"domain": domain, "status": "failed", "http_status": response.status_code}
                                    found = [item for item in self._filter_results(response.json().get("results", []))
                                             if domain_matches(urlparse(item.get("url", "")).hostname or "", domain)]
                                    for item in found:
                                        item["search_strategy"] = "family_site_fallback"
                                    return found, {"domain": domain, "status": "indexed_results" if found else "no_indexed_result"}
                                except (httpx.HTTPError, TimeoutError, ValueError) as exc:
                                    return [], {"domain": domain, "status": "failed", "reason": type(exc).__name__}
                        for found, record in await asyncio.gather(*(search_site(d) for d in domains if d not in covered)):
                            items.extend(found)
                            coverage.append(record)
                        if quota_stop.is_set():
                            raise QuotaTavilyDepasseError("Quota Tavily atteint pendant le repli par site.")
            except TimeoutError as exc:
                error = TavilySearchError(f"Tavily a dépassé le budget de {budget:g} secondes.")
                error.diagnostics = {"attempts": attempts, "domain_coverage": coverage}
                raise error from exc
            if not coverage:
                coverage = [{"domain": domain, "status": "indexed_results" if any(domain_matches(
                    urlparse(item.get("url", "")).hostname or "", domain) for item in items)
                    else "no_indexed_result_in_group_search"}
                    for domain in self.registry.domains(SEARCH_GROUP.get() or self.registry.groups[0].id)]
            resolver = NoticeResolver(self.registry)
            items = await resolver.resolve(items, query)
            result = SearchResults(deduplicate_notices(items), {
                "attempts": attempts, "domain_coverage": coverage, "notice_resolution": resolver.diagnostics,
                "api_results_received": sum(attempt.get("raw_results", 0) for attempt in attempts),
                "search_budget_seconds": budget, "resolution_budget_seconds": 14, "cache_hit": False})
            self._set_cache(query, result)
            return result
        except TavilySearchError as exc:
            if not hasattr(exc, "diagnostics"):
                exc.diagnostics = {"attempts": attempts, "domain_coverage": coverage}
            raise
        finally:
            _SEARCH_TRACE.reset(token)

    async def _search(
        self, query: str, categorie: str = "manuel",
    ) -> list[dict[str, Any]]:
        """
        Recherche Tavily avec filtrage multi-niveaux :
        1. Vérifie le cache
        2. Envoie la requête avec site: operators
        3. Filtre les résultats (URL, langue, bruit)
        4. Si 0 résultats, retente SANS site: (fallback)
        5. Filtre à nouveau le fallback
        6. Stocke dans le cache

        `categorie` : "auto" | "manuel" | "collecte" — ventile le comptage
        de quota (voir tavily_quota_service). "manuel" par défaut, pour
        ne rien changer aux appelants existants.
        """

        if not TAVILY_API_KEY:
            raise TavilySearchError("Tavily n'est pas configuré.")

        query = str(query or "").strip()
        if not query:
            return []

        # ✅ 1. Vérifier le cache
        cached = self._get_from_cache(query)
        if cached is not None:
            return cached

        # ✅ Quota — mode auto protégé EN AMONT (verifier_quota_auto,
        # une fois par passage, dans auto_detection_service.executer_detection),
        # jamais bloqué ici. Mode manuel/collecte : bloqué au plafond dur,
        # AVANT tout appel HTTP (correction Étape B).
        if categorie in ("manuel", "collecte") and tavily_quota_service.plafond_dur_atteint():
            cfg = tavily_quota_service.config()
            total = tavily_quota_service.consommation()
            raise QuotaTavilyDepasseError(
                f"Quota Tavily épuisé : {total}/{cfg['plafond_dur']} appels ce mois "
                f"(plafond dur). Réessayez le mois prochain, ou augmentez "
                f"TAVILY_QUOTA_PLAFOND_DUR dans .env."
            )

        # ✅ 2. Construire la query avec site: operators
        base_query = query
        for word in ["Madagascar", "madagascar", "Antananarivo", "antananarivo"]:
            base_query = base_query.replace(word, "")
        base_query = base_query.strip()

        # Sites prioritaires (les premiers seulement pour éviter query trop longue)
        registry = self.registry
        group = registry.group(SEARCH_GROUP.get())
        raw_content = TAVILY_RAW_CONTENT if group.include_raw_content is None else group.include_raw_content
        priority_sites = registry.domains(group.id)
        if len(priority_sites) > TAVILY_SITES_MAX:
            raise TavilySearchError("Famille trop large : répartir les domaines en familles plus petites ou augmenter TAVILY_SITES_MAX.")
        if not priority_sites:
            raise TavilySearchError(f"Aucune source active dans la famille {group.id}.")
        site_operators = " OR ".join([f"site:{s}" for s in priority_sites])
        enhanced_query = f"{base_query} Madagascar {group.query_hint} ({site_operators})"

        logger.info("🌐 Tavily query (with sites): %s", enhanced_query[:150])

        payload = {
            "api_key": TAVILY_API_KEY,
            "query": enhanced_query,
            "search_depth": "basic",  # Basic = rapide ; advanced = 10-28s
            "max_results": MAX_RESULTS_TAVILY,
            "include_raw_content": raw_content,
            "include_images": False,
            "include_answer": False,
            "exclude_domains": registry.excluded_domains,
            "include_domains": priority_sites,
            "include_published_date": True,
        }

        start = time.perf_counter()

        try:
            response = await retry_with_backoff(
                self._do_request,
                payload,
                categorie,
                max_retries=min(2, RETRY_MAX_ATTEMPTS),
                base_delay=RETRY_BASE_DELAY,
                retryable_exceptions=(httpx.HTTPStatusError,),
                label="Tavily",
            )
            if response.status_code in {429, 432, 433}:
                raise QuotaTavilyDepasseError("Quota ou limite de débit Tavily atteint.")
            if response.status_code in {401, 403}:
                raise TavilySearchError("Authentification Tavily refusée ; vérifier la configuration serveur.")

            elapsed = time.perf_counter() - start
            logger.info("⏱️ Tavily (with sites) : %.3fs", elapsed)

            if response.status_code == 200:
                data = response.json()
                raw_results = data.get("results", [])
                filtered = self._filter_results(raw_results)

                logger.info(
                    "📊 Tavily (with sites): %d bruts → %d après filtrage",
                    len(raw_results), len(filtered)
                )

                if filtered:
                    for item in filtered:
                        item["search_strategy"] = "family"
                    self._set_cache(query, filtered)
                    return filtered
            else:
                logger.warning(
                    "⚠️ Tavily HTTP %s sur requête avec sites",
                    response.status_code
                )

        except (httpx.TimeoutException, httpx.HTTPError, ValueError) as exc:
            logger.warning("⚠️ Tavily (with sites) échoué: %s", exc)

        # ✅ 3. FALLBACK : Retenter SANS site: operators
        logger.info("🔄 Fallback Tavily : retenter sans site: operators")

        fallback_query = f"{base_query} Madagascar"
        fallback_payload = {
            "api_key": TAVILY_API_KEY,
            "query": fallback_query,
            "search_depth": "basic",
            "max_results": MAX_RESULTS_TAVILY,
            "include_raw_content": False,
            "include_images": False,
            "include_answer": False,
            "exclude_domains": registry.excluded_domains,
            "include_published_date": True,
            "include_domains": priority_sites,
        }

        start = time.perf_counter()

        try:
            response = await retry_with_backoff(
                self._do_request,
                fallback_payload,
                categorie,
                max_retries=1,
                base_delay=RETRY_BASE_DELAY,
                retryable_exceptions=(httpx.TimeoutException, httpx.HTTPError),
                label="Tavily-Fallback",
            )

            elapsed = time.perf_counter() - start
            logger.info("⏱️ Tavily (fallback) : %.3fs", elapsed)

            if response.status_code in {429, 432, 433}:
                raise QuotaTavilyDepasseError("Quota ou limite de débit Tavily atteint.")
            if response.status_code != 200:
                raise TavilySearchError(
                    f"Tavily a répondu HTTP {response.status_code} après le repli."
                )

            data = response.json()
            raw_results = data.get("results", [])
            filtered = self._filter_results(raw_results)

            logger.info(
                "📊 Tavily (fallback): %d bruts → %d après filtrage",
                len(raw_results), len(filtered)
            )

            # ✅ Si fallback retourne résultats, on accepte MÊME si domaines non-autorisés
            # (car Tavily peut ne pas avoir les sites malgaches indexés)
            if filtered:
                for item in filtered:
                    item["search_strategy"] = "family_fallback"
                self._set_cache(query, filtered)
                return filtered

            # ✅ Si vraiment 0, on garde quelques résultats bruts "propres"
            # (utile pour montrer au LLM qu'il n'y a rien)
            clean_raw = self._filter_minimal(raw_results)
            for item in clean_raw:
                item["search_strategy"] = "family_fallback"
            self._set_cache(query, clean_raw)
            return clean_raw

        except (TavilySearchError, QuotaTavilyDepasseError):
            raise
        except (httpx.TimeoutException, httpx.HTTPError, ValueError) as exc:
            logger.error("❌ Tavily fallback échoué: %s", exc)
            raise TavilySearchError("Tavily est indisponible ou le délai est dépassé.") from exc
        except Exception as exc:
            logger.exception("❌ Tavily : %s", exc)
            raise TavilySearchError("Tavily a retourné une réponse inexploitable.") from exc

    def _filter_results(
        self, raw_results: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Filtrage STRICT :
        - URL doit venir d'un domaine autorisé
        - Contenu doit être latin
        - Pas de mots-clés bruit
        """
        filtered = []

        for result in raw_results:
            if not isinstance(result, dict):
                continue

            title = " ".join(str(result.get("title", "")).split())
            url = str(result.get("url", "")).strip()
            content = str(
                result.get("content", "") or result.get("snippet", "")
            ).strip()

            # Filtre 1 : URL autorisée
            registry = getattr(self, "registry", None) or load_registry()
            hostname = (urlparse(url).hostname or "").lower()
            if not registry.allowed_url(url) or not any(domain_matches(hostname, d) for d in registry.domains()):
                logger.debug("   🚫 URL non autorisée: %s", url[:80])
                continue

            # Filtre 2 : Contenu latin
            if not is_latin_content(title + " " + content):
                logger.debug("   🚫 Contenu non-latin: %s", title[:60])
                continue

            # Filtre 3 : Pas de bruit
            if contains_noise(title + " " + content) or self._configured_noise(title + " " + content):
                logger.debug("   🚫 Bruit détecté: %s", title[:60])
                continue

            filtered.extend(self._resultats_page(result, title, url, content))

        return filtered

    @staticmethod
    def _resultats_page(
        result: dict[str, Any], title: str, url: str, content: str,
    ) -> list[dict[str, Any]]:
        """Page de liste → un résultat par avis récent ; sinon la page seule."""
        url = normalize_url(url)
        captured_at = datetime.now(UTC).isoformat()
        registry = load_registry()
        host = (urlparse(url).hostname or "").lower()
        source = next((s for g in registry.groups for s in g.sources if s.enabled
                       and any(domain_matches(host, d) for d in s.domains)), None)
        metadata = {
            "source_registered": source is not None,
            "source_preferred": bool(source and any(urlparse(url).path.lower().startswith(p.lower()) for p in source.preferred_paths)),
            "employment_signal": any(re.search(r"\b" + re.escape(w) + r"\b", title + " " + content, re.IGNORECASE)
                                     for w in registry.employment_keywords),
        }
        avis = decouper_liste_avis(title, url, result.get("raw_content"))
        if avis is not None:
            logger.info(
                "   ✂️ Liste découpée : %s → %d avis récent(s)", title[:60], len(avis)
            )
            for item in avis:
                item["content"] = clean_scraped_content(item["content"])
                item["captured_at"] = captured_at
                item["search_group"] = SEARCH_GROUP.get() or "institutionnel"
                item.update(metadata)
            return avis
        return [{
            "title": title,
            "url": url,
            "content": clean_scraped_content(
                extrait_utile(content, result.get("raw_content"))
            ),
            "score": result.get("score", 0.0),
            "published_at": result.get("published_at") or result.get("published_date"),
            "captured_at": captured_at,
            "search_group": SEARCH_GROUP.get() or "institutionnel",
            **metadata,
        }]

    def _configured_noise(self, text):
        registry = getattr(self, "registry", None) or load_registry()
        return any(re.search(r"\b" + re.escape(word) + r"\b", text, re.IGNORECASE)
                   for word in registry.rejected_keywords)

    def _filter_minimal(
        self, raw_results: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Filtrage MINIMAL (utilisé en dernier recours) :
        - Rejette uniquement non-latin + bruit
        - Accepte TOUTES les URLs (même non-autorisées)
        """
        filtered = []

        for result in raw_results:
            if not isinstance(result, dict):
                continue

            title = " ".join(str(result.get("title", "")).split())
            url = str(result.get("url", "")).strip()
            content = str(
                result.get("content", "") or result.get("snippet", "")
            ).strip()

            registry = getattr(self, "registry", None) or load_registry()
            if not registry.allowed_url(url):
                continue

            if not is_latin_content(title + " " + content):
                continue

            if contains_noise(title + " " + content) or self._configured_noise(title + " " + content):
                continue

            filtered.extend(self._resultats_page(result, title, url, content))

        return filtered
