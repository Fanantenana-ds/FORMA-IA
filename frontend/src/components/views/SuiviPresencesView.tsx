import React, { useState, useEffect } from 'react';
import { PageHeader } from '../PageHeader';
import {
  UserCheck,
  CheckCircle2,
  Clock,
  AlertCircle,
  Search,
  Users,
  ArrowLeft,
  Building2,
  Calendar,
  MapPin,
  Sparkles,
  ShieldCheck,
  UserX
} from 'lucide-react';
import { PresenceRecord, Session } from '../../types';
import { apiService } from '../../services/api';

interface SuiviPresencesViewProps {
  presences: PresenceRecord[];
  sessions: Session[];
  readOnly?: boolean;
}

export const SuiviPresencesView: React.FC<SuiviPresencesViewProps> = ({
  presences: initialPresencesProps,
  sessions,
  readOnly = false
}) => {
  // Navigation State: null = list of sessions, session ID = detail view
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);

  // Local state for live presence tracking
  const [presencesList, setPresencesList] = useState<PresenceRecord[]>(initialPresencesProps);

  // Search & Filter state
  const [sessionSearch, setSessionSearch] = useState('');
  const [participantSearch, setParticipantSearch] = useState('');
  const [sessionFilter, setSessionFilter] = useState<'all' | 'en_cours'>(readOnly ? 'all' : 'en_cours');

  const [seances, setSeances] = useState<any[]>([]);
  const [selectedSeanceId, setSelectedSeanceId] = useState('');
  const [sessionPeople, setSessionPeople] = useState<any[]>([]);
  const [apiError, setApiError] = useState('');
  const [presenceBusy, setPresenceBusy] = useState(false);

  const createSessionSeance = async () => {
    if (!selectedSessionId) return;
    setPresenceBusy(true); setApiError('');
    try {
      const seance: any = await apiService.createSeance(selectedSessionId, { date: new Date().toISOString().slice(0, 10) });
      setSeances((previous) => [...previous, seance]); setSelectedSeanceId(seance.id);
    } catch (err) { setApiError(err instanceof Error ? err.message : 'La création de la séance a échoué.'); }
    finally { setPresenceBusy(false); }
  };

  // Sync if props change
  useEffect(() => {
    setPresencesList(initialPresencesProps);
  }, [initialPresencesProps]);

  // Selected session object
  const activeSession = sessions.find((s) => s.id === selectedSessionId);

  useEffect(() => {
    if (!selectedSessionId) return;
    let cancelled = false;
    setApiError(''); setPresenceBusy(true);
    Promise.all([apiService.getSeances(selectedSessionId), apiService.getParticipants(selectedSessionId)])
      .then(([sessionSeances, participants]) => {
        if (cancelled) return;
        setSeances(sessionSeances); setSessionPeople(participants);
        setSelectedSeanceId((previous) => previous && sessionSeances.some((s: any) => s.id === previous) ? previous : sessionSeances[0]?.id ?? '');
      })
      .catch((err) => { if (!cancelled) setApiError(err instanceof Error ? err.message : 'Impossible de charger les séances et les participants.'); })
      .finally(() => { if (!cancelled) setPresenceBusy(false); });
    return () => { cancelled = true; };
  }, [selectedSessionId]);

  useEffect(() => {
    if (!selectedSeanceId) { setPresencesList([]); return; }
    let cancelled = false;
    setPresenceBusy(true); setApiError('');
    apiService.getPresenceForSession(selectedSeanceId).then((records) => {
      if (cancelled) return;
      const byParticipant = new Map(records.map((r: any) => [r.participant_id, r]));
      const sessionId = selectedSessionId;
      const sessionTitle = activeSession?.intitule ?? '';
      setPresencesList(sessionPeople.map((person: any) => {
        const presence: any = byParticipant.get(person.id);
        return { id: presence?.id ?? person.id, participantId: person.id, sessionId, sessionTitle, nom: person.nom ?? '', prenom: person.prenom ?? '', apprenantNom: [person.prenom, person.nom].filter(Boolean).join(' '),
          entreprise: person.entreprise ?? '', date: new Date().toLocaleDateString('fr-FR'),
          statut: presence?.statut === 'PRESENT' ? 'Présent' : presence?.statut === 'EXCUSE' ? 'Excusé' : 'Absent',
          heureEmargement: undefined };
      }));
    }).catch((err) => { if (!cancelled) setApiError(err instanceof Error ? err.message : 'Impossible de charger les présences.'); })
      .finally(() => { if (!cancelled) setPresenceBusy(false); });
    return () => { cancelled = true; };
  }, [selectedSeanceId, sessionPeople, activeSession?.intitule]);

  // Current time helper
  const getCurrentTime = () => {
    const now = new Date();
    const h = String(now.getHours()).padStart(2, '0');
    const m = String(now.getMinutes()).padStart(2, '0');
    return `${h}:${m}`;
  };

  // Handler to update presence status of a participant
  const handleUpdateStatus = async (presenceId: string, newStatus: 'Présent' | 'Absent' | 'Excusé') => {
    const item = presencesList.find((p) => p.id === presenceId);
    const backendStatus = newStatus === 'Présent' ? 'PRESENT' : newStatus === 'Excusé' ? 'EXCUSE' : 'ABSENT';
    if (!item || !selectedSeanceId) return;
    setApiError(''); setPresenceBusy(true);
    let savedPresenceId = item.id;
    try {
      if (item.participantId && item.id === item.participantId) {
        const presence: any = await apiService.createPresence(selectedSeanceId, item.participantId, backendStatus);
        savedPresenceId = presence.id ?? item.id;
      } else await apiService.updatePresence(item.id, backendStatus);
    } catch (err) { setApiError(err instanceof Error ? err.message : 'La mise à jour de la présence a échoué.'); setPresenceBusy(false); return; }
    setPresenceBusy(false);
    const currentTime = getCurrentTime();
    setPresencesList((prev) =>
      prev.map((p) => {
        if (p.id === presenceId) {
          return {
            ...p,
            id: savedPresenceId,
            statut: newStatus,
            heureEmargement: newStatus === 'Absent' ? undefined : p.heureEmargement || currentTime
          };
        }
        return p;
      })
    );
  };

  // Filtered sessions for View 1
  const filteredSessions = sessions.filter((s) => {
    const matchesSearch =
      s.intitule.toLowerCase().includes(sessionSearch.toLowerCase()) ||
      s.code.toLowerCase().includes(sessionSearch.toLowerCase()) ||
      s.formateur.toLowerCase().includes(sessionSearch.toLowerCase());

    if (sessionFilter === 'en_cours') {
      return matchesSearch && s.statut === 'En cours';
    }
    return matchesSearch;
  });

  // Filtered participants for View 2
  const sessionParticipants = presencesList.filter((p) => p.sessionId === selectedSessionId);
  const filteredParticipants = sessionParticipants.filter(
    (p) =>
      p.apprenantNom.toLowerCase().includes(participantSearch.toLowerCase()) ||
      p.entreprise.toLowerCase().includes(participantSearch.toLowerCase())
  );

  // Stats for active selected session
  const presentsCount = sessionParticipants.filter((p) => p.statut === 'Présent').length;
  const retardsCount = sessionParticipants.filter((p) => p.statut === 'Excusé').length;
  const absentsCount = sessionParticipants.filter((p) => p.statut === 'Absent').length;
  const totalParticipants = sessionParticipants.length;

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* ========================================== */}
      {/* VUE 1 : LISTE DES SESSIONS ACTIVES        */}
      {/* ========================================== */}
      {!selectedSessionId && (
        <>
          <PageHeader
            icon={<UserCheck size={22} />}
            badge="Émargement numérique"
            title="Suivi des Présences"
            subtitle="Consultez une session pour enregistrer les presences par seance et verifier les pointages des participants inscrits."
          />

          {/* Barre de filtres */}
          {!readOnly && (
            <div className="flex items-center gap-1 rounded-2xl border border-slate-200 bg-white px-3 py-2 shadow-xs">
              <button onClick={() => setSessionFilter('en_cours')} className={`flex items-center gap-1.5 rounded-xl px-4 py-2 text-xs font-semibold transition-all ${sessionFilter === 'en_cours' ? 'bg-brand-navy text-white shadow-sm' : 'text-slate-500 hover:bg-slate-100 hover:text-slate-800'}`}>
                Sessions actives ({sessions.filter((s) => s.statut === 'En cours').length})
              </button>
              <button onClick={() => setSessionFilter('all')} className={`flex items-center gap-1.5 rounded-xl px-4 py-2 text-xs font-semibold transition-all ${sessionFilter === 'all' ? 'bg-brand-navy text-white shadow-sm' : 'text-slate-500 hover:bg-slate-100 hover:text-slate-800'}`}>
                Toutes les sessions ({sessions.length})
              </button>
            </div>
          )}

          {/* Search Bar */}
          <div className="relative">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
            <input
              type="text"
              value={sessionSearch}
              onChange={(e) => setSessionSearch(e.target.value)}
              placeholder="Rechercher une session par intitulé, code ou formateur..."
              className="w-full pl-10 pr-4 py-2.5 bg-white border border-slate-200 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#0B1F4D]"
            />
          </div>

          {/* Sessions Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredSessions.map((s) => {
              const sessionPresences = presencesList.filter((p) => p.sessionId === s.id);
              const pCount = sessionPresences.filter((p) => p.statut === 'Présent').length;

              return (
                <div
                  key={s.id}
                  className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs hover:border-[#0B1F4D]/40 hover:shadow-md transition-all flex flex-col justify-between"
                >
                  <div>
                    {/* Top Badges */}
                    <div className="flex items-center justify-between mb-2.5">
                      <span
                        className={`px-2.5 py-0.5 rounded-full text-[10px] font-extrabold flex items-center gap-1 ${
                          s.statut === 'En cours'
                            ? 'bg-emerald-100 text-emerald-800'
                            : s.statut === 'Planifiée'
                            ? 'bg-blue-100 text-blue-800'
                            : 'bg-slate-100 text-slate-600'
                        }`}
                      >
                        <span
                          className={`w-1.5 h-1.5 rounded-full ${
                            s.statut === 'En cours' ? 'bg-emerald-500 animate-pulse' : 'bg-current'
                          }`}
                        ></span>
                        <span>{s.statut}</span>
                      </span>

                      <span className="text-[10px] font-mono font-bold text-slate-400 bg-slate-50 px-2 py-0.5 rounded border border-slate-200">
                        {s.code}
                      </span>
                    </div>

                    {/* Session Title */}
                    <h3 className="font-extrabold text-[#11162A] text-sm leading-snug line-clamp-2">
                      {s.intitule}
                    </h3>
                    <p className="text-[11px] font-semibold text-[#0B1F4D] mt-1">{s.domaine}</p>

                    {/* Info Metadata */}
                    <div className="mt-4 space-y-1.5 text-xs text-slate-600">
                      <div className="flex items-center gap-2">
                        <Users size={14} className="text-slate-400 shrink-0" />
                        <span>
                          Formateur : <strong className="text-slate-800">{s.formateur}</strong>
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Calendar size={14} className="text-slate-400 shrink-0" />
                        <span>{s.dates}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <MapPin size={14} className="text-slate-400 shrink-0" />
                        <span>Modalité : {s.lieu}</span>
                      </div>
                    </div>

                    {/* Registered Participants & Attendance Stats */}
                    <div className="mt-4 p-3 rounded-xl bg-slate-50 border border-slate-100 flex items-center justify-between">
                      <div>
                        <div className="text-[10px] uppercase font-bold text-slate-400">Participants inscrits</div>
                        <div className="font-extrabold text-[#11162A] text-sm mt-0.5">
                          {s.capacityMax ? `${sessionPresences.length || s.participantsInscrits} / ${s.capacityMax}` : `${sessionPresences.length || s.participantsInscrits} inscrits`}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-[10px] uppercase font-bold text-slate-400">Émargo. Validés</div>
                        <div className="font-extrabold text-emerald-600 text-sm mt-0.5">
                          {pCount} Présent(s)
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Action Button */}
                  <button
                    onClick={() => setSelectedSessionId(s.id)}
                    className="w-full mt-5 py-2.5 bg-[#11162A] hover:bg-[#0B1F4D] text-white rounded-xl font-bold text-xs shadow-xs transition-colors flex items-center justify-center gap-2 cursor-pointer"
                  >
                    <UserCheck size={16} />
                    <span>Gérer l'émargement →</span>
                  </button>
                </div>
              );
            })}
          </div>

          {filteredSessions.length === 0 && (
            <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center text-slate-500">
              <AlertCircle size={32} className="mx-auto text-slate-400 mb-2" />
              <p className="font-bold text-sm text-slate-700">Aucune session trouvée</p>
              <p className="text-xs text-slate-400 mt-1">
                Essayez de modifier votre terme de recherche ou le filtre.
              </p>
            </div>
          )}
        </>
      )}

      {/* ========================================== */}
      {/* VUE 2 : PARTICIPANTS ET ÉMARGEMENT D'UNE SESSION */}
      {/* ========================================== */}
      {selectedSessionId && activeSession && (
        <div className="space-y-6">
          {/* Back & Title Header */}
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs">
            <button
              onClick={() => setSelectedSessionId(null)}
              className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-bold flex items-center gap-1.5 mb-4 transition-colors cursor-pointer"
            >
              <ArrowLeft size={14} />
              <span>Retour à la liste des sessions</span>
            </button>

            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="px-2.5 py-0.5 rounded text-[10px] font-extrabold bg-emerald-100 text-emerald-800">
                    {activeSession.statut}
                  </span>
                  <span className="text-xs font-mono font-bold text-slate-400">
                    {activeSession.code}
                  </span>
                </div>
                <h1 className="text-2xl font-extrabold text-[#11162A]">{activeSession.intitule}</h1>
                <p className="text-slate-600 text-xs mt-1 flex flex-wrap gap-x-4 gap-y-1">
                  <span>Formateur : <strong>{activeSession.formateur}</strong></span>
                  <span>• Dates : <strong>{activeSession.dates}</strong></span>
                  <span>• Modalité : <strong>{activeSession.lieu}</strong></span>
                </p>
              </div>

            </div>

            <div className="mt-5 flex flex-wrap items-center gap-2">
              <label htmlFor="presence-seance" className="text-xs font-bold text-slate-600">Séance :</label>
              <select id="presence-seance" value={selectedSeanceId} onChange={(e) => setSelectedSeanceId(e.target.value)} className="px-3 py-2 border border-slate-300 rounded-lg bg-white text-xs">
                <option value="">Choisir une séance</option>
                {seances.map((seance: any) => <option key={seance.id} value={seance.id}>{new Date(seance.date).toLocaleDateString('fr-FR')}{seance.theme ? ` · ${seance.theme}` : ''}</option>)}
              </select>
              {!readOnly && !seances.length && <button type="button" disabled={presenceBusy} onClick={createSessionSeance} className="px-3 py-2 bg-[#0B1F4D] text-white rounded-lg text-xs font-bold">Créer une séance aujourd'hui</button>}
              {presenceBusy && <span className="text-xs text-slate-500">Enregistrement…</span>}
            </div>
            {apiError && <div className="mt-3 p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs font-semibold">{apiError}</div>}

            {/* Attendance Counters Bar */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-6 pt-5 border-t border-slate-100">
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/80">
                <div className="text-[10px] uppercase font-bold text-slate-500">Total Inscrits</div>
                <div className="text-xl font-extrabold text-[#11162A] mt-0.5">{totalParticipants}</div>
              </div>

              <div className="p-3 bg-emerald-50 rounded-xl border border-emerald-200/80">
                <div className="text-[10px] uppercase font-bold text-emerald-700">Présents</div>
                <div className="text-xl font-extrabold text-emerald-800 mt-0.5">{presentsCount}</div>
              </div>

              <div className="p-3 bg-amber-50 rounded-xl border border-amber-200/80">
                <div className="text-[10px] uppercase font-bold text-amber-700">Excusés</div>
                <div className="text-xl font-extrabold text-amber-800 mt-0.5">{retardsCount}</div>
              </div>

              <div className="p-3 bg-red-50 rounded-xl border border-red-200/80">
                <div className="text-[10px] uppercase font-bold text-red-700">Absents</div>
                <div className="text-xl font-extrabold text-red-800 mt-0.5">{absentsCount}</div>
              </div>
            </div>
          </div>

          {/* Participant Search */}
          <div className="relative">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
            <input
              type="text"
              value={participantSearch}
              onChange={(e) => setParticipantSearch(e.target.value)}
              placeholder="Filtrer un participant inscrit par nom ou entreprise..."
              className="w-full pl-10 pr-4 py-2.5 bg-white border border-slate-200 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#0B1F4D]"
            />
          </div>

          {/* REGISTERED PARTICIPANTS LIST TABLE */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
            <div className="p-4 bg-[#F4F5F3] border-b border-slate-200 font-bold text-xs text-slate-600 uppercase tracking-wider grid grid-cols-12 gap-2 items-center">
              <div className="col-span-4">Apprenant Inscrit & Organisme</div>
              <div className="col-span-2">Date</div>
              <div className="col-span-2 text-center">Horodateur</div>
              <div className="col-span-4 text-center">Émargement Rapide (Action)</div>
            </div>

            <div className="divide-y divide-slate-100">
              {filteredParticipants.map((p) => (
                <div
                  key={p.id}
                  className="p-4 grid grid-cols-12 gap-2 items-center text-xs hover:bg-slate-50 transition-colors"
                >
                  {/* Participant Name & Company */}
                  <div className="col-span-4">
                    <div className="font-bold text-[#11162A] text-sm flex items-center gap-1.5">
                      <span>{p.apprenantNom}</span>
                    </div>
                    <div className="text-slate-500 text-[11px] flex items-center gap-1 mt-0.5">
                      <Building2 size={12} className="text-slate-400" />
                      <span>{p.entreprise}</span>
                    </div>
                  </div>

                  {/* Date */}
                  <div className="col-span-2 text-slate-600 font-mono text-[11px]">
                    {p.date}
                  </div>

                  {/* Horodateur / Timestamp */}
                  <div className="col-span-2 text-center">
                    {p.heureEmargement ? (
                      <span className="inline-flex items-center gap-1 bg-slate-100 text-slate-700 font-mono text-xs font-bold px-2 py-1 rounded-md border border-slate-200">
                        <Clock size={12} className="text-slate-400" />
                        <span>{p.heureEmargement}</span>
                      </span>
                    ) : (
                      <span className="text-slate-400 text-[11px] italic">Non renseigné</span>
                    )}
                  </div>

                  {/* 3 STATUS ACTION BUTTONS: PRÉSENT | ABSENT | RETARD */}
                  <div className="col-span-4 flex items-center justify-center gap-1.5">
                    {readOnly ? <span className={"rounded-full px-3 py-1.5 text-xs font-bold " + (p.statut === 'Présent' ? 'bg-emerald-50 text-emerald-700' : p.statut === 'Absent' ? 'bg-red-50 text-red-700' : 'bg-amber-50 text-amber-700')}>{p.statut}</span> : <>
                    {/* BUTTON 1: PRÉSENT */}
                    <button
                      onClick={() => handleUpdateStatus(p.id, 'Présent')}
                      className={`px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1 transition-all cursor-pointer ${
                        p.statut === 'Présent'
                          ? 'bg-emerald-600 text-white shadow-xs ring-2 ring-emerald-600/30 font-extrabold'
                          : 'bg-slate-100 text-slate-600 hover:bg-emerald-100 hover:text-emerald-800'
                      }`}
                    >
                      <CheckCircle2 size={14} />
                      <span>Présent</span>
                    </button>

                    {/* BUTTON 2: ABSENT */}
                    <button
                      onClick={() => handleUpdateStatus(p.id, 'Absent')}
                      className={`px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1 transition-all cursor-pointer ${
                        p.statut === 'Absent'
                          ? 'bg-red-600 text-white shadow-xs ring-2 ring-red-600/30 font-extrabold'
                          : 'bg-slate-100 text-slate-600 hover:bg-red-100 hover:text-red-800'
                      }`}
                    >
                      <UserX size={14} />
                      <span>Absent</span>
                    </button>

                    {/* BUTTON 3: RETARD */}
                    <button
                      onClick={() => handleUpdateStatus(p.id, 'Excusé')}
                      className={`px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1 transition-all cursor-pointer ${
                        p.statut === 'Excusé'
                          ? 'bg-amber-500 text-white shadow-xs ring-2 ring-amber-500/30 font-extrabold'
                          : 'bg-slate-100 text-slate-600 hover:bg-amber-100 hover:text-amber-800'
                      }`}
                    >
                      <Clock size={14} />
                      <span>Excusé</span>
                    </button>
                    </>}
                  </div>
                </div>
              ))}

              {filteredParticipants.length === 0 && (
                <div className="p-8 text-center text-slate-500">
                  <Users size={28} className="mx-auto text-slate-300 mb-2" />
                  <p className="font-bold text-xs text-slate-700">Aucun participant inscrit pour le moment.</p>
                  <p className="text-[11px] text-slate-400 mt-1">Les inscriptions se gèrent depuis Sessions &amp; Groupes.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

    </div>
  );
};
