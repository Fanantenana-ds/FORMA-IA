import React, { useEffect, useMemo, useState } from 'react';
import { apiService } from '../../services/api';

type Attendance = { id: string; statut: 'PRESENT' | 'ABSENT' | 'RETARD' | 'EXCUSE'; heure_arrivee?: string; motif_absence?: string };
type Person = { id: string; nom: string; prenom?: string };

const parseCsv = (text: string) => {
  const rows: string[][] = []; let row: string[] = []; let cell = ''; let quoted = false;
  for (let i=0;i<text.length;i++) { const c=text[i]; if(c==='"'&&text[i+1]==='"'&&quoted){cell+='"';i++;} else if(c==='"') quoted=!quoted; else if(c===','&&!quoted){row.push(cell.trim());cell='';} else if((c==='\n'||c==='\r')&&!quoted){if(c==='\r'&&text[i+1]==='\n')i++;row.push(cell.trim());if(row.some(Boolean))rows.push(row);row=[];cell='';} else cell+=c; }
  row.push(cell.trim()); if(row.some(Boolean)) rows.push(row);
  if(rows.length<2) return [];
  const headers=rows[0].map(h=>h.replace(/^\uFEFF/,''));
  return rows.slice(1).map(r=>Object.fromEntries(headers.map((h,i)=>[h,r[i]??''])));
};

export const SessionsM5Panel: React.FC<{ sessionId: string; sessionTitle: string; domain?: string; formationCode?: string; formateurId?: string; tauxPresence?: number; participants: Person[]; trainerMode?: boolean }> = ({ sessionId, sessionTitle, domain, formationCode, formateurId, tauxPresence, participants, trainerMode = false }) => {
  const [seances, setSeances] = useState<any[]>([]);
  const [attendance, setAttendance] = useState<Record<string, Attendance>>({});
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [start, setStart] = useState('09:00'); const [end, setEnd] = useState('12:00');
  const [theme, setTheme] = useState(''); const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [notice, setNotice] = useState('');
  const [trainers, setTrainers] = useState<any[]>([]); const [trainer, setTrainer] = useState(formateurId ?? '');
  const [beforeCsv, setBeforeCsv] = useState<File | null>(null); const [afterCsv, setAfterCsv] = useState<File | null>(null); const [satisfactionCsv, setSatisfactionCsv] = useState<File | null>(null);
  const [answerKeyText, setAnswerKeyText] = useState('{}'); const [analysis, setAnalysis] = useState<any>(null); const [analysisBusy, setAnalysisBusy] = useState(false);
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
  const analyzeLevels = async () => { if(!beforeCsv||!afterCsv) return; setAnalysisBusy(true);setError('');try { const before=parseCsv(await beforeCsv.text()),after=parseCsv(await afterCsv.text()); const keyOf=(r:any)=>String(r.email??r.Email??r.nom??r.Nom??r.name??r.Name??'').trim().toLowerCase(); const afterByKey=new Map(after.map(r=>[keyOf(r),r])); const ignored=new Set(['email','nom','name','prenom','organisation','entreprise','timestamp','horodateur']); const participants=before.map((r,i)=>{const post=afterByKey.get(keyOf(r))??after[i]??{};const answers=(source:any)=>Object.fromEntries(Object.entries(source).filter(([k,v])=>!ignored.has(k.toLowerCase())&&String(v).trim()).map(([k,v])=>[k,String(v)]));return {id:i+1,nom:r.nom??r.Nom??r.name??r.Name??r.email??`Participant ${i+1}`,reponses_avant:answers(r),reponses_apres:answers(post)};});const corrige=JSON.parse(answerKeyText);const result=await apiService.analyzeFormationLevels({session_info:{session_id:sessionId,titre:sessionTitle,formation_code:formationCode,domaine:domain??'Formation'},participants,corrige});setAnalysis(result.data??result);}catch(e){setError(e instanceof Error?e.message:'Analyse des niveaux impossible.');}finally{setAnalysisBusy(false);} };
  const analyzeSatisfaction = async () => { if(!satisfactionCsv) return;setAnalysisBusy(true);setError('');try{const responses=parseCsv(await satisfactionCsv.text()).map(r=>Object.fromEntries(Object.entries(r).map(([k,v])=>[k.toLowerCase().replaceAll(' ','_'),v])));const linkedTrainer=trainers.find((item:any)=>String(item.userId)===String(formateurId));const result=await apiService.analyzeFormationSatisfaction({session_info:{session_id:sessionId,titre:sessionTitle,formation_code:formationCode,domaine:domain??'Formation',taux_presence:tauxPresence,...(linkedTrainer?{formateur_id:linkedTrainer.id,formateur_nom:`${linkedTrainer.prenom??''} ${linkedTrainer.nom}`.trim()}:{})},responses});setAnalysis(result.data??result);if(linkedTrainer)setNotice('Analyse liée au profil du formateur. Après validation HITL, son rapport M4 sera généré automatiquement.');}catch(e){setError(e instanceof Error?e.message:'Analyse de satisfaction impossible.');}finally{setAnalysisBusy(false);} };
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
    {!trainerMode && <div className="grid gap-4 border-t border-slate-100 pt-4 lg:grid-cols-2"><div className="space-y-2 rounded-xl bg-slate-50 p-4"><h3 className="font-bold text-slate-800">Analyser la progression avant / après</h3><p className="text-[11px] text-slate-500">Importez les deux exports CSV. Saisissez le corrigé JSON avec les identifiants des colonnes de questions.</p><input type="file" accept=".csv,text/csv" onChange={e=>setBeforeCsv(e.target.files?.[0]??null)} className="block w-full text-xs"/><input type="file" accept=".csv,text/csv" onChange={e=>setAfterCsv(e.target.files?.[0]??null)} className="block w-full text-xs"/><textarea value={answerKeyText} onChange={e=>setAnswerKeyText(e.target.value)} rows={2} placeholder={'{"av_01":"A"}'} className="w-full rounded border p-2 font-mono text-xs"/><button disabled={!beforeCsv||!afterCsv||analysisBusy} onClick={()=>void analyzeLevels()} className="rounded-lg bg-[#11162A] px-3 py-2 text-xs font-bold text-white disabled:opacity-50">Analyser les niveaux</button></div><div className="space-y-2 rounded-xl bg-slate-50 p-4"><h3 className="font-bold text-slate-800">Analyser la satisfaction</h3><p className="text-[11px] text-slate-500">Importez le CSV des réponses Google Forms.</p><input type="file" accept=".csv,text/csv" onChange={e=>setSatisfactionCsv(e.target.files?.[0]??null)} className="block w-full text-xs"/><button disabled={!satisfactionCsv||analysisBusy} onClick={()=>void analyzeSatisfaction()} className="rounded-lg bg-[#11162A] px-3 py-2 text-xs font-bold text-white disabled:opacity-50">Analyser la satisfaction</button></div></div>}
    {analysis && <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-xs"><strong>{analysis.resume??'Résultat de l’analyse'}</strong><pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap">{JSON.stringify(analysis,null,2)}</pre></div>}
  </section>;
};
