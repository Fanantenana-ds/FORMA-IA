# ============================================================
# verifier_sync.py — VÉRIFIER CE QUI EST RÉELLEMENT EN BASE
# ============================================================
# Consultation directe et LECTURE SEULE de la base réelle (formaia) :
# aucune écriture, aucun risque. Réutilise la connexion déjà configurée
# par l'application (app.database), donc aucun mot de passe à ressaisir.
#
# Utilisation :
#   python scripts/verifier_sync.py                 → 10 dernières opportunités
#   python scripts/verifier_sync.py 20               → 20 dernières
#   python scripts/verifier_sync.py --recherche "IA"  → filtre par mot dans l'objet
# ============================================================

import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.database import engine  # noqa: E402


def main() -> None:
    args = sys.argv[1:]
    recherche = None
    limite = 10

    if "--recherche" in args:
        idx = args.index("--recherche")
        recherche = args[idx + 1] if idx + 1 < len(args) else None
        args = args[:idx] + args[idx + 2:]

    if args and args[0].isdigit():
        limite = int(args[0])

    where = "WHERE objet ILIKE :mot" if recherche else ""
    params = {"mot": f"%{recherche}%"} if recherche else {}

    with engine.connect() as db:
        total = db.execute(text("SELECT count(*) FROM opportunites")).scalar()
        print(f"Total opportunites en base : {total}")
        print("-" * 70)

        rows = db.execute(
            text(
                f"""
                SELECT id, objet, budget, domaine, statut, source, date_creation
                FROM opportunites
                {where}
                ORDER BY date_creation DESC
                LIMIT :limite
                """
            ),
            {**params, "limite": limite},
        ).fetchall()

        if not rows:
            print("Aucune ligne trouvée.")
            return

        for r in rows:
            d = r._mapping
            print(f"[{d['date_creation']}] {d['id']}")
            print(f"   objet   : {d['objet']}")
            print(f"   budget  : {d['budget']}  | domaine : {d['domaine']} "
                  f"| source : {d['source']} | statut : {d['statut']}")
            print()


if __name__ == "__main__":
    main()
