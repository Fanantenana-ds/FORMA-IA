import React, { useEffect, useState } from 'react';
import { BriefcaseBusiness, Building2, FileText, GraduationCap, Loader2, Plus, Sparkles } from 'lucide-react';
import { apiService } from '../../services/api';

type Tab = 'projets' | 'salles' | 'candidats' | 'syllabus';
const card = 'bg-white p-5 rounded-2xl border border-slate-200 shadow-xs';
const errorMessage = (error: unknown) => error instanceof Error ? error.message : 'La requête a échoué.';

export const ModulesBackendView: React.FC = () => {
  const [tab, setTab] = useState<Tab>('projets');
  const [items, setItems] = useState<any[]>([]);
  const [form, setForm] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const load = async () => {
    const data = tab === 'projets' ? await apiService.getProjects() : tab === 'salles' ? await apiService.getRooms() : tab === 'candidats' ? await apiService.getCandidates() : await apiService.getRagFormations();
    setItems(Array.isArray(data) ? data : data.projets ?? data.salles ?? data.candidats ?? data.data ?? data.formations ?? []);
  };
  useEffect(() => { setError(''); setNotice(''); load().catch(e => setError(errorMessage(e))); }, [tab]);
  const set = (key: string, value: string) => setForm(prev => ({ ...prev, [key]: value }));
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setError(''); setNotice('');
    try {
      if (tab === 'projets') await apiService.createProject({ titre: form.titre, client: form.client || undefined, date_debut: form.date_debut || undefined, date_fin: form.date_fin || undefined, statut: 'BROUILLON', notes: form.notes || undefined });
      if (tab === 'salles') await apiService.createRoom({ nom: form.nom, adresse: form.adresse || undefined, capacite: Number(form.capacite) || undefined, tarif_journalier: Number(form.tarif_journalier) || undefined, equipements: form.equipements || undefined });
      if (tab === 'candidats') await apiService.createCandidate({ nom: form.nom, poste_vise: form.poste_vise, cv_texte: form.cv_texte || undefined });
      setForm({}); setNotice('Enregistré dans le backend.'); await load();
    } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  };
  const generateSyllabus = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setError(''); setNotice('');
    try {
      const rows = (form.modules ?? '').split('\n').map(line => line.trim()).filter(Boolean);
      const modules = rows.map((line, index) => {
        const [titre, duree] = line.split('|').map(part => part.trim());
        if (!titre || !duree) throw new Error(`Ligne ${index + 1} : indiquez le titre et la durée sous la forme « Module | 3h » ou « Module | 1 jour ».`);
        return { titre, duree, contenus: '', methodes: '', objectif_lie: `Module ${index + 1}` };
      });
      if (!modules.length) throw new Error('Ajoutez au moins un module avec sa durée.');
      const result = await apiService.generateSyllabus({ formation_code: form.formation_code, modules, options: { format: form.format ?? 'présentiel' } }) as { _review_id?: string; review_id?: string };
      const reviewId = result._review_id ?? result.review_id;
      setNotice(`Syllabus généré. Il est disponible dans Validation IA${reviewId ? ` (référence ${reviewId})` : ''}.`);
    } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  };
  const generatePortfolio = async () => {
    setBusy(true); setError(''); setNotice('');
    try { const result = await apiService.generatePortfolio({ domaine: form.domaine || null, reference_ao: form.reference_ao || null }) as { _review_id?: string; review_id?: string }; const reviewId = result._review_id ?? result.review_id; setNotice(`Portfolio généré. Consultez Validation IA${reviewId ? ` (référence ${reviewId})` : ''}.`); }
    catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  };
  const runPreselection = async (candidate: any) => {
    setBusy(true); setError(''); setNotice('');
    try {
      const cvTexte = String(candidate.cv_texte ?? form.cv_texte ?? '').trim();
      if (cvTexte.length < 50) throw new Error('Collez le texte du CV (au moins 50 caractères) dans le champ à gauche avant de lancer l’analyse. Le backend ne renvoie pas le CV dans la liste des candidats.');
      const result = await apiService.createOpportunityFromReview('rh/preselection', { cv_texte: cvTexte, criteres_poste: { poste: candidate.poste_vise } }) as { review_id?: string };
      setNotice(`Analyse CV lancée. Consultez Validation IA${result.review_id ? ` (référence ${result.review_id})` : ''}.`);
    }
    catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  };
  const tabs: Array<[Tab, string, React.ReactNode]> = [['projets','Projets & logistique',<BriefcaseBusiness size={15}/>],['salles','Salles',<Building2 size={15}/>],['candidats','Candidats RH',<GraduationCap size={15}/>],['syllabus','Syllabus & portfolio',<FileText size={15}/>]];
  const input = (key: string, label: string, type = 'text', required = false) => <label className="block text-[11px] font-bold uppercase text-slate-600">{label}<input required={required} type={type} value={form[key] ?? ''} onChange={e => set(key,e.target.value)} className="mt-1 w-full px-3 py-2.5 rounded-xl bg-slate-50 border border-slate-300 text-sm font-normal normal-case text-slate-800" /></label>;
  return <div className="space-y-6 animate-in fade-in duration-300">
    <div className={`${card} flex flex-wrap items-center justify-between gap-4`}><div><span className="text-[11px] uppercase tracking-wider font-bold text-[#1B8F6E]">Fonctions complémentaires</span><h1 className="text-2xl font-extrabold text-[#11162A] mt-1">Projets, RH & contenus</h1><p className="text-xs text-slate-500 mt-1">Gestion de base des projets, salles et candidats, avec lancement de contenus IA.</p></div><div className="flex flex-wrap gap-1.5 bg-slate-100 p-1.5 rounded-xl">{tabs.map(([id,label,icon]) => <button key={id} onClick={() => setTab(id)} className={`px-3 py-2 rounded-lg flex items-center gap-1.5 text-xs font-bold ${tab===id?'bg-white text-[#11162A] shadow-xs':'text-slate-500'}`}>{icon}{label}</button>)}</div></div>
    {error && <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs font-semibold">{error}</div>}{notice && <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold">{notice}</div>}
    {tab !== 'syllabus' ? <div className="grid lg:grid-cols-[0.8fr_1.2fr] gap-4"><form onSubmit={submit} className={`${card} space-y-3`}><h2 className="font-extrabold text-[#11162A]">{tab==='projets'?'Nouveau projet':tab==='salles'?'Nouvelle salle':'Nouveau dossier candidat'}</h2>
      {tab==='projets' && <>{input('titre','Intitulé *','text',true)}{input('client','Client')}{input('date_debut','Date de début','date')}{input('date_fin','Date de fin','date')}{input('notes','Notes')}</>}
      {tab==='salles' && <>{input('nom','Nom de la salle *','text',true)}{input('adresse','Adresse')}{input('capacite','Capacité','number')}{input('tarif_journalier','Tarif journalier (Ar)','number')}{input('equipements','Équipements')}</>}
      {tab==='candidats' && <>{input('nom','Nom complet *','text',true)}{input('poste_vise','Poste visé *','text',true)}<label className="block text-[11px] font-bold uppercase text-slate-600">Texte du CV à enregistrer ou analyser<textarea value={form.cv_texte ?? ''} onChange={e=>set('cv_texte',e.target.value)} rows={5} className="mt-1 w-full p-3 rounded-xl bg-slate-50 border border-slate-300 text-sm font-normal normal-case" /></label><button type="button" disabled={busy} onClick={()=>runPreselection({ poste_vise: form.poste_vise })} className="w-full py-2.5 bg-emerald-50 text-emerald-800 rounded-xl text-xs font-bold flex items-center justify-center gap-2"><Sparkles size={14}/>Analyser le CV saisi</button></>}
      <button disabled={busy} className="w-full py-2.5 bg-[#1B8F6E] text-white rounded-xl text-xs font-bold flex justify-center items-center gap-2">{busy?<Loader2 size={15} className="animate-spin"/>:<Plus size={15}/>}Enregistrer</button></form>
      <section className={card}><div className="flex justify-between items-center mb-4"><h2 className="font-extrabold text-[#11162A]">{tab==='projets'?'Projets enregistrés':tab==='salles'?'Salles disponibles':'Dossiers candidats'}</h2><button onClick={()=>load().catch(e=>setError(errorMessage(e)))} className="text-xs text-[#1B8F6E] font-bold">Actualiser</button></div>{items.length?<div className="space-y-2 max-h-[560px] overflow-auto">{items.map((item:any,i)=><div key={item.id??i} className="p-3 rounded-xl border border-slate-200 flex items-center justify-between gap-3"><div><div className="font-bold text-sm text-[#11162A]">{item.titre??item.nom??item.formation_code??'Élément'}</div><div className="text-[11px] text-slate-500 mt-1">{item.client??item.poste_vise??item.adresse??item.statut??''}</div></div>{tab==='candidats'&&item.cv_texte&&<button disabled={busy} onClick={()=>runPreselection(item)} className="px-3 py-2 rounded-lg bg-emerald-50 text-emerald-800 text-[11px] font-bold flex gap-1"><Sparkles size={13}/>Analyser le CV</button>}</div>)}</div>:<p className="text-xs text-slate-500">Aucun élément enregistré.</p>}</section></div> : <div className="grid lg:grid-cols-2 gap-4"><form onSubmit={generateSyllabus} className={`${card} space-y-3`}><h2 className="font-extrabold text-[#11162A]">Générer un syllabus</h2><label className="block text-[11px] font-bold uppercase text-slate-600">Formation du catalogue *<select required value={form.formation_code ?? ''} onChange={e=>set('formation_code',e.target.value)} className="mt-1 w-full px-3 py-2.5 rounded-xl bg-slate-50 border border-slate-300 text-sm font-normal normal-case text-slate-800"><option value="">Sélectionner une formation</option>{items.map((formation:any)=><option key={formation.code} value={formation.code}>{formation.code} — {formation.titre}</option>)}</select></label><label className="block text-[11px] font-bold uppercase text-slate-600">Modules et durées (un par ligne : titre | durée) *<textarea required value={form.modules??''} onChange={e=>set('modules',e.target.value)} rows={5} placeholder={'Introduction | 1 jour\nAtelier pratique | 3h\nÉvaluation | 2h'} className="mt-1 w-full p-3 rounded-xl bg-slate-50 border border-slate-300 text-sm font-normal normal-case"/><span className="block mt-1 text-[10px] font-normal normal-case text-slate-500">Utilisez une durée reconnue comme 3h ou 1 jour; le total est vérifié par le backend.</span></label><button disabled={busy || !items.length} className="px-4 py-2.5 bg-[#1B8F6E] text-white rounded-xl text-xs font-bold flex gap-2 items-center">{busy?<Loader2 size={15} className="animate-spin"/>:<Sparkles size={15}/>}Générer et envoyer en validation</button></form><div className={`${card} space-y-3`}><h2 className="font-extrabold text-[#11162A]">Générer un portfolio</h2>{input('domaine','Domaine (facultatif)')}{input('reference_ao','Référence de l’appel d’offres') }<button disabled={busy} onClick={generatePortfolio} className="px-4 py-2.5 bg-[#11162A] text-white rounded-xl text-xs font-bold flex items-center gap-2"><Sparkles size={15}/>Générer le portfolio et soumettre pour validation</button><p className="text-[11px] text-slate-500">Les contenus générés sont visibles ensuite dans l’onglet Validation IA de l’Espace IA.</p></div></div>}
  </div>;
};

