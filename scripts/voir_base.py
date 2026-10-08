import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import engine
from sqlalchemy import text

TABLES = [
    "users", "opportunites", "historique_analyses",
    "documents", "offres", "projets", "salles",
    "sessions", "seances", "participants", "presences",
    "factures", "paiements", "relances",
    "formateurs", "candidats", "entretiens",
    "knowledge_base",
]

def main():
    print("=" * 60)
    print("FORMAIA — État de la base de données")
    print("=" * 60)
    with engine.connect() as c:
        for t in TABLES:
            try:
                n = c.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
                print(f"  {t:25s} : {n:>6} lignes")
            except Exception:
                print(f"  {t:25s} : (table absente)")
        
        print()
        print("=" * 60)
        print("RAG — Chunks par collection")
        print("=" * 60)
        rows = c.execute(text(
            "SELECT collection, formation_code, COUNT(*) "
            "FROM knowledge_base GROUP BY collection, formation_code"
        )).fetchall()
        for r in rows:
            print(f"  [{r[0]}] {r[1] or 'GLOBAL'} : {r[2]} chunks")

if __name__ == "__main__":
    main()