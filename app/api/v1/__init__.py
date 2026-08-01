# ============================================================
# FORMA-IA — API V1 PACKAGE
# ============================================================

from .routes_veille import router as veille_router
# from .routes_tdr import router as tdr_router
# from .routes_formation import router as formation_router
# from .routes_attestation import router as attestation_router
# from .routes_dashboard import router as dashboard_router

__all__ = [
    "veille_router",
]