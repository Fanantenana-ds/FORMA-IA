"""
Migration : création des tables RH M4 (formateurs, candidats, entretiens).
Idempotent — vérifie l'existence avant création.

Usage :
    $env:PYTHONPATH = "."
    .\\venv\\Scripts\\python.exe scripts\\creer_tables_rh.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import engine

SQL = """
-- ============================================================
-- TABLE : formateurs
-- ============================================================
CREATE TABLE IF NOT EXISTS formateurs (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nom              VARCHAR(100) NOT NULL,
    prenom           VARCHAR(100),
    email            VARCHAR(200),
    telephone        VARCHAR(30),
    adresse          VARCHAR(300),
    specialite       VARCHAR(200),
    tarif_journalier FLOAT,
    statut           VARCHAR(20) NOT NULL DEFAULT 'DISPONIBLE'
                         CHECK (statut IN ('DISPONIBLE','OCCUPE','INACTIF')),
    score_moyen      FLOAT,
    nb_sessions      VARCHAR(10),
    recommandation   VARCHAR(20)
                         CHECK (recommandation IN ('OUI','CONDITIONNEL','NON')),
    notes_internes   TEXT,
    date_creation    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_formateurs_specialite ON formateurs(specialite);
CREATE INDEX IF NOT EXISTS idx_formateurs_statut     ON formateurs(statut);

-- ============================================================
-- TABLE : candidats
-- ============================================================
CREATE TABLE IF NOT EXISTS candidats (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nom                     VARCHAR(200) NOT NULL,
    poste_vise              VARCHAR(200) NOT NULL,
    cv_texte                TEXT,
    score_preselection      FLOAT,
    decision_preselection   VARCHAR(20)
                                CHECK (decision_preselection IN
                                       ('RETENU','A_DISCUTER','NON_RETENU')),
    review_id_preselection  VARCHAR(100),
    formateur_id            UUID REFERENCES formateurs(id) ON DELETE SET NULL,
    date_creation           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_candidats_decision   ON candidats(decision_preselection);
CREATE INDEX IF NOT EXISTS idx_candidats_formateur  ON candidats(formateur_id);

-- ============================================================
-- TABLE : entretiens
-- ============================================================
CREATE TABLE IF NOT EXISTS entretiens (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    candidat_id         UUID NOT NULL REFERENCES candidats(id) ON DELETE CASCADE,
    date_entretien      TIMESTAMPTZ,
    interviewers        VARCHAR(500),
    notes_brutes        TEXT,
    compte_rendu        TEXT,
    decision            VARCHAR(20)
                            CHECK (decision IN
                                   ('RECRUTER','APPROFONDIR','NE_PAS_RECRUTER')),
    review_id_entretien VARCHAR(100),
    email_brouillon     TEXT,
    review_id_email     VARCHAR(100),
    date_creation       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_entretiens_candidat ON entretiens(candidat_id);
"""


def main():
    print("=" * 60)
    print("Migration M4 RH — Création des tables")
    print("=" * 60)

    with engine.connect() as conn:
        from sqlalchemy import text
        conn.execute(text(SQL))
        conn.commit()

        for table in ("formateurs", "candidats", "entretiens"):
            result = conn.execute(
                text(f"SELECT COUNT(*) FROM {table}")
            ).scalar()
            print(f"  ✅ Table '{table}' prête — {result} ligne(s)")

    print("=" * 60)
    print("Migration terminée avec succès.")


if __name__ == "__main__":
    main()
