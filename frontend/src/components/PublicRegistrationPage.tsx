import React, { useEffect, useState } from 'react';
import { apiService } from '../services/api';

type PublicQuestion = { id: string; competence?: string; enonce: string; options: Array<{ id: string; label: string }> };

export const PublicRegistrationPage: React.FC<{ token: string }> = ({ token }) => {
  const [info, setInfo] = useState<any>(null);
  const [form, setForm] = useState({ nom: '', prenom: '', email: '', organisation: '', poste: '', telephone: '', specialite: '' });
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [satisfactionAnswers, setSatisfactionAnswers] = useState<Record<string, string>>({});
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [done, setDone] = useState('');
  useEffect(() => { apiService.getPublicRegistration(token).then(setInfo).catch(e => setError(e.message)); }, [token]);

  const questions: PublicQuestion[] = info?.assessment?.questions ?? [];
  const postQuestions: PublicQuestion[] = info?.post_formation?.questions ?? [];
  const satisfactionQuestions: Array<{id:string;label:string;type:'rating'|'choice'|'text';options?:string[]}> = info?.post_formation?.satisfaction_questions ?? [];
  const isLearnerFlow = info?.kind === 'participant' || info?.kind === 'post_formation';
  const formationDetails = info?.formation_details ?? {};
  const trainerProfile = typeof formationDetails.formateur_profil === 'string' ? formationDetails.formateur_profil.trim() : '';
  const trainerSkills = Array.isArray(formationDetails.competences_requises) ? formationDetails.competences_requises : [];
  const formatDate = (value: unknown): string => {
    if (typeof value !== 'string' || !value) return 'À confirmer';
    const date = new Date(`${value.slice(0, 10)}T12:00:00`);
    return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' }).format(date);
  };
  const setField = (key: keyof typeof form, value: string) => setForm(previous => ({ ...previous, [key]: value }));
  const detailList = (value: unknown): string[] => Array.isArray(value) ? value.map(item => String(item)).filter(Boolean) : typeof value === 'string' && value.trim() ? [value] : [];

  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true); setError('');
    try {
      let confirmation = 'Votre demande a été enregistrée. Merci.';
      if (info.kind === 'participant') {
        const result = await apiService.submitPublicParticipant(token, {
          nom: form.nom, prenom: form.prenom, email: form.email,
          organisation: form.organisation, poste: form.poste,
          assessment_attempt_id: info.assessment?.attempt_id,
          answers: questions.map(question => ({ question_id: question.id, answer: answers[question.id] ?? '' }))
        });
        confirmation = result.niveau_initial
          ? `Inscription validée. Votre niveau de départ pour cette formation est : ${result.niveau_initial} (${result.score_positionnement}/100).`
          : 'Votre inscription à la formation a été enregistrée.';
      } else if (info.kind === 'post_formation') {
        const result = await apiService.submitPostFormation(token, {
          email: form.email,
          assessment_attempt_id: info.post_formation?.attempt_id,
          answers: postQuestions.map(question => ({ question_id: question.id, answer: answers[question.id] ?? '' })),
          satisfaction_answers: satisfactionQuestions.map(question => ({ question_id: question.id, answer: satisfactionAnswers[question.id] ?? '' }))
        });
        confirmation = `Merci pour votre retour. Votre niveau après formation est ${result.niveau_final} (${result.score_test_final}/100). Votre satisfaction a été enregistrée pour l’évaluation du formateur.`;
      } else {
        if (!file) throw new Error('Sélectionnez votre CV.');
        const result = await apiService.submitPublicTrainer(token, { nom: form.nom, prenom: form.prenom, email: form.email, telephone: form.telephone, specialite: form.specialite, fichier: file });
        confirmation = result.review_id_preselection
          ? 'Votre candidature a été reçue. Le CV a été analysé et les questions d’entretien sont préparées pour l’équipe RH.'
          : 'Votre candidature a été reçue. L’équipe RH analysera votre CV et préparera les questions d’entretien.';
      }
      setDone(confirmation);
    } catch (e) { setError(e instanceof Error ? e.message : 'Envoi impossible.'); }
    finally { setBusy(false); }
  };

  const input = (key: keyof typeof form, label: string, type = 'text') => <label className="block text-sm font-semibold text-slate-700">{label}<input required value={form[key]} type={type} onChange={e => setField(key, e.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 p-3 font-normal" /></label>;

  return <main className="min-h-screen bg-slate-50 px-4 py-10"><div className="mx-auto max-w-2xl rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
    <h1 className="text-2xl font-extrabold text-[#11162A]">{info?.kind === 'participant' ? 'Inscription à une formation' : info?.kind === 'post_formation' ? 'Bilan de fin de formation' : 'Candidature formateur'}</h1>
    {info?.session && isLearnerFlow && <p className="mt-2 text-sm text-slate-600">{info.session.titre} · {info.session.date_debut}{info.session.lieu ? ` · ${info.session.lieu}` : ''}</p>}
    {info && <section className="mt-5 space-y-4 rounded-2xl border border-emerald-200 bg-gradient-to-br from-emerald-50 to-white p-5">
      <div><p className="text-[10px] font-extrabold uppercase tracking-widest text-[#0B1F4D]">{isLearnerFlow ? 'Présentation de la formation' : 'Mission de formation · Poste de formateur'}</p><h2 className="mt-1 text-xl font-extrabold text-[#11162A]">{formationDetails.titre ?? info.session?.titre}</h2>{info.kind === 'formateur' && <p className="mt-2 text-sm text-slate-600">Consultez le cadre de la mission et le profil recherché avant de déposer votre candidature.</p>}</div>
      <div className="grid gap-2 sm:grid-cols-2"><div className="rounded-xl border border-white bg-white/80 p-3"><span className="block text-[10px] font-bold uppercase text-slate-500">Client / organisme</span><strong className="mt-1 block text-sm text-slate-800">{formationDetails.client ?? info.session?.client ?? 'À confirmer'}</strong></div><div className="rounded-xl border border-white bg-white/80 p-3"><span className="block text-[10px] font-bold uppercase text-slate-500">Lieu de la formation</span><strong className="mt-1 block text-sm text-slate-800">{formationDetails.lieu ?? info.session?.lieu ?? 'À confirmer'}</strong></div><div className="rounded-xl border border-white bg-white/80 p-3"><span className="block text-[10px] font-bold uppercase text-slate-500">Début prévu</span><strong className="mt-1 block text-sm text-slate-800">{formatDate(formationDetails.date_debut ?? info.session?.date_debut)}</strong></div><div className="rounded-xl border border-white bg-white/80 p-3"><span className="block text-[10px] font-bold uppercase text-slate-500">Fin prévue</span><strong className="mt-1 block text-sm text-slate-800">{formatDate(formationDetails.date_fin ?? info.session?.date_fin)}</strong></div></div>
      {(formationDetails.contexte || formationDetails.client_description) && <div className="grid gap-3 md:grid-cols-2">{formationDetails.contexte && <div className="rounded-xl bg-white/80 p-3"><h3 className="text-xs font-extrabold text-[#11162A]">{isLearnerFlow ? 'Pourquoi cette formation ?' : 'Contexte de la mission'}</h3><p className="mt-1 whitespace-pre-line text-xs leading-5 text-slate-600">{formationDetails.contexte}</p></div>}{formationDetails.client_description && <div className="rounded-xl bg-white/80 p-3"><h3 className="text-xs font-extrabold text-[#11162A]">{isLearnerFlow ? 'Organisme bénéficiaire' : 'Présentation du client'}</h3><p className="mt-1 whitespace-pre-line text-xs leading-5 text-slate-600">{formationDetails.client_description}</p></div>}</div>}
      {formationDetails.objectif_general && <div className="rounded-xl bg-white/80 p-3"><h3 className="text-xs font-extrabold text-[#11162A]">{isLearnerFlow ? 'But de la formation' : 'Objectif général de la mission'}</h3><p className="mt-1 whitespace-pre-line text-xs leading-5 text-slate-600">{formationDetails.objectif_general}</p></div>}
      {detailList(formationDetails.objectifs_specifiques).length > 0 && <div className="rounded-xl bg-white/80 p-3"><h3 className="text-xs font-extrabold text-[#11162A]">{isLearnerFlow ? 'Ce que vous allez apprendre' : 'Objectifs spécifiques'}</h3><ul className="mt-2 list-disc space-y-1 pl-5 text-xs leading-5 text-slate-600">{detailList(formationDetails.objectifs_specifiques).map((item, index) => <li key={index}>{item}</li>)}</ul></div>}
      {info.kind === 'formateur' && <div className="rounded-xl border border-emerald-100 bg-white p-4"><h3 className="text-sm font-extrabold text-[#11162A]">Profil recherché</h3>{trainerProfile ? <p className="mt-2 whitespace-pre-line text-sm leading-6 text-slate-700">{trainerProfile}</p> : <p className="mt-2 text-sm text-amber-800">Le profil détaillé n’a pas encore été publié pour cette mission. Demandez les critères à l’équipe avant de postuler.</p>}{trainerSkills.length > 0 && <><h4 className="mt-4 text-xs font-bold text-slate-700">Compétences attendues</h4><ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-slate-700">{detailList(trainerSkills).map((item, index) => <li key={index}>{item}</li>)}</ul></>}</div>}
      {isLearnerFlow && detailList(formationDetails.benefices).length > 0 && <div className="rounded-xl bg-white/80 p-3"><h3 className="text-xs font-extrabold text-[#11162A]">Bénéfices pour vous</h3><ul className="mt-2 list-disc space-y-1 pl-5 text-xs leading-5 text-slate-600">{detailList(formationDetails.benefices).map((item, index) => <li key={index}>{item}</li>)}</ul></div>}
    </section>}
    {error && <p className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
    {done ? <p className="mt-6 rounded-lg bg-emerald-50 p-4 font-semibold text-emerald-800">{done}</p> : info && <form onSubmit={submit} className="mt-6 space-y-5">
      <section className="space-y-4">
        <div><div className="text-[11px] font-bold uppercase tracking-wider text-[#0B1F4D]">{info.kind === 'post_formation' ? 'Identification' : 'Étape 1'}</div><h2 className="mt-1 font-extrabold text-[#11162A]">{info.kind === 'post_formation' ? 'Confirmez votre inscription' : 'Vos informations'}</h2></div>
        {info.kind === 'post_formation' ? input('email','E-mail utilisé lors de l’inscription','email') : <>{input('nom','Nom')}{input('prenom','Prénom')}{input('email','E-mail','email')}
        {info.kind === 'participant' ? <>{input('organisation','Organisation / entreprise')}{input('poste','Poste occupé')}</> : <>{input('telephone','Téléphone')}{input('specialite','Spécialité')}<label className="block text-sm font-semibold text-slate-700">CV (PDF, DOCX, DOC, image ou TXT)<input required type="file" accept=".pdf,.docx,.doc,.jpg,.jpeg,.png,.txt" onChange={e => setFile(e.target.files?.[0] ?? null)} className="mt-1 block w-full rounded-lg border border-slate-300 p-3 font-normal" /></label></>}</>}
      </section>

      {info.kind === 'participant' && info.assessment?.enabled && <section className="space-y-4 border-t border-slate-200 pt-5">
        <div><div className="text-[11px] font-bold uppercase tracking-wider text-[#0B1F4D]">Étape 2 · Test de positionnement</div><h2 className="mt-1 font-extrabold text-[#11162A]">Évaluez votre niveau de départ</h2><p className="mt-1 text-xs text-slate-500">Répondez aux questions avant de valider. Ce test aide l’équipe à adapter la formation à votre expérience.</p></div>
        {questions.map((question, index) => <fieldset key={question.id} className="rounded-xl border border-slate-200 p-4"><legend className="px-1 text-sm font-bold text-[#11162A]">{index + 1}. {question.enonce}</legend>{question.competence && <p className="mb-2 text-[10px] font-bold uppercase text-slate-400">{question.competence}</p>}<div className="space-y-2">{question.options.map(option => <label key={option.id} className={`flex cursor-pointer items-start gap-2 rounded-lg border p-2.5 text-sm ${answers[question.id] === option.id ? 'border-[#0B1F4D] bg-emerald-50 text-emerald-950' : 'border-slate-100 hover:bg-slate-50'}`}><input required type="radio" name={question.id} value={option.id} checked={answers[question.id] === option.id} onChange={() => setAnswers(previous => ({ ...previous, [question.id]: option.id }))} className="mt-0.5 accent-[#0B1F4D]"/><span>{option.label}</span></label>)}</div></fieldset>)}
      </section>}

      {info.kind === 'post_formation' && <>
        <section className="space-y-4 border-t border-slate-200 pt-5">
          <div><div className="text-[11px] font-bold uppercase tracking-wider text-[#0B1F4D]">Étape 1 · Évaluation des acquis</div><h2 className="mt-1 font-extrabold text-[#11162A]">Votre niveau après la formation</h2><p className="mt-1 text-xs text-slate-500">Vos réponses seront comparées à votre test initial pour mesurer les acquis.</p></div>
          {postQuestions.map((question, index) => <fieldset key={question.id} className="rounded-xl border border-slate-200 p-4"><legend className="px-1 text-sm font-bold text-[#11162A]">{index + 1}. {question.enonce}</legend><div className="space-y-2">{question.options.map(option => <label key={option.id} className={`flex cursor-pointer items-start gap-2 rounded-lg border p-2.5 text-sm ${answers[question.id] === option.id ? 'border-[#0B1F4D] bg-emerald-50 text-emerald-950' : 'border-slate-100 hover:bg-slate-50'}`}><input required type="radio" name={question.id} value={option.id} checked={answers[question.id] === option.id} onChange={() => setAnswers(previous => ({ ...previous, [question.id]: option.id }))} className="mt-0.5 accent-[#0B1F4D]"/><span>{option.label}</span></label>)}</div></fieldset>)}
        </section>
        <section className="space-y-4 border-t border-slate-200 pt-5">
          <div><div className="text-[11px] font-bold uppercase tracking-wider text-[#0B1F4D]">Étape 2 · Enquête de satisfaction</div><h2 className="mt-1 font-extrabold text-[#11162A]">Évaluez votre expérience</h2><p className="mt-1 text-xs text-slate-500">Vos réponses contribuent à l’évaluation du formateur pour les prochaines formations.</p></div>
          {satisfactionQuestions.map(question => <label key={question.id} className="block rounded-xl border border-slate-200 p-4 text-sm font-semibold text-[#11162A]">{question.label}{question.type === 'rating' ? <select required value={satisfactionAnswers[question.id] ?? ''} onChange={event => setSatisfactionAnswers(previous => ({ ...previous, [question.id]: event.target.value }))} className="mt-2 w-full rounded-lg border border-slate-300 bg-white p-2.5 text-sm font-normal"><option value="">Choisissez une note</option>{[1,2,3,4,5].map(value => <option key={value} value={value}>{value} / 5{value === 1 ? ' · Insuffisant' : value === 5 ? ' · Excellent' : ''}</option>)}</select> : question.type === 'choice' ? <div className="mt-2 flex gap-2">{(question.options ?? []).map(option => <label key={option} className={`flex flex-1 cursor-pointer items-center gap-2 rounded-lg border p-2.5 font-normal ${satisfactionAnswers[question.id] === option ? 'border-[#0B1F4D] bg-emerald-50' : 'border-slate-200'}`}><input required type="radio" name={question.id} value={option} checked={satisfactionAnswers[question.id] === option} onChange={() => setSatisfactionAnswers(previous => ({ ...previous, [question.id]: option }))} className="accent-[#0B1F4D]"/>{option}</label>)}</div> : <textarea value={satisfactionAnswers[question.id] ?? ''} onChange={event => setSatisfactionAnswers(previous => ({ ...previous, [question.id]: event.target.value }))} rows={3} maxLength={1500} className="mt-2 w-full rounded-lg border border-slate-300 p-3 text-sm font-normal" placeholder="Facultatif"/>}</label>)}
        </section>
      </>}

      <button disabled={busy} className="w-full rounded-lg bg-[#0B1F4D] p-3 font-bold text-white disabled:opacity-50">{busy ? 'Envoi et analyse…' : info.kind === 'participant' ? 'Valider mon inscription et mon test' : info.kind === 'post_formation' ? 'Envoyer mon bilan et ma satisfaction' : 'Envoyer ma candidature'}</button>
    </form>}
  </div></main>;
};
