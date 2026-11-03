import React, { useEffect, useMemo, useState } from 'react';
import { apiService } from '../../services/api';
import type { VoiceActionContext } from '../../services/voiceActionContext';

type Attendance = { id: string; statut: 'PRESENT' | 'ABSENT' | 'RETARD' | 'EXCUSE'; heure_arrivee?: string; motif_absence?: string };
type Person = { id: string; nom: string; prenom?: string };


export const SessionsM5Panel: React.FC<{ sessionId: string; sessionTitle: string; domain?: string; formationCode?: string; formateurId?: string; tauxPresence?: number; participants: Person[]; trainerMode?: boolean; voiceAction?: VoiceActionContext | null }> = ({ sessionId, sessionTitle, domain, formationCode, formateurId, tauxPresence, participants, trainerMode = false, voiceAction }) => {
  const [seances, setSeances] = useState<any[]>([]);
  const [attendance, setAttendance] = useState<Record<string, Attendance>>({});
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [start, setStart] = useState('09:00'); const [end, setEnd] = useState('12:00');
  const [theme, setTheme] = useState(''); const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [notice, setNotice] = useState('');
  const [trainers, setTrainers] = useState<any[]>([]); const [trainer, setTrainer] = useState(formateurId ?? '');
  const [analysis, setAnalysis] = useState<any>(null); const [analysisBusy, setAnalysisBusy] = useState(false);
  const load = async () => {
    const list = await apiService.getSeances(sessionId); setSeances(list);
    const rows = await Promise.all(list.map(async (item: any) => [item.id, await apiService.getPresenceForSession(item.id)] as const));
    const next: Record<string, Attendance> = {};
    rows.forEach(([seanceId, items]) => items.forEach((item: any) => { next[`${seanceId}:${item.participant_id}`] = { id: item.id, statut: item.statut, heure_arrivee: item.heure_arrivee, motif_absence: item.motif_absence }; }));
    setAttendance(next);
  };
  useEffect(() => { setTrainer(formateurId ?? ''); }, [formateurId, sessionId]);
  useEffect(() => { let live = true; Promise.all([apiService.getSeances(sessionId), trainerMode ? Promise.resolve([]) : apiService.getSessionTrainerOptions()]).then(async ([list, staff]) => { if (!live) return; setSeances(list); setTrainers(staff); const rows = await Promise.all(list.map(async (item: any) => [item.id, await apiService.getPresenceForSession(item.id)] as const)); if (!live) return; const next: Record<string, Attendance> = {}; rows.forEach(([sid, items]) => items.forEach((item: any) => { next[`${sid}:${item.participant_id}`] = { id:item.id, statut:item.statut, heure_arrivee:item.heure_arrivee, motif_absence:item.motif_absence }; })); setAttendance(next); }).catch(e => setError(e.message)); return () => { live = false; }; }, [sessionId, trainerMode]);
  const create = async (e: React.FormEvent) => { e.preventDefault(); if (!theme.trim()) return; setBusy(true); setError(''); try { await apiService.createSeance(sessionId, { date, heure_debut:start, heure_fin:end, duree:`${start}–${end}`, theme:theme.trim(), formateur_id:trainerMode ? formateurId : trainer || formateurId || undefined }); await load(); setTheme(''); setNotice('Séance créée pour cette journée de formation.'); } catch(e) { setError(e instanceof Error ? e.message : 'Création séance impossible.'); } finally { setBusy(false); } };
  const save = async (seanceId: string, participantId: string, statut: Attendance['statut'], extra: Partial<Attendance> = {}) => {
    const key = `${seanceId}:${participantId}`, current = attendance[key]; const optimistic = { ...(current ?? { id:'', statut }), statut, ...extra } as Attendance;
    setAttendance(prev => ({ ...prev, [key]: optimistic })); setError(''); setNotice('Enregistrement…');
    try { const data: any = current?.id ? await apiService.updatePresence(current.id, statut, extra) : await apiService.createPresence(seanceId, participantId, statut, extra); setAttendance(prev => ({ ...prev, [key]: { ...optimistic, id: data.id ?? current?.id ?? '' } })); setNotice('Présence enregistrée automatiquement.'); }
    catch(e) { setError(e instanceof Error ? e.message : 'Enregistrement de présence impossible.'); await load().catch(()=>{}); }
  };
  const rate = (personId:string) => { if(!seances.length) return 0; const ok=seances.filter(s=>['PRESENT','RETARD'].includes(attendance[`${s.id}:${personId}`]?.statut)).length; return Math.round(ok/seances.length*100); };
  const analyzeLevels = async () => { setAnalysisBusy(true);setError('');try{const result=await apiService.analyserNiveauxDb(sessionId);if(!result.success){setError(result.message||'Analyse des niveaux impossible.');return;}setAnalysis(result.data??result);}catch(e){setError(e instanceof Error?e.message:'Analyse des niveaux impossible.');}finally{setAnalysisBusy(false);} };
  const analyzeSatisfaction = async () => { setAnalysisBusy(true);setError('');try{const result=await apiService.analyserSatisfactionDb(sessionId);if(!result.success){setError(result.message||'Analyse de satisfaction impossible.');return;}const linkedTrainer=trainers.find((item:any)=>String(item.userId)===String(formateurId));setAnalysis(result.data??result);if(linkedTrainer)setNotice('Analyse liée au profil du formateur. Après validation HITL, son rapport M4 sera généré automatiquement.');}catch(e){setError(e instanceof Error?e.message:'Analyse de satisfaction impossible.');}finally{setAnalysisBusy(false);} };
  useEffect(() => {
    if (!voiceAction) return;
    const data = voiceAction.prefill ?? {};
    if (voiceAction.action === 'ouvrir_formulaire_seance') {
      if (data.date || data.date_seance) setDate(String(data.date ?? data.date_seance));
      if (data.heure_debut || data.heure) setStart(String(data.heure_debut ?? data.heure));
      if (data.heure_fin) setEnd(String(data.heure_fin));
      if (data.theme || data.intitule) setTheme(String(data.theme ?? data.intitule));
      setNotice('Séance préparée dans la session sélectionnée. Vérifiez la date et le thème, puis validez sa création.');
    } else if (voiceAction.action === 'ouvrir_analyse_niveaux') {
      void analyzeLevels();
    } else if (voiceAction.action === 'ouvrir_analyse_satisfaction') {
      void analyzeSatisfaction();
    } else if (voiceAction.action === 'ouvrir_analyse_presences') {
      setNotice('La consultation des présences de cette session est ouverte. L’analyse automatique dédiée n’est pas raccordée à cet écran.');
    } else if (voiceAction.action === 'ouvrir_formulaire_attestation') {
      setNotice('La session est ouverte. Vérifiez les présences et l’éligibilité avant toute génération d’attestations.');
    } else if (voiceAction.action === 'ouvrir_formulaires_session') {
      setNotice('Session sélectionnée. La génération et la publication des formulaires doivent encore être raccordées à cet écran.');
    }
  // Le traitement doit s'exécuter une seule fois par commande vocale.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [voiceAction]);
  const allStatuses = useMemo(() => [{v:'PRESENT',l:'Présent'},{v:'ABSENT',l:'Absent'},{v:'RETARD',l:'Retard'},{v:'EXCUSE',l:'Excusé'}] as const, []);
  const renderAttendanceCell = (seance: any, person: Person) => {
    const current = attendance[`${seance.id}:${person.id}`];
    if (trainerMode) {
      const label = allStatuses.find(status => status.v === current?.statut)?.l ?? 'À saisir';
      return <td key={seance.id} className="p-3"><span className="inline-flex rounded-full bg-slate-100 px-2.5 py-1 font-bold text-slate-700">{label}</span></td>;
    }
    return <td key={seance.id} className="space-y-1 p-2">
      <select value={current?.statut ?? ''} onChange={event => void save(seance.id, person.id, event.target.value as Attendance['statut'])} className="w-full rounded border border-slate-300 bg-white p-2">
        <option value="">À saisir</option>{allStatuses.map(status => <option key={status.v} value={status.v}>{status.l}</option>)}
      </select>
      {current?.statut === 'RETARD' && <input type="time" aria-label="Heure d’arrivée" value={current.heure_arrivee ?? ''} onChange={event => void save(seance.id, person.id, 'RETARD', {heure_arrivee:event.target.value})} className="w-full rounded border p-1.5"/>}
      {current?.statut === 'ABSENT' && <input placeholder="Motif (facultatif)" value={current.motif_absence ?? ''} onChange={event => setAttendance(previous => ({...previous, [`${seance.id}:${person.id}`]: {...current, motif_absence:event.target.value}}))} onBlur={event => void save(seance.id, person.id, 'ABSENT', {motif_absence:event.target.value})} className="w-full rounded border p-1.5"/>}
    </td>;
  };
  return <section className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-xs"><div><h2 className="font-extrabold text-[#11162A]">Séances et présences · M5</h2><p className="mt-1 text-xs text-slate-500">{trainerMode ? 'Ajoutez une séance pour chaque journée de votre formation. Les présences restent consultables.' : 'Créez les séances, puis renseignez les présences par participant. Chaque changement est sauvegardé immédiatement.'}</p></div>
    <form onSubmit={create} className="grid gap-3 rounded-xl bg-slate-50 p-4 md:grid-cols-6"><label className="text-[11px] font-bold text-slate-600">Date<input required type="date" value={date} onChange={e=>setDate(e.target.value)} className="mt-1 w-full rounded-lg border bg-white p-2"/></label><label className="text-[11px] font-bold text-slate-600">Début<input required type="time" value={start} onChange={e=>setStart(e.target.value)} className="mt-1 w-full rounded-lg border bg-white p-2"/></label><label className="text-[11px] font-bold text-slate-600">Fin<input required type="time" value={end} onChange={e=>setEnd(e.target.value)} className="mt-1 w-full rounded-lg border bg-white p-2"/></label><label className="text-[11px] font-bold text-slate-600 md:col-span-2">Thème<input required value={theme} onChange={e=>setTheme(e.target.value)} className="mt-1 w-full rounded-lg border bg-white p-2"/></label>{!trainerMode && <label className="text-[11px] font-bold text-slate-600">Formateur<select value={trainer} onChange={e=>setTrainer(e.target.value)} className="mt-1 w-full rounded-lg border bg-white p-2"><option value="">Formateur de session</option>{trainers.map(t=><option key={t.id ?? t.userId} value={t.id ?? t.userId}>{t.prenom} {t.nom}</option>)}</select></label>}<button disabled={busy} className="rounded-lg bg-[#1B8F6E] px-4 py-2 text-xs font-bold text-white md:col-span-6">{busy?'Création…':'Ajouter une séance'}</button></form>
    {error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-xs text-red-700">{error}</p>}{notice && <p className="text-xs text-emerald-700">{notice}</p>}
    <div className="overflow-x-auto rounded-xl border border-slate-200">
      <table className="min-w-full text-left text-xs">
        <thead className="bg-slate-50 text-slate-600"><tr><th className="p-3">Participant</th><th className="p-3">Taux présence</th>{seances.map(seance => <th key={seance.id} className="min-w-44 p-3">{seance.date}<br/><span className="font-normal">{seance.heure_debut ?? ''} {seance.theme}</span></th>)}</tr></thead>
        <tbody className="divide-y divide-slate-100">{participants.map(person => <tr key={person.id}><td className="p-3 font-semibold">{person.prenom ? `${person.prenom} ` : ''}{person.nom}</td><td className="p-3 font-bold">{rate(person.id)}%</td>{seances.map(seance => renderAttendanceCell(seance, person))}</tr>)}</tbody>
      </table>
    </div>
    {!trainerMode && <div className="grid gap-4 border-t border-slate-100 pt-4 lg:grid-cols-2"><div className="space-y-2 rounded-xl bg-slate-50 p-4"><h3 className="font-bold text-slate-800">Analyser la progression avant / après</h3><p className="text-[11px] text-slate-500">Les scores de positionnement (lien inscription) et de test final (lien post-formation) sont lus directement depuis la base de données.</p><button disabled={analysisBusy} onClick={()=>void analyzeLevels()} className="rounded-lg bg-[#11162A] px-3 py-2 text-xs font-bold text-white disabled:opacity-50">{analysisBusy?'Analyse en cours…':'Analyser les niveaux'}</button></div><div className="space-y-2 rounded-xl bg-slate-50 p-4"><h3 className="font-bold text-slate-800">Analyser la satisfaction</h3><p className="text-[11px] text-slate-500">Les réponses au questionnaire de satisfaction (lien post-formation) sont lues directement depuis la base de données.</p><button disabled={analysisBusy} onClick={()=>void analyzeSatisfaction()} className="rounded-lg bg-[#11162A] px-3 py-2 text-xs font-bold text-white disabled:opacity-50">{analysisBusy?'Analyse en cours…':'Analyser la satisfaction'}</button></div></div>}
    {analysis && <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-xs"><strong>{analysis.resume??'Résultat de l’analyse'}</strong><pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap">{JSON.stringify(analysis,null,2)}</pre></div>}
  </section>;
};
