import uuid
from datetime import datetime, time, date
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.preparation import EDT
from app.repositories.preparation_repository import PreparationRepository
from app.schemas.preparation import EDTGeneratorOutput

class PreparationService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = PreparationRepository(db)

    def _parse_time(self, date_str: str) -> time:
        return datetime.strptime(date_str, "%H:%M").time()

    def _parse_date(self, date_str: str) -> date:
        return datetime.strptime(date_str, "%Y-%m-%d").date()

    def ingest_ia_edt_contract(self, projet_id: uuid.UUID, llm_output: EDTGeneratorOutput) -> list[EDT]:
        projet = self.repository.get_projet_by_id(projet_id)
        if not projet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Projet introuvable"
            )

        # Sauvegarde  automatique : point de restauration automatique si exception levée
        with self.db.begin_nested():
            # 1. Nettoyage de l'ancien EDT
            self.repository.clear_projet_edts(projet_id)

            # 2. Résolution des ressources principales
            formateur_principal = self.repository.get_or_create_formateur(
                nom=llm_output.formateur.nom,
                specialite=llm_output.formateur.specialite
            )
            salle_principal = self.repository.get_or_create_salle(
                nom=llm_output.salle.nom,
                adresse=llm_output.salle.adresse
            )

            # 3. Mise à jour des métadonnées du Projet
            self.repository.update_projet_metadata_edt(
                projet_id=projet_id,
                duree_totale_jours=llm_output.duree_totale_jours,
                nombre_modules=llm_output.nombre_modules,
                formateur_principal_id=formateur_principal.id,
                salle_principale_id=salle_principal.id,
                resume_hebdomadaire=llm_output.resume_hebdomadaire.model_dump(),
                notes=llm_output.notes
            )

            # 4. Consturction des sessions et pauses
            edts_to_insert = []

            for jour in llm_output.jours:
                jour_date = self._parse_date(jour.date)

                for session in jour.sessions:
                    f_id = formateur_principal.id
                    if session.formateur and session.formateur != formateur_principal.nom:
                        f_id = self.repository.get_or_create_formateur(session.formateur).id

                    s_id = salle_principal.id
                    if session.salle and session.salle != salle_principal.nom:
                        s_id = self.repository.get_or_create_salle(session.salle).id

                    edts_to_insert.append(EDT(
                        projet_id=projet_id,
                        code_session=session.id,
                        numero_jour=jour.numero,
                        date=jour_date,
                        heure_debut=self._parse_time(session.heure_debut),
                        heure_fin=self._parse_time(session.heure_fin),
                        duree_minutes=session.duree_minutes,
                        module=session.module,
                        type_activite=session.type,
                        objectifs=session.objectifs,
                        formateur_id=f_id,
                        salle_id=s_id
                    ))

                for pause in jour.pauses:
                    h_debut = self._parse_time(pause.heure_debut)
                    h_fin = self._parse_time(pause.heure_fin)
                    duree_p = int((datetime.combine(jour_date, h_fin) - datetime.combine(jour_date, h_debut)).total_seconds() / 60)

                    edts_to_insert.append(EDT(
                        projet_id=projet_id,
                        code_session=f"pause_{jour.numero}_{pause.heure_debut.replace(':', '')}",
                        numero_jour=jour.numero,
                        jour_semaine=jour.jour_semaine,
                        date=jour_date,
                        heure_debut=h_debut,
                        heure_fin=h_fin,
                        duree_minutes=duree_p,
                        module="Pause" if pause.type == "pause" else "Déjeuner",
                        type_activite=pause.type,
                        objectifs=[],
                        formateur_id=None,
                        salle_id=None
                    ))

            # 5. Insertion en masse
            self.repository.bulk_insert_edts(edts_to_insert)

        self.db.commit()
        return edts_to_insert  