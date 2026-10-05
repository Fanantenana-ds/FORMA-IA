import React, { useState, useEffect } from 'react';
import {
  UserCheck,
  CheckCircle2,
  Clock,
  AlertCircle,
  Search,
  Users,
  ArrowLeft,
  UserPlus,
  X,
  Plus,
  Check,
  Building2,
  Calendar,
  MapPin,
  Sparkles,
  ShieldCheck,
  UserX
} from 'lucide-react';
import { PresenceRecord, Session } from '../../types';

interface SuiviPresencesViewProps {
  presences: PresenceRecord[];
  sessions: Session[];
}

export const SuiviPresencesView: React.FC<SuiviPresencesViewProps> = ({
  presences: initialPresencesProps,
  sessions
}) => {
  // Navigation State: null = list of sessions, session ID = detail view
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);

  // Local state for live presence tracking
  const [presencesList, setPresencesList] = useState<PresenceRecord[]>(initialPresencesProps);

  // Search & Filter state
  const [sessionSearch, setSessionSearch] = useState('');
  const [participantSearch, setParticipantSearch] = useState('');
  const [sessionFilter, setSessionFilter] = useState<'all' | 'en_cours'>('en_cours');

  // Modal State for adding retained participant
  const [isAddParticipantModalOpen, setIsAddParticipantModalOpen] = useState(false);
  const [newNom, setNewNom] = useState('');
  const [newEntreprise, setNewEntreprise] = useState('');
  const [newStatut, setNewStatut] = useState<'Présent' | 'Absent' | 'Retard'>('Présent');
  const [newHeure, setNewHeure] = useState('');

  // Sync if props change
  useEffect(() => {
    setPresencesList(initialPresencesProps);
  }, [initialPresencesProps]);

  // Selected session object
  const activeSession = sessions.find((s) => s.id === selectedSessionId);

  // Current time helper
  const getCurrentTime = () => {
    const now = new Date();
    const h = String(now.getHours()).padStart(2, '0');
    const m = String(now.getMinutes()).padStart(2, '0');
    return `${h}:${m}`;
  };

  // Handler to update presence status of a participant
  const handleUpdateStatus = (participantId: string, newStatus: 'Présent' | 'Absent' | 'Retard') => {
    const currentTime = getCurrentTime();
    setPresencesList((prev) =>
      prev.map((p) => {
        if (p.id === participantId) {
          return {
            ...p,
            statut: newStatus,
            heureEmargement: newStatus === 'Absent' ? undefined : p.heureEmargement || currentTime
          };
        }
        return p;
      })
    );
  };

  // Handler to submit a new retained participant
  const handleAddParticipantSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newNom || !newEntreprise || !activeSession) return;

    const timeToUse = newHeure || getCurrentTime();

    const newRecord: PresenceRecord = {
      id: `pres-${Date.now()}`,
      sessionId: activeSession.id,
      sessionTitle: activeSession.intitule,
      apprenantNom: newNom,
      entreprise: newEntreprise,
      date: new Date().toLocaleDateString('fr-FR'),
      statut: newStatut,
      heureEmargement: newStatut === 'Absent' ? undefined : timeToUse
    };

    setPresencesList((prev) => [newRecord, ...prev]);

    // Reset form & close
    setNewNom('');
    setNewEntreprise('');
    setNewStatut('Présent');
    setNewHeure('');
    setIsAddParticipantModalOpen(false);
  };

  // Open modal handler
  const handleOpenAddModal = () => {
    setNewHeure(getCurrentTime());
    setIsAddParticipantModalOpen(true);
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
  const retardsCount = sessionParticipants.filter((p) => p.statut === 'Retard').length;
  const absentsCount = sessionParticipants.filter((p) => p.statut === 'Absent').length;
  const totalParticipants = sessionParticipants.length;

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* ========================================== */}
      {/* VUE 1 : LISTE DES SESSIONS ACTIVES        */}
      {/* ========================================== */}
      {!selectedSessionId && (
        <>
          {/* Header Banner */}
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="px-2.5 py-0.5 rounded text-[11px] font-extrabold bg-[#1B8F6E]/10 text-[#1B8F6E]">
                  Émargement Numérique & Certifié
                </span>
                <span className="text-xs text-slate-400 font-medium">• Contrôle Qualiopi</span>
              </div>
              <h1 className="text-2xl font-extrabold text-[#11162A]">Suivi des Présences</h1>
              <p className="text-slate-600 text-xs mt-1">
                Sélectionnez une session active pour gérer l'émargement et valider la présence des participants inscrits.
              </p>
            </div>

            <div className="flex items-center gap-2 bg-slate-100 p-1 rounded-xl text-xs font-bold shrink-0">
              <button
                onClick={() => setSessionFilter('en_cours')}
                className={`px-3 py-2 rounded-lg transition-all cursor-pointer ${
                  sessionFilter === 'en_cours'
                    ? 'bg-white text-[#11162A] shadow-xs'
                    : 'text-slate-500 hover:text-slate-800'
                }`}
              >
                Sessions Actives ({sessions.filter((s) => s.statut === 'En cours').length})
              </button>
              <button
                onClick={() => setSessionFilter('all')}
                className={`px-3 py-2 rounded-lg transition-all cursor-pointer ${
                  sessionFilter === 'all'
                    ? 'bg-white text-[#11162A] shadow-xs'
                    : 'text-slate-500 hover:text-slate-800'
                }`}
              >
                Toutes ({sessions.length})
              </button>
            </div>
          </div>

          {/* Search Bar */}
          <div className="relative">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
            <input
              type="text"
              value={sessionSearch}
              onChange={(e) => setSessionSearch(e.target.value)}
              placeholder="Rechercher une session par intitulé, code ou formateur..."
              className="w-full pl-10 pr-4 py-2.5 bg-white border border-slate-200 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1B8F6E]"
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
                  className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs hover:border-[#1B8F6E]/40 hover:shadow-md transition-all flex flex-col justify-between"
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
                    <p className="text-[11px] font-semibold text-[#1B8F6E] mt-1">{s.domaine}</p>

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
                          {sessionPresences.length || s.participantsInscrits} / {s.capacityMax}
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
                    className="w-full mt-5 py-2.5 bg-[#11162A] hover:bg-[#1B8F6E] text-white rounded-xl font-bold text-xs shadow-xs transition-colors flex items-center justify-center gap-2 cursor-pointer"
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
              <span>← Retour à la liste des sessions</span>
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

              {/* Add Retained Participant Modal Launcher Button */}
              <button
                onClick={handleOpenAddModal}
                className="px-4 py-2.5 bg-[#1B8F6E] hover:bg-[#16785c] text-white rounded-xl text-xs font-bold flex items-center justify-center gap-2 shadow-sm transition-colors cursor-pointer shrink-0"
              >
                <UserPlus size={16} />
                <span>+ Ajouter un participant retenu</span>
              </button>
            </div>

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
                <div className="text-[10px] uppercase font-bold text-amber-700">Retards</div>
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
              className="w-full pl-10 pr-4 py-2.5 bg-white border border-slate-200 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1B8F6E]"
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
                      onClick={() => handleUpdateStatus(p.id, 'Retard')}
                      className={`px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1 transition-all cursor-pointer ${
                        p.statut === 'Retard'
                          ? 'bg-amber-500 text-white shadow-xs ring-2 ring-amber-500/30 font-extrabold'
                          : 'bg-slate-100 text-slate-600 hover:bg-amber-100 hover:text-amber-800'
                      }`}
                    >
                      <Clock size={14} />
                      <span>Retard</span>
                    </button>
                  </div>
                </div>
              ))}

              {filteredParticipants.length === 0 && (
                <div className="p-8 text-center text-slate-500">
                  <Users size={28} className="mx-auto text-slate-300 mb-2" />
                  <p className="font-bold text-xs text-slate-700">Aucun participant inscrit pour le moment.</p>
                  <p className="text-[11px] text-slate-400 mt-1">
                    Cliquez sur "+ Ajouter un participant retenu" pour l'inscrire à cette session.
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ========================================== */}
      {/* MODAL : AJOUT DE PARTICIPANT RETENU       */}
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
                  <h3 className="text-base font-extrabold text-[#11162A]">Ajouter un Participant Retenu</h3>
                  <p className="text-[11px] text-slate-500">Session : {activeSession.code}</p>
                </div>
              </div>

              <button
                onClick={() => setIsAddParticipantModalOpen(false)}
                className="p-1 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100"
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleAddParticipantSubmit} className="mt-4 space-y-4 text-xs">
              <div>
                <label className="block font-bold text-slate-700 uppercase mb-1">
                  Nom & Prénom de l'apprenant *
                </label>
                <input
                  type="text"
                  required
                  value={newNom}
                  onChange={(e) => setNewNom(e.target.value)}
                  placeholder="ex: Jean-Baptiste Rabe"
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 focus:ring-2 focus:ring-[#1B8F6E] focus:outline-none"
                />
              </div>

              <div>
                <label className="block font-bold text-slate-700 uppercase mb-1">
                  Entreprise / Organisme Client *
                </label>
                <input
                  type="text"
                  required
                  value={newEntreprise}
                  onChange={(e) => setNewEntreprise(e.target.value)}
                  placeholder="ex: TELMA Madagascar / Orange"
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 focus:ring-2 focus:ring-[#1B8F6E] focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-bold text-slate-700 uppercase mb-1">Statut Initial</label>
                  <select
                    value={newStatut}
                    onChange={(e) => setNewStatut(e.target.value as 'Présent' | 'Absent' | 'Retard')}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 font-bold focus:ring-2 focus:ring-[#1B8F6E]"
                  >
                    <option value="Présent">Présent</option>
                    <option value="Retard">Retard</option>
                    <option value="Absent">Absent</option>
                  </select>
                </div>

                <div>
                  <label className="block font-bold text-slate-700 uppercase mb-1">Heure d'émargement</label>
                  <input
                    type="text"
                    value={newHeure}
                    onChange={(e) => setNewHeure(e.target.value)}
                    placeholder="HH:MM"
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 font-mono focus:ring-2 focus:ring-[#1B8F6E]"
                  />
                </div>
              </div>

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
                  className="px-4 py-2 bg-[#1B8F6E] hover:bg-[#16785c] text-white rounded-xl font-bold shadow-xs transition-colors cursor-pointer flex items-center gap-1.5"
                >
                  <Check size={16} />
                  <span>Valider & Inscrire</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
