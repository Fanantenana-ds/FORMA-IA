"""Lecture bornée d'avis publics ; les pages et extraits restent des données."""
import asyncio
import re
from datetime import UTC, datetime
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import httpx
from lxml import html

from app.services.veille.prefilter_service import _TECH_TITLE
from app.services.veille.source_registry import domain_matches
from app.services.veille.progress_service import emit_progress

_NEED = re.compile(r"formation|formateur|consultant|prestataire|appel|recrutement", re.IGNORECASE)


def is_listing(url):
    path = urlparse(str(url)).path.lower().rstrip("/")
    return path in {"", "/appels-doffres", "/appels-a-manifestations-dinterets"} or any(
        token in path for token in ("/category/", "adminshowbuyer", "list.do"))


def canonical_url(url):
    parsed = urlparse(str(url))
    query = urlencode([(k, v) for k, v in parse_qsl(parsed.query)
                       if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}])
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower().removeprefix("www."),
                       parsed.path.rstrip("/"), "", query, parsed.fragment))


def deduplicate_notices(sources):
    """Même URL ou même référence chez un même éditeur ; jamais domaine seul."""
    unique, seen = [], set()
    for source in sorted(sources, key=lambda s: (is_listing(s.get("url")), -len(s.get("content") or ""))):
        url = canonical_url(source.get("url"))
        text = str(source.get("content") or "")
        reference = re.search(r"(?:N[°º]|Réf(?:érence)?\s*:)\s*([\w][\w./_-]{7,})", text, re.IGNORECASE)
        host = (urlparse(url).hostname or "").removeprefix("www.")
        keys = ["url:" + url]
        if reference and not is_listing(url):
            keys.append("ref:" + host + ":" + reference.group(1).casefold())
        if any(key in seen for key in keys):
            continue
        seen.update(keys)
        unique.append(source)
    return unique


def parse_notice_page(document, url):
    tree = html.fromstring(document, parser=html.HTMLParser(no_network=True, recover=True))
    for node in tree.xpath("//script|//style|//nav|//footer|//aside|//header[not(ancestor::article)]"):
        node.drop_tree()
    for node in tree.xpath("//*[contains(@class, 'related') or contains(@class, 'entry-footer')]"):
        node.drop_tree()
    root = (tree.xpath("//article//h1/ancestor::article[1]|//main|//*[@class='entry-content']") or [tree])[0]
    headings = root.xpath(".//h1") or tree.xpath("//h1")
    title = " ".join(headings[0].itertext()).strip() if headings else ""
    text = " ".join(" ".join(root.itertext()).split())
    text = re.split(r"ARTICLES? SIMILAIRES\s*:", text, flags=re.IGNORECASE)[0]
    links = []
    for node in root.xpath(".//a[@href]"):
        label = " ".join(node.itertext()).strip()
        target = urljoin(url, node.get("href"))
        if (_NEED.search(label) and _TECH_TITLE.search(label) and not is_listing(target)
                and not re.search(r"\.(pdf|docx?|xlsx?)(?:$|\?)", target, re.IGNORECASE)):
            links.append({"title": label, "url": target})
    published = tree.xpath("//meta[@property='article:published_time']/@content|//time[@datetime]/@datetime")
    return {"title": title, "content": text[:14000], "links": links,
            "published_at": published[0] if published else None}


