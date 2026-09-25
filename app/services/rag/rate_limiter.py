# app/services/rag/rate_limiter.py
# ============================================================
# LIMITEUR DE DÉBIT — RPM + TPM (partagé par tout le module RAG)
# ============================================================
# Horloge et sommeil injectables : aucun test ne doit dépendre d'une
# vraie attente (voir consigne "HORLOGE SIMULÉE pour toute attente").
# ============================================================

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Deque, Optional, Tuple

FENETRE_S = 60.0


class DelaiDepasseError(Exception):
    """
    Levée quand l'attente nécessaire dépasse l'attente maximale autorisée
    (mode chat : jamais plus de 5 s, voir attendre_puis_consommer()).
    """

    def __init__(self, temps_restant_s: float):
        self.temps_restant_s = temps_restant_s
        super().__init__(
            f"Limite de débit Voyage atteinte, réessayez dans "
            f"{temps_restant_s:.0f} s"
        )


@dataclass
class LimiteurDebit:
    """
    Limiteur RPM (appels) + TPM (tokens) sur une fenêtre glissante de 60 s.

    Une seule instance doit être partagée par tout le module RAG (voir
    get_limiteur_partage() dans embedding_provider.py).
    """

    rpm: int
    tpm: int
    horloge: Callable[[], float] = time.monotonic
    _appels: Deque[float] = field(default_factory=deque, init=False, repr=False)
    _tokens: Deque[Tuple[float, int]] = field(default_factory=deque, init=False, repr=False)

    def _purger(self, maintenant: float) -> None:
        limite = maintenant - FENETRE_S
        while self._appels and self._appels[0] <= limite:
            self._appels.popleft()
        while self._tokens and self._tokens[0][0] <= limite:
            self._tokens.popleft()

    def temps_attente(self, tokens_a_envoyer: int) -> float:
        """Temps (s) à attendre avant de pouvoir envoyer, 0 si immédiat."""
        maintenant = self.horloge()
        self._purger(maintenant)

        attente = 0.0

        if len(self._appels) >= self.rpm:
            attente = max(attente, FENETRE_S - (maintenant - self._appels[0]))

        total_tokens = sum(tok for _, tok in self._tokens)
        if total_tokens + tokens_a_envoyer > self.tpm:
            a_liberer = total_tokens + tokens_a_envoyer - self.tpm
            libere = 0
            for horodatage, tok in self._tokens:
                libere += tok
                if libere >= a_liberer:
                    attente = max(attente, FENETRE_S - (maintenant - horodatage))
                    break

        return max(0.0, attente)

    def enregistrer_appel(self, tokens_envoyes: int) -> None:
        maintenant = self.horloge()
        self._purger(maintenant)
        self._appels.append(maintenant)
        self._tokens.append((maintenant, tokens_envoyes))

    async def attendre_puis_consommer(
        self,
        tokens_a_envoyer: int,
        *,
        attente_max_s: Optional[float] = None,
        dormir: Callable[[float], "asyncio.Future"] = asyncio.sleep,
        sur_attente: Optional[Callable[[float], None]] = None,
    ) -> None:
        """
        Attend le temps nécessaire puis enregistre l'appel.

        attente_max_s=None (indexation) : attend le temps qu'il faut ;
        sur_attente(temps_restant) est appelé une fois avant l'attente,
        pour afficher une progression.

        attente_max_s=5.0 (chat) : lève DelaiDepasseError(temps_restant)
        SANS attendre si l'attente nécessaire dépasse ce délai. Jamais
        d'écran figé.
        """
        attente = self.temps_attente(tokens_a_envoyer)

        if attente > 0:
            if attente_max_s is not None and attente > attente_max_s:
                raise DelaiDepasseError(attente)
            if sur_attente:
                sur_attente(attente)
            await dormir(attente)

        self.enregistrer_appel(tokens_a_envoyer)
