import React, { useState, useEffect, useRef } from 'react';
import {
  CalendarDays,
  Plus,
  MapPin,
  Users,
  User,
  Search,
  Clock,
  ArrowLeft,
  UserPlus,
  Building2,
  X,
  Check,
  Trash2,
  UserCheck,
  Pencil
} from 'lucide-react';
import { Session, PresenceRecord } from '../../types';
import { apiService } from '../../services/api';
import { SessionsM5Panel } from './SessionsM5Panel';

interface SessionsGroupesViewProps {
  sessions: Session[];
  presences?: PresenceRecord[];
  onOpenNewSession: () => void;
  onRefreshData?: () => Promise<void> | void;
  canDeleteSessions?: boolean;
  readOnly?: boolean;
}

const mapSessionParticipant = (p: any, sessionId: string, sessionTitle: string): PresenceRecord => ({
  id: String(p.id), participantId: String(p.id), sessionId, sessionTitle,
  nom: p.nom ?? '', prenom: p.prenom ?? '',
  apprenantNom: [p.prenom, p.nom].filter(Boolean).join(' '),
  entreprise: p.entreprise ?? '', poste: p.poste ?? '',
  niveauInitial: p.niveau_initial ?? '', scorePositionnement: p.score_positionnement ?? undefined,
  niveauFinal: p.niveau_final ?? '', scoreTestFinal: p.score_test_final ?? undefined,
  scoreSatisfaction: p.score_satisfaction ?? undefined,
  date: p.date_inscription ? new Date(p.date_inscription).toLocaleDateString('fr-FR') : '',
  statut: 'Absent'
});