class NoticeResolver:
    """Au plus deux listes et deux avis, 14 s au total ; aucun appel Groq."""
    def __init__(self, registry):
        self.registry = registry
        self.diagnostics = []

    def allowed(self, url):
        host = (urlparse(str(url)).hostname or "").lower()
        # Les plateformes privées restent consultées via leur index public.
        return self.registry.allowed_url(url) and any(
            domain_matches(host, d) for group in self.registry.groups
            if group.id in {"institutionnel", "international", "decouverte"}
            for source in group.sources if source.enabled for d in source.domains)

    async def _fetch(self, url):
        await emit_progress("analyse", "source_reading", "Lecture et vérification d'une page publique.", source_url=url)
        async with httpx.AsyncClient(timeout=6, follow_redirects=False) as client:
            for _ in range(3):
                if not self.allowed(url):
                    raise ValueError("Lien de détail hors des sources publiques autorisées")
                async with client.stream("GET", url, headers={"User-Agent": "FORMA-IA/1.0 market-monitor"}) as response:
                    if response.is_redirect:
                        url = urljoin(url, response.headers["location"])
                        continue
                    response.raise_for_status()
                    if "html" not in response.headers.get("content-type", "").lower():
                        raise ValueError("Avis non HTML : vérification documentaire nécessaire")
                    content = bytearray()
                    async for chunk in response.aiter_bytes():
                        content.extend(chunk)
                        if len(content) > 1_200_000:
                            raise ValueError("Page trop volumineuse pour la lecture bornée")
                    return parse_notice_page(bytes(content), url), url
        raise ValueError("Trop de redirections")

    async def resolve(self, sources, query=""):
        additions, visited, detail_count = [], set(), 0
        terms = set(re.findall(r"\w{4,}", query.casefold())) - {"madagascar", "appel", "offres", "formation"}
        async def read_detail(target, source, listing_url=None):
            nonlocal detail_count
            if detail_count >= 2 or target in visited or not self.allowed(target):
                return
            visited.add(target)
            detail_count += 1
            try:
                detail, final = await self._fetch(target)
                if len(detail["content"]) < 100 or not _TECH_TITLE.search(detail["title"]):
                    raise ValueError("Contenu principal sans annonce informatique identifiable")
                checked = datetime.now(UTC).isoformat()
                additions.append({**source, "title": detail["title"], "url": final,
                                  "content": detail["content"], "listing_url": listing_url,
                                  "published_at": detail["published_at"] or source.get("published_at"),
                                  "captured_at": checked, "last_verified_at": checked,
                                  "verification_method": "direct_public_page"})
                self.diagnostics.append({"url": final, "status": "verified_content"})
            except (httpx.HTTPError, ValueError) as exc:
                self.diagnostics.append({"url": target, "status": "failed", "reason": type(exc).__name__})
        try:
            async with asyncio.timeout(14):
                direct = [s for s in sources if not is_listing(s.get("url")) and self.allowed(s.get("url"))
                          and _TECH_TITLE.search(s.get("title", "")) and _NEED.search(s.get("title", ""))
                          and not re.search(r"\.(pdf|docx?|xlsx?)(?:$|\?)", s.get("url", ""), re.IGNORECASE)]
                direct.sort(key=lambda s: -sum(word in s.get("title", "").casefold() for word in terms))
                listings = sorted([s for s in sources if is_listing(s.get("url")) and self.allowed(s.get("url"))],
                                  key=lambda s: (bool(urlparse(s["url"]).query), "/category/" in s["url"]))[:2]
                # Un ancien avis vaguement proche ne doit pas masquer l'index
                # courant. Un détail fortement lié à la requête reste prioritaire.
                prefer_current = bool(listings and not urlparse(listings[0]["url"]).query and (
                    not direct or sum(word in direct[0].get("title", "").casefold() for word in terms) < 2))
                if not prefer_current:
                    for source in direct[:2]:
                        await read_detail(source["url"], source)
                for source in listings:
                    if additions or detail_count >= 2:
                        break
                    url = source["url"]
                    try:
                        page, final_url = await self._fetch(url)
                        self.diagnostics.append({"url": url, "status": "read", "links_found": len(page["links"])})
                    except (httpx.HTTPError, ValueError) as exc:
                        self.diagnostics.append({"url": url, "status": "failed", "reason": type(exc).__name__})
                        continue
                    for link in sorted(page["links"], key=lambda link: -sum(word in link["title"].casefold() for word in terms)):
                        target = link["url"]
                        await read_detail(target, source, final_url)
                    if additions or detail_count >= 2:
                        break
                if not additions:
                    for source in direct[:2]:
                        await read_detail(source["url"], source)
        except TimeoutError:
            self.diagnostics.append({"status": "timeout", "budget_seconds": 14})
        return deduplicate_notices(additions + sources)
