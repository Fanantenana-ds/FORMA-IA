import uuid
from typing import Optional
from sqlalchemy.orm import Session
from app.models.preparation import Projet, Salle, EDT
from app.models.rh import Formateur


class PreparationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_projet_by_id(self, projet_id: uuid.UUID) -> Optional[Projet]:
        return self.db.query(Projet).filter(Projet.id == projet_id).first()

    def update_projet_metadata_edt(
            self,
            projet_id: uuid.UUID,
            duree_totale_jours: int,
            nombre_modules: int,
            formateur_principal_id: uuid.UUID,
            salle_principale_id: uuid.UUID,
            resume_hebdomadaire: dict,
            notes: list
    ) -> None:
        projet = self.get_projet_by_id(projet_id)
        if projet:
            projet.duree_totale_jours = duree_totale_jours
            projet.nombre_modules = nombre_modules
            projet.formateur_principal_id = formateur_principal_id
            projet.salle_principale_id = salle_principale_id
            projet.resume_hebdomadaire = resume_hebdomadaire
            projet.notes = notes

            self.db.flush()

    def get_or_create_formateur(self, nom: str, specialite: Optional[str] = None) -> Formateur:
        formateur = self.db.query(Formateur).filter(Formateur.nom.ilike(nom.strip())).first()
        if not formateur:
            formateur = Formateur(nom=nom.strip(), specialite=specialite)
            
            self.db.add(formateur)
            self.db.flush()
        return formateur

    def get_or_create_salle(self, nom: str, adresse: Optional[str] = None) -> Salle:
        salle = self.db.query(Salle).filter(Salle.nom.ilike(nom.strip())).first()
        if not salle:
            salle = Salle(nom.strip(), adresse=adresse)

            self.db.add(salle)
            self.db.flush()
        return salle

    def clear_projet_edts(self,projet_id: uuid.UUID) -> None:
        self.db.query(EDT).filter(EDT.projet_id == projet_id).delete(synchronize_session=False)
        self.db.flush()

    def bulk_insert_edts(self, edts: list[EDT]) -> None:
        self.db.add_all(edts)
        self.db.flush()