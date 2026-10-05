import React, { useState, useEffect } from 'react';
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
  UserCheck
} from 'lucide-react';
import { Session, PresenceRecord } from '../../types';

interface SessionsGroupesViewProps {
  sessions: Session[];
  presences?: PresenceRecord[];
  onOpenNewSession: () => void;
}

export const SessionsGroupesView: React.FC<SessionsGroupesViewProps> = ({
  sessions,
  presences: initialPresencesProps = [],
  onOpenNewSession
}) => {
  // Navigation State: null = list of sessions, session ID = detail view
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);

  // Local state for participants across sessions
  const [presencesList, setPresencesList] = useState<PresenceRecord[]>(initialPresencesProps);

  // Sync when props change
  useEffect(() => {
    setPresencesList(initialPresencesProps);
  }, [initialPresencesProps]);

  // Search terms
  const [sessionSearch, setSessionSearch] = useState('');
  const [participantSearch, setParticipantSearch] = useState('');

  // Modal State for adding participant
  const [isAddParticipantModalOpen, setIsAddParticipantModalOpen] = useState(false);
  const [newNom, setNewNom] = useState('');
  const [newEntreprise, setNewEntreprise] = useState('');

  // Selected session object
  const activeSession = sessions.find((s) => s.id === selectedSessionId);

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
  const handleAddParticipantSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newNom || !newEntreprise || !activeSession) return;

    const newRecord: PresenceRecord = {
      id: `pres-${Date.now()}`,
      sessionId: activeSession.id,
      sessionTitle: activeSession.intitule,
      apprenantNom: newNom,
      entreprise: newEntreprise,
      date: new Date().toLocaleDateString('fr-FR'),
      statut: 'Présent'
    };

    setPresencesList((prev) => [newRecord, ...prev]);

    // Reset & close modal
    setNewNom('');
    setNewEntreprise('');
    setIsAddParticipantModalOpen(false);
  };

  // Delete participant from session
  const handleDeleteParticipant = (participantId: string) => {
    setPresencesList((prev) => prev.filter((p) => p.id !== participantId));
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

            <button
              onClick={onOpenNewSession}
              className="px-4 py-2.5 bg-[#1B8F6E] hover:bg-[#16785c] text-white rounded-xl text-xs font-bold flex items-center gap-1.5 shadow-xs transition-colors shrink-0 cursor-pointer"
            >
              <Plus size={16} />
              <span>Créer une session</span>
            </button>
          </div>

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
                  </div>

                  <div className="flex flex-wrap items-center gap-5 pt-3 lg:pt-0 border-t lg:border-t-0 border-slate-100 shrink-0">
                    <div>
                      <div className="text-[10px] font-bold text-slate-400 uppercase">Inscrits / Jauge</div>
                      <div className="text-sm font-extrabold text-[#11162A] mt-0.5">
                        {totalInscrits} / {s.capacityMax}
                      </div>
                      <div className="w-24 bg-slate-100 h-1.5 rounded-full mt-1 overflow-hidden">
                        <div
                          className="bg-[#1B8F6E] h-full rounded-full"
                          style={{ width: `${Math.min(100, (totalInscrits / s.capacityMax) * 100)}%` }}
                        ></div>
                      </div>
                    </div>

                    <div className="text-right">
                      <div className="text-[10px] font-bold text-slate-400 uppercase">Prix par apprenant</div>
                      <div className="text-sm font-extrabold text-[#11162A] mt-0.5">
                        {s.prixUnitaire.toLocaleString()} Ar HT
                      </div>
                    </div>

                    <button
                      onClick={() => setSelectedSessionId(s.id)}
                      className="px-4 py-2.5 bg-[#11162A] hover:bg-[#1B8F6E] text-white rounded-xl text-xs font-bold flex items-center gap-2 shadow-xs transition-colors cursor-pointer"
                    >
                      <Users size={15} />
                      <span>Inscrits ({totalInscrits}) →</span>
                    </button>
                  </div>
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

              {/* Add Participant Modal Trigger */}
              <button
                onClick={() => setIsAddParticipantModalOpen(true)}
                className="px-4 py-2.5 bg-[#1B8F6E] hover:bg-[#16785c] text-white rounded-xl text-xs font-bold flex items-center justify-center gap-2 shadow-sm transition-colors cursor-pointer shrink-0"
              >
                <UserPlus size={16} />
                <span>+ Ajouter un participant retenu</span>
              </button>
            </div>

            {/* Session Stats Bar */}
            <div className="grid grid-cols-3 gap-3 mt-6 pt-5 border-t border-slate-100">
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/80">
                <div className="text-[10px] uppercase font-bold text-slate-500">Participants Inscrits</div>
                <div className="text-xl font-extrabold text-[#11162A] mt-0.5">{sessionParticipants.length}</div>
              </div>

              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/80">
                <div className="text-[10px] uppercase font-bold text-slate-500">Capacité Maximale</div>
                <div className="text-xl font-extrabold text-[#11162A] mt-0.5">{activeSession.capacityMax}</div>
              </div>

              <div className="p-3 bg-emerald-50 rounded-xl border border-emerald-200/80">
                <div className="text-[10px] uppercase font-bold text-emerald-700">Taux de Remplissage</div>
                <div className="text-xl font-extrabold text-emerald-800 mt-0.5">
                  {Math.round((sessionParticipants.length / activeSession.capacityMax) * 100)}%
                </div>
              </div>
            </div>
          </div>

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
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
            <div className="p-4 bg-[#F4F5F3] border-b border-slate-200 font-bold text-xs text-slate-600 uppercase tracking-wider grid grid-cols-12 gap-2 items-center">
              <div className="col-span-5">Apprenant Inscrit</div>
              <div className="col-span-4">Organisme / Entreprise</div>
              <div className="col-span-2">Date d'inscription</div>
              <div className="col-span-1 text-center">Action</div>
            </div>

            <div className="divide-y divide-slate-100">
              {filteredParticipants.map((p) => (
                <div
                  key={p.id}
                  className="p-4 grid grid-cols-12 gap-2 items-center text-xs hover:bg-slate-50 transition-colors"
                >
                  {/* Name */}
                  <div className="col-span-5 flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-[#1B8F6E]/10 text-[#1B8F6E] font-extrabold text-xs flex items-center justify-center shrink-0">
                      {p.apprenantNom.substring(0, 1)}
                    </div>
                    <div>
                      <div className="font-bold text-[#11162A] text-sm">{p.apprenantNom}</div>
                      <div className="text-[10px] text-slate-400 font-mono">ID: {p.id}</div>
                    </div>
                  </div>

                  {/* Company */}
                  <div className="col-span-4 font-semibold text-slate-700 flex items-center gap-1.5">
                    <Building2 size={14} className="text-slate-400" />
                    <span>{p.entreprise}</span>
                  </div>

                  {/* Registration Date */}
                  <div className="col-span-2 text-slate-500 font-mono text-xs">
                    {p.date}
                  </div>

                  {/* Remove Action */}
                  <div className="col-span-1 text-center">
                    <button
                      onClick={() => handleDeleteParticipant(p.id)}
                      title="Retirer ce participant de la session"
                      className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors cursor-pointer"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
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
                <label className="block font-bold text-slate-700 uppercase mb-1">
                  Nom & Prénom de l'apprenant *
                </label>
                <input
                  type="text"
                  required
                  value={newNom}
                  onChange={(e) => setNewNom(e.target.value)}
                  placeholder="ex: Mihaja Rasoanaivo"
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 focus:ring-2 focus:ring-[#1B8F6E] focus:outline-none"
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
                  placeholder="ex: TELMA Madagascar / Orange / BOA"
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 focus:ring-2 focus:ring-[#1B8F6E] focus:outline-none"
                />
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
