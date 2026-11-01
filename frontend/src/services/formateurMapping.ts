import { Formateur, StatutFormateur } from '../types';

/** Formateur tel que renvoyé par le backend (FormateurResponse). */
export interface BackendFormateur {
  id: string;
  nom: string;
  prenom: string | null;
  email: string | null;
  telephone: string | null;
  adresse: string | null;
  specialite: string | null;
  tarif_journalier: number | null;
  statut: 'DISPONIBLE' | 'OCCUPE' | 'INACTIF';
  score_moyen: number | null;
  nb_sessions: string | null;
  recommandation: string | null;
  notes_internes: string | null;
  date_creation: string;
}

export const STATUT_LABELS: StatutFormateur[] = ['Disponible', 'En session', 'Indisponible'];

const STATUT_FROM_BACKEND: Record<string, StatutFormateur> = {
  DISPONIBLE: 'Disponible',
  OCCUPE: 'En session',
  INACTIF: 'Indisponible'
};

const STATUT_TO_BACKEND: Record<StatutFormateur, BackendFormateur['statut']> = {
  Disponible: 'DISPONIBLE',
  'En session': 'OCCUPE',
  Indisponible: 'INACTIF'
};

const RECOMMANDATION_LABELS: Record<string, string> = {
  OUI: 'Oui',
  CONDITIONNEL: 'Conditionnel',
  NON: 'Non'
};

/** Chaîne vide ou espaces -> undefined. */
const clean = (value: string | null | undefined): string | undefined => {
  const trimmed = value?.trim();
  return trimmed ? trimmed : undefined;
};

export const toFormateur = (b: BackendFormateur): Formateur => {
  const sessions = b.nb_sessions !== null ? parseInt(b.nb_sessions, 10) : NaN;
  return {
    id: b.id,
    nom: b.nom,
    prenom: clean(b.prenom),
    email: clean(b.email),
    telephone: clean(b.telephone),
    adresse: clean(b.adresse),
    specialite: clean(b.specialite),
    tarifJournalier: b.tarif_journalier ?? undefined,
    statut: STATUT_FROM_BACKEND[b.statut] ?? 'Disponible',
    scoreMoyen: b.score_moyen ?? undefined,
    nbSessions: Number.isNaN(sessions) ? undefined : sessions,
    recommandation: b.recommandation
      ? RECOMMANDATION_LABELS[b.recommandation.toUpperCase()] ?? b.recommandation
      : undefined,
    notesInternes: clean(b.notes_internes),
    dateCreation: b.date_creation
  };
};

/** « Prénom Nom » */
export const formateurFullName = (f: Pick<Formateur, 'nom' | 'prenom'>): string =>
  [f.prenom, f.nom].filter(Boolean).join(' ');

/** Spécialités sous forme de liste (séparées par des virgules ou des points-virgules). */
export const specialitesList = (f: Pick<Formateur, 'specialite'>): string[] =>
  (f.specialite ?? '')
    .split(/[,;]/)
    .map((s) => s.trim())
    .filter(Boolean);

/** Valeurs du formulaire (tout en texte). */
export interface FormateurFormValues {
  prenom: string;
  nom: string;
  email: string;
  telephone: string;
  adresse: string;
  specialite: string;
  tarifJournalier: string;
  notesInternes: string;
  statut: StatutFormateur;
}

export const EMPTY_FORMATEUR_FORM: FormateurFormValues = {
  prenom: '',
  nom: '',
  email: '',
  telephone: '',
  adresse: '',
  specialite: '',
  tarifJournalier: '',
  notesInternes: '',
  statut: 'Disponible'
};

export const formValuesFromFormateur = (f: Formateur): FormateurFormValues => ({
  prenom: f.prenom ?? '',
  nom: f.nom,
  email: f.email ?? '',
  telephone: f.telephone ?? '',
  adresse: f.adresse ?? '',
  specialite: f.specialite ?? '',
  tarifJournalier: f.tarifJournalier !== undefined ? String(f.tarifJournalier) : '',
  notesInternes: f.notesInternes ?? '',
  statut: f.statut
});

const parseTarif = (value: string): number | undefined => {
  const n = parseFloat(value.replace(',', '.'));
  return Number.isFinite(n) && n > 0 ? n : undefined;
};

/** Corps de POST /rh/formateurs : les champs vides sont omis (le statut initial est « Disponible »). */
export const toCreatePayload = (v: FormateurFormValues) => {
  const tarif = parseTarif(v.tarifJournalier);
  return {
    nom: v.nom.trim(),
    ...(clean(v.prenom) ? { prenom: clean(v.prenom) } : {}),
    ...(clean(v.email) ? { email: clean(v.email) } : {}),
    ...(clean(v.telephone) ? { telephone: clean(v.telephone) } : {}),
    ...(clean(v.adresse) ? { adresse: clean(v.adresse) } : {}),
    ...(clean(v.specialite) ? { specialite: clean(v.specialite) } : {}),
    ...(tarif !== undefined ? { tarif_journalier: tarif } : {}),
    ...(clean(v.notesInternes) ? { notes_internes: v.notesInternes.trim() } : {})
  };
};

/**
 * Corps de PATCH /rh/formateurs/{id}.
 * Le backend ignore les valeurs null : pour vider un champ texte on envoie une chaîne vide.
 * Le tarif, lui, doit rester strictement positif : s'il est vide, il n'est pas modifié.
 */
export const toUpdatePayload = (v: FormateurFormValues) => {
  const tarif = parseTarif(v.tarifJournalier);
  return {
    nom: v.nom.trim(),
    prenom: v.prenom.trim(),
    email: v.email.trim(),
    telephone: v.telephone.trim(),
    adresse: v.adresse.trim(),
    specialite: v.specialite.trim(),
    notes_internes: v.notesInternes.trim(),
    statut: STATUT_TO_BACKEND[v.statut],
    ...(tarif !== undefined ? { tarif_journalier: tarif } : {})
  };
};