export const SessionsGroupesView: React.FC<SessionsGroupesViewProps> = ({
  sessions,
  presences: initialPresencesProps = [],
  onOpenNewSession,
  onRefreshData,
  canDeleteSessions = false,
  readOnly = false
}) => {
  // Navigation State: null = list of sessions, session ID = detail view
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);

  // Local state for participants across sessions
  const [presencesList, setPresencesList] = useState<PresenceRecord[]>(initialPresencesProps);

  // Sync when props change
  useEffect(() => {
    setPresencesList((current) => {
      const enrolled = current.filter((item) => Boolean(item.participantId || item.niveauInitial));
      const enrolledIds = new Set(enrolled.map((item) => item.id));
      return [...initialPresencesProps.filter((item) => !enrolledIds.has(item.id)), ...enrolled];
    });
  }, [initialPresencesProps]);

  // Search terms
  const [sessionSearch, setSessionSearch] = useState('');
  const [participantSearch, setParticipantSearch] = useState('');

  // Modal State for adding participant
  const [isAddParticipantModalOpen, setIsAddParticipantModalOpen] = useState(false);
  const [newNom, setNewNom] = useState('');
  const [newEmail, setNewEmail] = useState('');
  const [newEntreprise, setNewEntreprise] = useState('');
  const [selectedParticipantId, setSelectedParticipantId] = useState('');
  const [participantOptions, setParticipantOptions] = useState<any[]>([]);
  const [participantError, setParticipantError] = useState('');
  const [participantsLoading, setParticipantsLoading] = useState(false);
  const [editingDateSessionId, setEditingDateSessionId] = useState<string | null>(null);
  const [editStartDate, setEditStartDate] = useState('');
  const [editEndDate, setEditEndDate] = useState('');
  const [editLieu, setEditLieu] = useState('');
  const [dateEditError, setDateEditError] = useState('');
  const [savingDates, setSavingDates] = useState(false);
  const [deletingSessionId, setDeletingSessionId] = useState<string | null>(null);
  const [sessionDeleteError, setSessionDeleteError] = useState('');
  const [sessionTrainerOptions, setSessionTrainerOptions] = useState<any[]>([]);
  const [editFormateurId, setEditFormateurId] = useState('');
  const [formsFeedback, setFormsFeedback] = useState<{ id: string; text: string; error?: boolean } | null>(null);
  const [publicLinks, setPublicLinks] = useState<{ participant?: string; formateur?: string; post_formation?: string }>({});
  const [publicLinkBusy, setPublicLinkBusy] = useState(false);
  const [publicLinkError, setPublicLinkError] = useState('');
  const participantCsvInput = useRef<HTMLInputElement>(null);

  const generatePublicLink = async (kind: 'participant' | 'formateur' | 'post_formation') => {
    setPublicLinkBusy(true); setPublicLinkError('');
    try {
      if (!activeSession?.id) throw new Error('Sélectionnez une session avant de générer ce lien.');
      const result = await apiService.createPublicRegistrationLink(kind, activeSession.id);
      const url = new URL(result.path, window.location.origin).toString();
      setPublicLinks(prev => ({ ...prev, [kind]: url }));
      try { await navigator.clipboard?.writeText(url); } catch { /* Le lien reste affiché avec son bouton Copier dédié. */ }
    } catch (error) { setPublicLinkError(error instanceof Error ? error.message : 'Génération du lien impossible.'); }
    finally { setPublicLinkBusy(false); }
  };

  // Selected session object
  const activeSession = sessions.find((s) => s.id === selectedSessionId);

  useEffect(() => {
    if (!selectedSessionId) return;
    let cancelled = false;
    setPublicLinks({});
    apiService.getSessionPublicLinks(selectedSessionId).then((links) => {
      if (cancelled) return;
      setPublicLinks({
        participant: links.participant ? new URL(links.participant.path, window.location.origin).toString() : undefined,
        formateur: links.formateur ? new URL(links.formateur.path, window.location.origin).toString() : undefined,
        post_formation: links.post_formation ? new URL(links.post_formation.path, window.location.origin).toString() : undefined,
      });
    }).catch(() => { if (!cancelled) setPublicLinks({}); });
    return () => { cancelled = true; };
  }, [selectedSessionId]);

  const startDateEdit = async (session: Session) => {
    setEditingDateSessionId(session.id);
    setEditStartDate(session.dateDebut ?? '');
    setEditEndDate(session.dateFin ?? '');
    setEditLieu(session.lieu ?? '');
    setEditFormateurId(session.formateurId ?? '');
    setDateEditError('');
    try { setSessionTrainerOptions(await apiService.getSessionTrainerOptions()); }
    catch { setSessionTrainerOptions([]); }
  };

  const saveSessionDates = async (sessionId: string) => {
    if (!editStartDate) { setDateEditError('La date de début est obligatoire.'); return; }
    if (editEndDate && editEndDate < editStartDate) { setDateEditError('La date de fin doit suivre la date de début.'); return; }
    setSavingDates(true);
    setDateEditError('');
    try {
      await apiService.updateSession(sessionId, { date_debut: editStartDate, date_fin: editEndDate || null, lieu: editLieu.trim() || null, ...(editFormateurId ? { formateur_id: editFormateurId } : {}) });
      await onRefreshData?.();
      setEditingDateSessionId(null);
    } catch (err) {
      setDateEditError(err instanceof Error ? err.message : 'Impossible de mettre à jour les dates.');
    } finally {
      setSavingDates(false);
    }
  };

  const deleteSession = async (session: Session) => {
    if (!window.confirm(`Supprimer la formation « ${session.intitule} » et ses séances ?`)) return;
    setDeletingSessionId(session.id);
    setSessionDeleteError('');
    try {
      await apiService.deleteSession(session.id);
      setPresencesList((previous) => previous.filter((participant) => participant.sessionId !== session.id));
      await onRefreshData?.();
    } catch (error) {
      setSessionDeleteError(error instanceof Error ? error.message : 'La suppression de la formation a échoué.');
    } finally {
      setDeletingSessionId(null);
    }
  };

  // Précharge les inscrits de toutes les sessions dès l'ouverture de la vue.
  // Ainsi, les noms et niveaux sont visibles sur les cartes sans ouvrir chaque session.
  useEffect(() => {
    if (!sessions.length) return;
    let cancelled = false;
    const sessionTitles = new Map<string, string>(sessions.map((session) => [session.id, session.intitule]));
    Promise.allSettled(sessions.map(async (session) => ({
      sessionId: session.id,
      participants: await apiService.getParticipants(session.id)
    }))).then((results) => {
      if (cancelled) return;
      const loadedIds = new Set(sessions.map((session) => session.id));
      const records = results.flatMap((result) => result.status === 'fulfilled'
        ? result.value.participants.map((participant: any) => mapSessionParticipant(participant, result.value.sessionId, sessionTitles.get(result.value.sessionId) ?? ''))
        : []);
      setPresencesList((prev) => [
        ...prev.filter((participant) => !loadedIds.has(participant.sessionId)),
        ...records
      ]);
      if (results.some((result) => result.status === 'rejected')) {
        setParticipantError('Certains inscrits n’ont pas pu être chargés. Actualisez la page pour réessayer.');
      }
    });
    return () => { cancelled = true; };
  }, [sessions]);

  // Filtered sessions
  const filteredSessions = sessions.filter(
    (s) =>
      s.intitule.toLowerCase().includes(sessionSearch.toLowerCase()) ||
      s.formateur.toLowerCase().includes(sessionSearch.toLowerCase()) ||
      s.code.toLowerCase().includes(sessionSearch.toLowerCase())
  );

  // Filtered participants for active session
  const sessionParticipants = presencesList.filter((p) => p.sessionId === selectedSessionId);
  const filteredParticipants = sessionParticipants.filter(
    (p) =>
      p.apprenantNom.toLowerCase().includes(participantSearch.toLowerCase()) ||
      p.entreprise.toLowerCase().includes(participantSearch.toLowerCase())
  );

  // Submit new participant
  const openAddParticipant = async () => {
    setNewNom(''); setNewEmail(''); setNewEntreprise(''); setSelectedParticipantId(''); setParticipantError('');
    setIsAddParticipantModalOpen(true);
    setParticipantsLoading(true);
    try { setParticipantOptions(await apiService.getParticipants()); }
    catch (err) { setParticipantError(err instanceof Error ? err.message : 'Impossible de charger les participants existants.'); }
    finally { setParticipantsLoading(false); }
  };

  const handleAddParticipantSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if ((!newNom.trim() && !selectedParticipantId) || !activeSession) return;
    setParticipantError('');
    setParticipantsLoading(true);
    try {
      const participant: any = selectedParticipantId
        ? participantOptions.find(item => String(item.id) === selectedParticipantId)
        : (newEmail.trim() ? participantOptions.find(item => String(item.email ?? '').trim().toLowerCase() === newEmail.trim().toLowerCase()) : undefined)
          ?? await apiService.createParticipant({ nom: newNom.trim(), email: newEmail.trim() || undefined, entreprise: newEntreprise.trim() || undefined });
      if (!participant) throw new Error('Participant introuvable. Actualisez la liste puis réessayez.');
      await apiService.enrollParticipant(activeSession.id, participant.id);
      const newRecord: PresenceRecord = { id: participant.id, participantId: participant.id, sessionId: activeSession.id, sessionTitle: activeSession.intitule, nom: participant.nom, apprenantNom: [participant.prenom, participant.nom].filter(Boolean).join(' '), entreprise: participant.entreprise ?? '', date: new Date().toLocaleDateString('fr-FR'), statut: 'Absent' };
      setPresencesList((prev) => [newRecord, ...prev]);
    } catch (err) { setParticipantError(err instanceof Error ? err.message : "L'inscription du participant a échoué."); return; }
    finally { setParticipantsLoading(false); }

    // Reset & close modal
    setNewNom('');
    setNewEmail('');
    setNewEntreprise('');
    setSelectedParticipantId('');
    setIsAddParticipantModalOpen(false);
  };

  const importParticipantsCsv = async (file?: File) => {
    if(!file||!activeSession) return;
    setParticipantsLoading(true);setParticipantError('');
    try {
      const lines=(await file.text()).replace(/^\uFEFF/,'').split(/\r?\n/).filter(Boolean);
      const parse=(line:string)=>line.split(/[,;]/).map(s=>s.trim().replace(/^"|"$/g,''));
      if(lines.length<2) throw new Error('Le CSV doit contenir une ligne d’en-têtes et au moins un participant.');
      const headers=parse(lines[0]).map(s=>s.toLowerCase().replaceAll(' ','_'));
      const existing=await apiService.getParticipants(); let added=0;
      for(const line of lines.slice(1)) {
        const cols=parse(line); const row=Object.fromEntries(headers.map((h,i)=>[h,cols[i]??'']));
        const nom=String(row.nom??row.name??'').trim(), prenom=String(row.prenom??row.first_name??'').trim(), email=String(row.email??'').trim().toLowerCase(), entreprise=String(row.organisation??row.entreprise??row.organization??'').trim();
        if(!nom) continue;
        let person:any=existing.find((p:any)=>email&&String(p.email??'').toLowerCase()===email);
        if(!person) { person=await apiService.createParticipant({nom,prenom,email:email||undefined,entreprise:entreprise||undefined}); existing.push(person); }
        try { await apiService.enrollParticipant(activeSession.id,String(person.id)); added++; } catch(e) { if(!(e instanceof Error&&e.message.toLowerCase().includes('déjà inscrit'))) throw e; }
      }
      const people=await apiService.getParticipants(activeSession.id);
      setPresencesList(prev=>[...prev.filter(p=>p.sessionId!==activeSession.id),...people.map((p:any)=>mapSessionParticipant(p,activeSession.id,activeSession.intitule))]);
      setParticipantError('');setFormsFeedback({id:activeSession.id,text:`Import terminé : ${added} inscription(s) traitée(s).`});
    } catch(e) { setParticipantError(e instanceof Error?e.message:'Import CSV impossible. Vérifiez les colonnes nom, prenom, email, organisation.'); }
    finally { setParticipantsLoading(false); if(participantCsvInput.current) participantCsvInput.current.value=''; }
  };

  // Delete participant from session
  const handleDeleteParticipant = async (participantId: string) => {
    if (!activeSession) return;
    try { await apiService.removeParticipant(activeSession.id, participantId); setPresencesList((prev) => prev.filter((p) => p.id !== participantId)); }
    catch (err) { setParticipantError(err instanceof Error ? err.message : 'La désinscription a échoué.'); }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* ========================================== */}
      {/* VUE 1 : LISTE DES SESSIONS ET GROUPES      */}
      {/* ========================================== */}
      {!selectedSessionId && (
        <>
          {/* Header Banner */}
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="px-2.5 py-0.5 rounded text-[11px] font-extrabold bg-[#1B8F6E]/10 text-[#1B8F6E]">
                  Planning & Promos
                </span>
                <span className="text-xs text-slate-400 font-medium">• Synchronisé REST</span>
              </div>
              <h1 className="text-2xl font-extrabold text-[#11162A]">Sessions & Groupes</h1>
              <p className="text-slate-600 text-xs mt-1">
                Gestion des promotions, répartition des groupes et inscription des participants retenus.
              </p>
            </div>

            {!readOnly && <button
              onClick={onOpenNewSession}
              className="px-4 py-2.5 bg-[#1B8F6E] hover:bg-[#16785c] text-white rounded-xl text-xs font-bold flex items-center gap-1.5 shadow-xs transition-colors shrink-0 cursor-pointer"
            >
              <Plus size={16} />
              <span>Créer une session</span>
            </button>}
          </div>

          {sessionDeleteError && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-xs font-semibold text-red-700">{sessionDeleteError}</div>}

          {/* Search Bar */}
          <div className="relative">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
            <input
              type="text"
              value={sessionSearch}
              onChange={(e) => setSessionSearch(e.target.value)}
              placeholder="Rechercher par intitulé, code session ou formateur..."
              className="w-full pl-10 pr-4 py-2.5 bg-white border border-slate-200 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1B8F6E]"
            />
          </div>

          {/* Sessions List */}
          <div className="space-y-4">
            {filteredSessions.map((s) => {
              const sessionPresences = presencesList.filter((p) => p.sessionId === s.id);
              const totalInscrits = sessionPresences.length || s.participantsInscrits;

              return (
                <div
                  key={s.id}
                  className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs flex flex-col lg:flex-row lg:items-center justify-between gap-4 hover:border-[#1B8F6E]/40 transition-all"
                >
                  <div className="space-y-2 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs font-extrabold text-slate-500 bg-[#F4F5F3] px-2.5 py-0.5 rounded border border-slate-200">
                        {s.code}
                      </span>
                      <span
                        className={`px-2.5 py-0.5 rounded-full text-xs font-bold ${
                          s.statut === 'En cours'
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            : s.statut === 'Planifiée'
                            ? 'bg-blue-50 text-blue-700 border border-blue-200'
                            : 'bg-slate-100 text-slate-600'
                        }`}
                      >
                        {s.statut}
                      </span>
                      <span className="text-xs text-slate-500 bg-slate-100 px-2.5 py-0.5 rounded flex items-center gap-1 font-medium">
                        <MapPin size={12} />
                        {s.lieu}
                      </span>
                    </div>

                    <h3 className="text-base font-extrabold text-[#11162A]">{s.intitule}</h3>

                    <div className="flex flex-wrap items-center gap-4 text-xs text-slate-600">
                      <span className="flex items-center gap-1.5">
                        <User size={14} className="text-slate-400" />
                        Formateur : <strong className="text-slate-800">{s.formateur}</strong>
                      </span>
                      <span className="flex items-center gap-1.5">
                        <Clock size={14} className="text-slate-400" />
                        Dates : <strong className="text-slate-800">{s.dates}</strong>
                      </span>
                    </div>
                    <div className="pt-1">
                      <div className="mb-1.5 flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wide text-slate-500">
                        <Users size={12} /> Participants inscrits
                      </div>
                      {sessionPresences.length ? (
                        <div className="flex flex-wrap gap-1.5">
                          {sessionPresences.map((participant) => (
                            <span key={participant.id} className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[10px] font-semibold text-slate-700">
                              {participant.apprenantNom}
                              {participant.niveauInitial && <span className="text-[#1B8F6E]">· {participant.niveauInitial}</span>}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="text-[11px] text-slate-400">Aucun participant inscrit pour le moment.</span>
                      )}
                    </div>
                    {!readOnly && editingDateSessionId === s.id && (
                      <div className="mt-3 flex flex-wrap items-end gap-2">
                        <label className="text-[11px] font-semibold text-slate-600">
                          Début
                          <input type="date" required value={editStartDate} onChange={(e) => setEditStartDate(e.target.value)} className="block mt-1 px-2.5 py-2 bg-slate-50 border border-slate-300 rounded-lg text-xs text-slate-800" />
                        </label>
                        <label className="text-[11px] font-semibold text-slate-600">
                          Fin
                          <input type="date" min={editStartDate || undefined} value={editEndDate} onChange={(e) => setEditEndDate(e.target.value)} className="block mt-1 px-2.5 py-2 bg-slate-50 border border-slate-300 rounded-lg text-xs text-slate-800" />
                        </label>
                        <label className="text-[11px] font-semibold text-slate-600">
                          Lieu
                          <input type="text" maxLength={200} value={editLieu} onChange={(e) => setEditLieu(e.target.value)} placeholder="Ville et salle à confirmer" className="block mt-1 min-w-44 px-2.5 py-2 bg-slate-50 border border-slate-300 rounded-lg text-xs text-slate-800" />
                        </label>
                        <label className="text-[11px] font-semibold text-slate-600">
                          Formateur
                          <select value={editFormateurId} onChange={(e) => setEditFormateurId(e.target.value)} className="block mt-1 min-w-52 px-2.5 py-2 bg-slate-50 border border-slate-300 rounded-lg text-xs text-slate-800">
                            <option value="">Conserver le formateur actuel</option>
                            {sessionTrainerOptions.map((trainer) => <option key={trainer.id} value={trainer.id}>{[trainer.prenom, trainer.nom].filter(Boolean).join(' ')}{trainer.recommandation === 'Oui' ? ' · Recommandé' : trainer.recommandation === 'Conditionnel' ? ' · À confirmer' : ''}{trainer.scoreMoyen != null ? ` · ${Math.round(trainer.scoreMoyen)}/100` : ''}{trainer.statut === 'En session' ? ' · En session' : ''}</option>)}
                          </select>
                          {!sessionTrainerOptions.length && <span className="block mt-1 max-w-52 text-[10px] text-slate-500">Aucun formateur disponible dans la section Formateurs.</span>}
                        </label>
                        <button type="button" disabled={savingDates} onClick={() => void saveSessionDates(s.id)} className="px-3 py-2 bg-[#1B8F6E] text-white rounded-lg text-xs font-bold disabled:opacity-50">
                          {savingDates ? 'Enregistrement…' : 'Enregistrer'}
                        </button>
                        <button type="button" onClick={() => { setEditingDateSessionId(null); setDateEditError(''); }} className="px-3 py-2 bg-slate-100 text-slate-700 rounded-lg text-xs font-bold">Annuler</button>
                        {dateEditError && <span className="w-full text-xs text-red-600">{dateEditError}</span>}
                      </div>
                    )}
                  </div>

                  <div className="flex flex-wrap items-center gap-5 pt-3 lg:pt-0 border-t lg:border-t-0 border-slate-100 shrink-0">
                    <div>
                      <div className="text-[10px] font-bold text-slate-400 uppercase">Inscrits / Jauge</div>
                      <div className="text-sm font-extrabold text-[#11162A] mt-0.5">
                        {s.capacityMax ? `${totalInscrits} / ${s.capacityMax}` : `${totalInscrits} inscrits`}
                      </div>
                      <div className="w-24 bg-slate-100 h-1.5 rounded-full mt-1 overflow-hidden">
                        <div
                          className="bg-[#1B8F6E] h-full rounded-full"
                          style={{ width: s.capacityMax ? `${Math.min(100, (totalInscrits / s.capacityMax) * 100)}%` : '0%' }}
                        ></div>
                      </div>
                    </div>

                    <div className="text-right">
                      <div className="text-[10px] font-bold text-slate-400 uppercase">Prix par apprenant</div>
                      <div className="text-sm font-extrabold text-[#11162A] mt-0.5">
                        {s.prixUnitaire != null ? `${s.prixUnitaire.toLocaleString()} Ar HT` : 'À définir'}
                      </div>
                    </div>

                    {!readOnly && <button
                      type="button"
                      title="Modifier les dates et le formateur"
                      onClick={() => editingDateSessionId === s.id ? setEditingDateSessionId(null) : startDateEdit(s)}
                      className="p-2.5 bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-lg transition-colors"
                    >
                      <Pencil size={15} />
                    </button>}

                    {!readOnly && canDeleteSessions && <button type="button" title="Supprimer cette formation" disabled={deletingSessionId === s.id} onClick={() => void deleteSession(s)} className="p-2.5 bg-red-50 hover:bg-red-100 text-red-600 rounded-lg transition-colors disabled:opacity-50"><Trash2 size={15} /></button>}

                    <button
                      type="button"
                      onClick={() => setSelectedSessionId(s.id)}
                      className="px-4 py-2.5 bg-[#11162A] hover:bg-[#1B8F6E] text-white rounded-xl text-xs font-bold flex items-center gap-2 shadow-xs transition-colors cursor-pointer"
                    >
                      <Users size={15} />
                      <span>Inscrits ({totalInscrits}) →</span>
                    </button>
                  </div>
                  {formsFeedback?.id === s.id && <div className={`w-full text-xs font-semibold ${formsFeedback.error ? 'text-red-600' : 'text-emerald-700'}`}>{formsFeedback.text}</div>}
                </div>
              );
            })}
          </div>
        </>
      )}

      {/* ========================================== */}
      {/* VUE 2 : LISTE DES PARTICIPANTS D'UNE SESSION */}
      {/* ========================================== */}
      {selectedSessionId && activeSession && (
        <div className="space-y-6">
          {/* Back & Session Info Header */}
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs">
            <button
              onClick={() => setSelectedSessionId(null)}
              className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-bold flex items-center gap-1.5 mb-4 transition-colors cursor-pointer"
            >
              <ArrowLeft size={14} />
              <span>← Retour à la liste des sessions</span>
            </button>

            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="px-2.5 py-0.5 rounded text-[10px] font-extrabold bg-blue-100 text-blue-800">
                    Code : {activeSession.code}
                  </span>
                  <span className="text-xs font-bold text-slate-500">
                    Statut : {activeSession.statut}
                  </span>
                </div>
                <h1 className="text-2xl font-extrabold text-[#11162A]">{activeSession.intitule}</h1>
                <p className="text-slate-600 text-xs mt-1 flex flex-wrap gap-x-4 gap-y-1">
                  <span>Formateur : <strong>{activeSession.formateur}</strong></span>
                  <span>• Dates : <strong>{activeSession.dates}</strong></span>
                  <span>• Lieu : <strong>{activeSession.lieu}</strong></span>
                </p>
              </div>

              <div className="flex flex-wrap gap-2">
                {!readOnly && <><button onClick={() => void openAddParticipant()} className="px-4 py-2.5 bg-[#1B8F6E] hover:bg-[#16785c] text-white rounded-xl text-xs font-bold flex items-center justify-center gap-2 shadow-sm transition-colors cursor-pointer"><UserPlus size={16} /><span>Ajouter un participant retenu</span></button>
                <input ref={participantCsvInput} type="file" accept=".csv,text/csv" className="hidden" onChange={e=>void importParticipantsCsv(e.target.files?.[0])}/><button onClick={()=>participantCsvInput.current?.click()} className="px-4 py-2.5 bg-slate-100 text-slate-700 rounded-xl text-xs font-bold">Importer CSV</button>
                <button disabled={publicLinkBusy} onClick={() => void generatePublicLink('participant')} className="px-4 py-2.5 bg-blue-50 text-blue-800 rounded-xl text-xs font-bold disabled:opacity-50">Lien public participants</button>
                <button disabled={publicLinkBusy} onClick={() => void generatePublicLink('post_formation')} className="px-4 py-2.5 bg-emerald-50 text-emerald-800 rounded-xl text-xs font-bold disabled:opacity-50">Lien d’évaluation post-formation</button>
                <button disabled={publicLinkBusy} onClick={() => void generatePublicLink('formateur')} className="px-4 py-2.5 bg-violet-50 text-violet-800 rounded-xl text-xs font-bold disabled:opacity-50">Lien candidature formateur</button></>}
              </div>
            </div>
            {(publicLinks.participant || publicLinks.formateur || publicLinks.post_formation || publicLinkError) && <div className="mt-3 space-y-2">{publicLinkError && <p role="alert" className="text-xs text-red-700">{publicLinkError}</p>}{(['participant','post_formation','formateur'] as const).map(kind => publicLinks[kind] && <div key={kind} className="flex flex-wrap items-center gap-2 rounded-lg bg-slate-50 p-2 text-xs"><strong>{kind === 'participant' ? 'Inscription participants' : kind === 'formateur' ? 'Candidatures formateur' : 'Évaluation post-formation'} :</strong><a className="break-all text-blue-700 underline" href={publicLinks[kind]} target="_blank" rel="noreferrer">{publicLinks[kind]}</a><button onClick={() => void navigator.clipboard?.writeText(publicLinks[kind]!)} className="rounded bg-white px-2 py-1 font-bold">Copier</button></div>)}{publicLinks.formateur && <p className="text-xs text-slate-600">Avant de partager ce lien, vérifiez sur la page publique le lieu, les dates et le profil issu du TDR validé.</p>}</div>}

            {/* Session Stats Bar */}
            <div className="grid grid-cols-3 gap-3 mt-6 pt-5 border-t border-slate-100">
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/80">
                <div className="text-[10px] uppercase font-bold text-slate-500">Participants Inscrits</div>
                <div className="text-xl font-extrabold text-[#11162A] mt-0.5">{sessionParticipants.length}</div>
              </div>

              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/80">
                <div className="text-[10px] uppercase font-bold text-slate-500">Capacité Maximale</div>
                <div className="text-xl font-extrabold text-[#11162A] mt-0.5">{activeSession.capacityMax ?? '—'}</div>
              </div>

              <div className="p-3 bg-emerald-50 rounded-xl border border-emerald-200/80">
                <div className="text-[10px] uppercase font-bold text-emerald-700">Taux de Remplissage</div>
                <div className="text-xl font-extrabold text-emerald-800 mt-0.5">
                  {activeSession.capacityMax ? `${Math.round((sessionParticipants.length / activeSession.capacityMax) * 100)}%` : '—'}
                </div>
              </div>
            </div>
          </div>

          {participantsLoading && <div className="p-3 rounded-xl bg-blue-50 text-blue-800 text-xs font-semibold">Chargement des participants…</div>}
          {participantError && <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs font-semibold">{participantError}</div>}

          {/* Participant Filter Search */}
          <div className="relative">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
            <input
              type="text"
              value={participantSearch}
              onChange={(e) => setParticipantSearch(e.target.value)}
              placeholder="Filtrer un participant par nom ou organisme..."
              className="w-full pl-10 pr-4 py-2.5 bg-white border border-slate-200 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1B8F6E]"
            />
          </div>

          {/* Participants Table List */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-x-auto">
            <div className="min-w-[1120px]">
              <div className="p-4 bg-[#F4F5F3] border-b border-slate-200 font-bold text-[10px] text-slate-600 uppercase tracking-wider grid grid-cols-14 gap-2 items-center">
                <div className="col-span-2">Nom</div><div className="col-span-2">Prénom</div><div className="col-span-2">Organisme / Entreprise</div><div className="col-span-2">Poste</div><div className="col-span-2">Niveau initial</div><div className="col-span-2">Niveau final</div><div className="col-span-1">Inscription</div><div className="col-span-1 text-center">Action</div>
              </div>

              <div className="divide-y divide-slate-100">
                {filteredParticipants.map((p) => (
                  <div key={p.id} className="p-4 grid grid-cols-14 gap-2 items-center text-xs hover:bg-slate-50 transition-colors">
                    <div className="col-span-2 font-bold text-[#11162A]">{p.nom ?? p.apprenantNom}</div>
                    <div className="col-span-2 text-slate-700">{p.prenom || '—'}</div>
                    <div className="col-span-2 font-semibold text-slate-700 flex items-center gap-1.5"><Building2 size={14} className="shrink-0 text-slate-400"/><span className="truncate">{p.entreprise || '—'}</span></div>
                    <div className="col-span-2 text-slate-700">{p.poste || '—'}</div>
                    <div className="col-span-2"><span className={`inline-flex rounded-full px-2.5 py-1 text-[10px] font-bold ${p.niveauInitial==='Expert'||p.niveauInitial==='Avancé'?'bg-violet-100 text-violet-800':p.niveauInitial==='Normal'?'bg-blue-100 text-blue-800':p.niveauInitial==='Intermédiaire'?'bg-amber-100 text-amber-800':p.niveauInitial==='Débutant'?'bg-slate-100 text-slate-700':'bg-slate-50 text-slate-400'}`}>{p.niveauInitial || 'Non évalué'}</span>{p.scorePositionnement!=null&&<span className="ml-1 text-[10px] text-slate-400">{p.scorePositionnement}%</span>}</div>
                    <div className="col-span-2"><span className={`inline-flex rounded-full px-2.5 py-1 text-[10px] font-bold ${p.niveauFinal==='Expert'||p.niveauFinal==='Avancé'?'bg-violet-100 text-violet-800':p.niveauFinal==='Normal'?'bg-blue-100 text-blue-800':p.niveauFinal==='Intermédiaire'?'bg-amber-100 text-amber-800':p.niveauFinal==='Débutant'?'bg-slate-100 text-slate-700':'bg-slate-50 text-slate-400'}`}>{p.niveauFinal || 'À évaluer'}</span>{p.scoreTestFinal!=null&&<span className="ml-1 text-[10px] text-slate-400">{p.scoreTestFinal}%</span>}</div>
                    <div className="col-span-1 text-slate-500 font-mono text-[10px]">{p.date || '—'}</div>
                    <div className="col-span-1 text-center">{!readOnly && <button onClick={() => handleDeleteParticipant(p.id)} title="Retirer ce participant de la session" className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors cursor-pointer"><Trash2 size={16} /></button>}</div>
                  </div>
                ))}

              {filteredParticipants.length === 0 && (
                <div className="p-8 text-center text-slate-500">
                  <Users size={28} className="mx-auto text-slate-300 mb-2" />
                  <p className="font-bold text-xs text-slate-700">Aucun participant retenu dans cette session.</p>
                  <p className="text-[11px] text-slate-400 mt-1">
                    Utilisez le bouton "+ Ajouter un participant retenu" ci-dessus pour l'inscrire.
                  </p>
                </div>
              )}
              </div>
            </div>
          </div>
          <SessionsM5Panel sessionId={activeSession.id} sessionTitle={activeSession.intitule} domain={activeSession.domaine} formationCode={activeSession.formationCode} formateurId={activeSession.formateurId} tauxPresence={activeSession.tauxPresence} participants={sessionParticipants.map(p => ({ id:p.id, nom:p.apprenantNom, prenom:(p as any).prenom }))} trainerMode={readOnly} />
        </div>
      )}

      {/* ========================================== */}
      {/* MODAL : AJOUT DE PARTICIPANT              */}
      {/* ========================================== */}
      {isAddParticipantModalOpen && activeSession && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in duration-200">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200 relative">
            <div className="flex items-center justify-between pb-4 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-[#1B8F6E]/10 text-[#1B8F6E] flex items-center justify-center font-bold">
                  <UserPlus size={18} />
                </div>
                <div>
                  <h3 className="text-base font-extrabold text-[#11162A]">Inscrire un Participant Retenu</h3>
                  <p className="text-[11px] text-slate-500">Session : {activeSession.code}</p>
                </div>
              </div>

              <button
                onClick={() => setIsAddParticipantModalOpen(false)}
                className="p-1 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 cursor-pointer"
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleAddParticipantSubmit} className="mt-4 space-y-4 text-xs">
              <div>
                <label className="block font-bold text-slate-700 uppercase mb-1">Participant déjà enregistré</label>
                <select value={selectedParticipantId} onChange={(e) => setSelectedParticipantId(e.target.value)} className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 focus:ring-2 focus:ring-[#1B8F6E] focus:outline-none">
                  <option value="">Créer une nouvelle fiche participant</option>
                  {participantOptions.map((participant) => <option key={participant.id} value={participant.id}>{participant.nom}{participant.email ? ` — ${participant.email}` : ''}</option>)}
                </select>
              </div>
              {!selectedParticipantId && <>
              <div>
                <label className="block font-bold text-slate-700 uppercase mb-1">
                  Nom & Prénom de l'apprenant *
                </label>
                <input
                  type="text"
                  required={!selectedParticipantId}
                  maxLength={50}
                  value={newNom}
                  onChange={(e) => setNewNom(e.target.value)}
                  placeholder="ex: Mihaja Rasoanaivo"
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 focus:ring-2 focus:ring-[#1B8F6E] focus:outline-none"
                />
              </div>

              <div>
                <label className="block font-bold text-slate-700 uppercase mb-1">
                  Adresse e-mail
                </label>
                <input
                  type="email"
                  maxLength={30}
                  value={newEmail}
                  onChange={(e) => setNewEmail(e.target.value)}
                  placeholder="participant@exemple.mg"
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 focus:ring-2 focus:ring-[#1B8F6E] focus:outline-none"
                />
              </div>

              <div>
                <label className="block font-bold text-slate-700 uppercase mb-1">
                  Entreprise / Organisme
                </label>
                <input
                  type="text"
                  maxLength={30}
                  value={newEntreprise}
                  onChange={(e) => setNewEntreprise(e.target.value)}
                  placeholder="ex: TELMA Madagascar / Orange / BOA"
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 focus:ring-2 focus:ring-[#1B8F6E] focus:outline-none"
                />
              </div>
              </>}

              <div className="pt-2 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setIsAddParticipantModalOpen(false)}
                  className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl font-bold transition-colors cursor-pointer"
                >
                  Annuler
                </button>
                <button
                  type="submit"
                  disabled={participantsLoading}
                  className="px-4 py-2 bg-[#1B8F6E] hover:bg-[#16785c] text-white rounded-xl font-bold shadow-xs transition-colors cursor-pointer flex items-center gap-1.5"
                >
                  <Check size={16} />
                  <span>Inscrire à la session</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
