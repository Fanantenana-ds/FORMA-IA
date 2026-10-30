"""Configuration des recherches réelles M1 ; aucun lien avec DEMO_MODE."""
import os
import re
from contextvars import ContextVar
from pathlib import Path
from urllib.parse import urlparse

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

REGISTRY_PATH = Path(__file__).resolve().parents[2] / "config" / "veille_sources.yaml"
SEARCH_GROUP = ContextVar("m1_search_group", default=None)


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    domains: list[str] = Field(min_length=1)
    enabled: bool = True
    preferred_paths: list[str] = Field(default_factory=list)
    excluded_paths: list[str] = Field(default_factory=list)

    @field_validator("domains")
    @classmethod
    def valid_domains(cls, values):
        if any(not re.fullmatch(r"[a-z0-9]+(?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,}", v) for v in values):
            raise ValueError("Utiliser des domaines seuls, sans URL ni opérateur site:.")
        return values


class SourceGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    query_hint: str
    include_raw_content: bool | None = None
    search_budget_seconds: float | None = Field(default=None, gt=0, le=60)
    request_timeout_seconds: float | None = Field(default=None, gt=0, le=60)
    sources: list[Source] = Field(min_length=1)


class SourceRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int
    groups: list[SourceGroup] = Field(min_length=1)
    excluded_domains: list[str]
    rejected_keywords: list[str]
    employment_keywords: list[str]

    def group(self, name=None):
        name = name or self.groups[0].id
        for group in self.groups:
            if group.id == name:
                return group
        raise ValueError(f"Famille M1 inconnue : {name}")

    def domains(self, group=None):
        groups = [self.group(group)] if group else self.groups
        return list(dict.fromkeys(d for g in groups for s in g.sources if s.enabled for d in s.domains))

    def allowed_url(self, url):
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme not in {"http", "https"} or not host:
            return False
        if any(domain_matches(host, d) for d in self.excluded_domains):
            return False
        for group in self.groups:
            for source in group.sources:
                if any(domain_matches(host, d) for d in source.domains):
                    if not source.enabled or any(parsed.path.lower().startswith(p.lower()) for p in source.excluded_paths):
                        return False
        return True


def domain_matches(host, domain):
    return host == domain or host.endswith("." + domain)


def csv_env(name):
    return [v.strip().lower() for v in os.getenv(name, "").split(",") if v.strip()]


def load_registry(path=None):
    data = yaml.safe_load(Path(path or REGISTRY_PATH).read_text(encoding="utf-8"))
    registry = SourceRegistry.model_validate(data)
    if registry.version != 1:
        raise ValueError("Version de registre M1 non supportée.")
    ids = [g.id for g in registry.groups]
    if len(set(ids)) != len(ids) or not registry.domains():
        raise ValueError("Registre M1 : familles dupliquées ou toutes les sources désactivées.")
    # Les réglages historiques complètent le registre, ils ne masquent plus
    # les sources officielles (FID notamment) en remplaçant toute la liste.
    extra = csv_env("TAVILY_INCLUDE_DOMAINS")
    known = registry.domains()
    extra = [d for d in extra if d not in known and not any(
        d in s.domains for g in registry.groups for s in g.sources)]
    if extra:
        registry.groups[-1].sources.append(Source(id="env_extra", domains=extra))
    registry.excluded_domains = list(dict.fromkeys(registry.excluded_domains + csv_env("TAVILY_EXCLUDE_DOMAINS")))
    # Un organisme acheteur ne doit pas être exclu en tant que mot-clé.
    protected = {"unicef", "undp", "pnud", "fid", "afd", "oit", "ilo"}
    registry.rejected_keywords = [v for v in dict.fromkeys(
        registry.rejected_keywords + csv_env("TAVILY_REJECTED_KEYWORDS")) if v not in protected]
    registry.employment_keywords = list(dict.fromkeys(
        registry.employment_keywords + csv_env("TAVILY_JOB_KEYWORDS")))
    return registry
