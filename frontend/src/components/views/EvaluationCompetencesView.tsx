import React, { useEffect, useState } from 'react';
import { Award, CheckCircle2, Star, BarChart2, ThumbsUp, Info, Clock, Sparkles, TrendingUp } from 'lucide-react';
import { Formateur } from '../../types';
import { formateurFullName, specialitesList } from '../../services/formateurMapping';
import { apiService } from '../../services/api';

interface EvaluationCompetencesViewProps {
  formateurs: Formateur[];
}

const scoreColor = (score: number): string =>
  score >= 75 ? 'text-emerald-700' : score >= 50 ? 'text-amber-700' : 'text-red-600';

const scoreBar = (score: number): string =>
  score >= 75 ? 'bg-emerald-500' : score >= 50 ? 'bg-amber-500' : 'bg-red-500';

const recommandationStyle = (reco: string): string => {
  const r = reco.toLowerCase();
  return r === 'oui'
    ? 'bg-emerald-100 text-emerald-800'
    : r === 'non'
    ? 'bg-red-100 text-red-700'
    : 'bg-amber-100 text-amber-800';
};

export const EvaluationCompetencesView: React.FC<EvaluationCompetencesViewProps> = ({ formateurs }) => {
  const [activeTab, setActiveTab] = useState<'matrice' | 'par_formateur'>('par_formateur');
  const [selectedFormateurId, setSelectedFormateurId] = useState<string>('');
  const [sessionTitle, setSessionTitle] = useState('');
  const [satisfactionScore, setSatisfactionScore] = useState('');
  const [attendanceRate, setAttendanceRate] = useState('');
  const [evaluationReport, setEvaluationReport] = useState('');
  const [evaluationBusy, setEvaluationBusy] = useState(false);
  const [evaluationError, setEvaluationError] = useState('');
  const [evaluationNotice, setEvaluationNotice] = useState('');
  const [evaluationReviewId, setEvaluationReviewId] = useState('');
  const [approvedEvaluations, setApprovedEvaluations] = useState<any[]>([]);
  const [satisfactionFeedback, setSatisfactionFeedback] = useState<any[]>([]);
  const [historyBusy, setHistoryBusy] = useState(false);

  // Matrice d'acquisition par module : sera alimentée par le backend (aucune donnée pour l'instant)
  const competencesData: { module: string; acquise: number; participants: number }[] = [];

  const evalues = formateurs.filter((f) => f.scoreMoyen !== undefined);
  const scoreMoyenGlobal = evalues.length
    ? evalues.reduce((acc, f) => acc + (f.scoreMoyen ?? 0), 0) / evalues.length
    : null;
  const recommandes = formateurs.filter((f) => f.recommandation?.toLowerCase() === 'oui').length;

  const currentFormateur =
    formateurs.find((f) => f.id === selectedFormateurId) ?? formateurs[0];

  useEffect(() => {
    let cancelled = false;
    apiService.getTrainerSatisfactionResponses()
      .then(rows => { if (!cancelled) setSatisfactionFeedback(rows); })
      .catch(() => { if (!cancelled) setSatisfactionFeedback([]); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const loadApprovedEvaluations = async () => {
      if (!currentFormateur) { setApprovedEvaluations([]); return; }
      setHistoryBusy(true);
      try {
        const history = await apiService.getReviewHistory('approved', 'agent_m4_evaluation');
        const trainerName = formateurFullName(currentFormateur).trim().toLocaleLowerCase();
        const related = (history.reviews ?? []).filter((review: any) =>
          String(review.meta?.formateur_id ?? '') === currentFormateur.id ||
          (!review.meta?.formateur_id && String(review.summary ?? '').toLocaleLowerCase().includes(trainerName))
        );
        const details = await Promise.all(related.map(async (review: any) => {
          try {
            const response = await apiService.getReview(String(review.review_id));
            return response.review ?? response.data ?? response;
          } catch { return review; }
        }));
        if (!cancelled) setApprovedEvaluations(details);
      } catch {
        if (!cancelled) setApprovedEvaluations([]);
      } finally { if (!cancelled) setHistoryBusy(false); }
    };
    void loadApprovedEvaluations();
    return () => { cancelled = true; };
  }, [currentFormateur?.id, formateurs]);

  const generateEvaluation = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!currentFormateur) return;
    setEvaluationBusy(true); setEvaluationError(''); setEvaluationNotice('');
    try {
      const result = await apiService.evaluateTrainer({
        formateur: formateurFullName(currentFormateur), formateur_id: currentFormateur.id, session: sessionTitle.trim(),
        donnees_session: {
          satisfaction: satisfactionScore ? { score_moyen: Number(satisfactionScore), points_positifs: [], points_negatifs: [] } : undefined,
          presences: attendanceRate ? { taux_moyen_pct: Number(attendanceRate), anomalies: [] } : undefined,
          rapport: evaluationReport.trim() || undefined
        }
      });
      if (!result.review_id) throw new Error(result.message || 'Le backend n’a pas retourné de dossier de validation.');
      setEvaluationReviewId(result.review_id);
      setEvaluationNotice(`Évaluation préparée (${result.review_id}). Après validation dans Espace IA, elle sera automatiquement ajoutée à cette synthèse.`);
    } catch (error) { setEvaluationError(error instanceof Error ? error.message : 'Évaluation IA impossible.'); }
    finally { setEvaluationBusy(false); }
  };

  const currentTrainerFeedback = satisfactionFeedback.filter(item => String(item.formateur_id ?? '') === String(currentFormateur?.id ?? ''));
  const ratingDimensions = [
    { id: 'sat_1', label: 'Maîtrise du sujet' },
    { id: 'sat_2', label: 'Clarté des explications' },
    { id: 'sat_3', label: 'Exercices pratiques' },
    { id: 'sat_4', label: 'Écoute et disponibilité' },
    { id: 'sat_5', label: 'Objectifs atteints' },
  ].map(dimension => {
    const ratings = currentTrainerFeedback.flatMap(feedback => (feedback.reponses_satisfaction ?? [])
      .filter((answer: any) => answer.question_id === dimension.id)
      .map((answer: any) => Number(answer.answer))
      .filter((score: number) => Number.isFinite(score) && score >= 1 && score <= 5));
    return { ...dimension, average: ratings.length ? ratings.reduce((sum, score) => sum + score, 0) / ratings.length : null };
  });
  const ratedFeedback = currentTrainerFeedback.filter(item => item.score_satisfaction != null);
  const meanSatisfaction = ratedFeedback.length
    ? ratedFeedback.reduce((sum, item) => sum + Number(item.score_satisfaction), 0) / ratedFeedback.length
    : NaN;
  const reviewData = approvedEvaluations.map(review => review.data ?? review);
  const listOf = (value: unknown): string[] => Array.isArray(value)
    ? value.map(item => typeof item === 'string' ? item : String((item as any)?.point ?? (item as any)?.description ?? '')).filter(Boolean)
    : typeof value === 'string' && value.trim() ? [value.trim()] : [];
  const narrativeCandidates = [currentFormateur?.notesInternes,
    ...reviewData.flatMap(data => [data.synthese_globale, data.synthese, data.resume, data.justification_recommandation, data.conclusion])]
    .filter((value): value is string => typeof value === 'string' && value.trim().length > 0);
  const aiNarratives = [...new Set(narrativeCandidates)];
  const aiStrengths = [...new Set(reviewData.flatMap(data => listOf(data.points_forts_session ?? data.points_forts ?? data.points_positifs ?? data.recommandations)))].slice(0, 3);
  const aiImprovements = [...new Set(reviewData.flatMap(data => listOf(data.axes_amelioration ?? data.points_negatifs ?? data.axes_de_progression)))].slice(0, 3);
  const levelOrder: Record<string, number> = { 'Débutant': 1, 'Intermédiaire': 2, 'Normal': 3, 'Avancé': 4, 'Expert': 5 };
  const progressionCount = currentTrainerFeedback.filter(item => levelOrder[item.niveau_final] > levelOrder[item.niveau_initial]).length;

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Header Banner */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2.5 py-0.5 rounded text-[11px] font-extrabold bg-[#1B8F6E]/10 text-[#1B8F6E]">
              Assurance Qualité
            </span>
            <span className="text-xs text-slate-400 font-medium">• Évaluation des formateurs</span>
          </div>
          <h1 className="text-2xl font-extrabold text-[#11162A]">Évaluation & Compétences</h1>
          <p className="text-slate-600 text-xs mt-1">
            Résultats d'évaluation post-session des formateurs (score global et recommandation) et suivi des acquis.
          </p>
        </div>

        {/* Tab Selector */}
        <div className="flex items-center gap-1.5 bg-slate-100 p-1.5 rounded-xl text-xs font-bold shrink-0">
          <button
            onClick={() => setActiveTab('par_formateur')}
            className={`px-4 py-2.5 rounded-lg transition-all flex items-center gap-2 cursor-pointer ${
              activeTab === 'par_formateur' ? 'bg-[#1B8F6E] text-white shadow-xs' : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            <Star size={15} />
            <span>Par formateur</span>
          </button>
          <button
            onClick={() => setActiveTab('matrice')}
            className={`px-4 py-2.5 rounded-lg transition-all flex items-center gap-2 cursor-pointer ${
              activeTab === 'matrice' ? 'bg-[#1B8F6E] text-white shadow-xs' : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            <BarChart2 size={15} />
            <span>Matrice d'acquisition</span>
          </button>
        </div>
      </div>

      {/* Stats globales */}
      <form onSubmit={generateEvaluation} className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-3">
        <div><h2 className="font-extrabold text-[#11162A]">Nouvelle évaluation post-session (M4)</h2><p className="text-xs text-slate-500 mt-1">Saisissez les résultats M5 disponibles. Le contenu généré doit être validé dans Espace IA.</p></div>
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-3">
          <label className="text-[11px] font-bold text-slate-600">Formateur<select required value={currentFormateur?.id ?? ''} onChange={e => setSelectedFormateurId(e.target.value)} className="mt-1 w-full p-2.5 rounded-xl border border-slate-300 bg-slate-50 text-sm">{formateurs.map(f => <option key={f.id} value={f.id}>{formateurFullName(f)}</option>)}</select></label>
          <label className="text-[11px] font-bold text-slate-600">Session<input required minLength={2} value={sessionTitle} onChange={e => setSessionTitle(e.target.value)} className="mt-1 w-full p-2.5 rounded-xl border border-slate-300 bg-slate-50 text-sm" placeholder="Intitulé de la session" /></label>
          <label className="text-[11px] font-bold text-slate-600">Satisfaction moyenne<input type="number" min="0" max="100" step="0.1" value={satisfactionScore} onChange={e => setSatisfactionScore(e.target.value)} className="mt-1 w-full p-2.5 rounded-xl border border-slate-300 bg-slate-50 text-sm" placeholder="0 à 100" /></label>
          <label className="text-[11px] font-bold text-slate-600">Présence moyenne (%)<input type="number" min="0" max="100" step="0.1" value={attendanceRate} onChange={e => setAttendanceRate(e.target.value)} className="mt-1 w-full p-2.5 rounded-xl border border-slate-300 bg-slate-50 text-sm" placeholder="0 à 100" /></label>
        </div>
        <textarea value={evaluationReport} onChange={e => setEvaluationReport(e.target.value)} rows={2} placeholder="Extrait du rapport de session (facultatif)" className="w-full p-3 rounded-xl border border-slate-300 bg-slate-50 text-sm" />
        {evaluationError && <div role="alert" className="text-xs text-red-700 font-semibold">{evaluationError}</div>}{evaluationNotice && <div className="text-xs text-emerald-800 font-semibold">{evaluationNotice}</div>}
        <div className="flex flex-wrap items-center gap-2"><button type="submit" disabled={evaluationBusy || !currentFormateur} className="px-4 py-2.5 rounded-xl bg-[#1B8F6E] text-white text-xs font-bold disabled:opacity-50">{evaluationBusy ? 'Traitement…' : 'Générer une évaluation IA'}</button>{evaluationReviewId && <span className="rounded-xl bg-amber-50 px-3 py-2.5 text-xs font-bold text-amber-800">En attente de validation dans l’Espace IA · {evaluationReviewId}</span>}</div>
      </form>

      {/* Stats globales */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs">
          <div className="text-3xl font-extrabold text-[#11162A]">
            {scoreMoyenGlobal !== null ? `${Math.round(scoreMoyenGlobal)} / 100` : '—'}
          </div>
          <div className="text-xs font-bold text-slate-500 uppercase mt-1">Score moyen</div>
          <p className="text-[11px] text-emerald-600 mt-1 font-semibold">Moyenne des formateurs évalués</p>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs">
          <div className="text-3xl font-extrabold text-[#11162A]">
            {evalues.length} / {formateurs.length}
          </div>
          <div className="text-xs font-bold text-slate-500 uppercase mt-1">Formateurs évalués</div>
          <p className="text-[11px] text-[#1B8F6E] mt-1 font-semibold">Au moins une évaluation enregistrée</p>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs">
          <div className="text-3xl font-extrabold text-[#11162A]">{recommandes}</div>
          <div className="text-xs font-bold text-slate-500 uppercase mt-1">Recommandés</div>
          <p className="text-[11px] text-blue-600 mt-1 font-semibold">Recommandation « Oui »</p>
        </div>
      </div>

      {/* ONGLET 1 : PAR FORMATEUR */}
      {activeTab === 'par_formateur' && (
        <div className="space-y-6">
          {formateurs.length === 0 && (
            <div className="bg-white p-8 rounded-2xl border border-slate-200 text-center text-slate-500">
              <p className="font-bold text-xs text-slate-700">Aucun formateur enregistré pour le moment.</p>
            </div>
          )}

          {formateurs.length > 0 && (
            <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-xs flex items-center gap-3">
              <span className="text-xs font-bold text-slate-500 uppercase shrink-0">Choisir le formateur :</span>
              <select
                value={currentFormateur?.id ?? ''}
                onChange={(e) => setSelectedFormateurId(e.target.value)}
                className="w-full md:w-72 p-2.5 bg-slate-50 border border-slate-200 rounded-xl font-bold text-xs text-[#11162A] focus:ring-2 focus:ring-[#1B8F6E] focus:outline-none"
              >
                {formateurs.map((f) => (
                  <option key={f.id} value={f.id}>
                    {formateurFullName(f)}
                    {f.scoreMoyen !== undefined ? ` (${Math.round(f.scoreMoyen)}/100)` : ''}
                  </option>
                ))}
              </select>
            </div>
          )}

          {currentFormateur && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Fiche du formateur */}
              <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-5">
                <div className="text-center space-y-3">
                  <div className="w-20 h-20 rounded-2xl mx-auto bg-[#1B8F6E] text-white flex items-center justify-center text-2xl font-extrabold shadow-md">
                    {formateurFullName(currentFormateur).charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <h2 className="text-lg font-extrabold text-[#11162A]">{formateurFullName(currentFormateur)}</h2>
                    <p className="text-xs text-slate-500 font-medium">{currentFormateur.email ?? 'Email non renseigné'}</p>
                  </div>

                  {currentFormateur.scoreMoyen !== undefined ? (
                    <>
                      <div className="inline-flex items-baseline gap-2 bg-slate-50 px-4 py-2 rounded-xl border border-slate-200">
                        <span className={`text-3xl font-black ${scoreColor(currentFormateur.scoreMoyen)}`}>
                          {Math.round(currentFormateur.scoreMoyen)}
                        </span>
                        <span className="text-xs font-bold text-slate-500">/ 100</span>
                      </div>
                      <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full ${scoreBar(currentFormateur.scoreMoyen)}`}
                          style={{ width: `${Math.min(100, Math.max(0, currentFormateur.scoreMoyen))}%` }}
                        ></div>
                      </div>
                    </>
                  ) : (
                    <div className="text-xs font-bold text-slate-400 bg-slate-50 px-4 py-2 rounded-xl border border-slate-200">
                      Pas encore évalué
                    </div>
                  )}
                </div>

                <div className="space-y-2 pt-4 border-t border-slate-100 text-xs">
                  {currentFormateur.recommandation && (
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-slate-600 flex items-center gap-1.5">
                        <ThumbsUp size={13} /> Recommandation
                      </span>
                      <span className={`px-2 py-0.5 rounded text-[11px] font-bold ${recommandationStyle(currentFormateur.recommandation)}`}>
                        {currentFormateur.recommandation}
                      </span>
                    </div>
                  )}
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-slate-600 flex items-center gap-1.5">
                      <Clock size={13} /> Sessions
                    </span>
                    <span className="font-extrabold text-[#11162A]">
                      {currentFormateur.nbSessions !== undefined ? currentFormateur.nbSessions : '—'}
                    </span>
                  </div>
                </div>

                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs text-slate-600 space-y-1">
                  <div className="font-bold text-slate-800">Spécialités :</div>
                  <div className="flex flex-wrap gap-1">
                    {specialitesList(currentFormateur).map((s, idx) => (
                      <span key={idx} className="bg-white border border-slate-200 px-2 py-0.5 rounded text-[11px] font-semibold">
                        {s}
                      </span>
                    ))}
                    {specialitesList(currentFormateur).length === 0 && (
                      <span className="text-slate-400">Non renseignées</span>
                    )}
                  </div>
                </div>

                <section className="rounded-xl border border-violet-200 bg-gradient-to-br from-violet-50 via-white to-emerald-50 p-3.5 space-y-3">
                  <div className="flex items-center gap-2"><Sparkles size={15} className="text-violet-600"/><h3 className="text-xs font-extrabold text-[#11162A]">Résumé IA global</h3></div>
                  <div className="space-y-2"><p className="text-[11px] leading-relaxed text-slate-700">Sur {new Set(currentTrainerFeedback.map(item => item.session_id)).size || approvedEvaluations.length} session(s) évaluée(s), la note moyenne de satisfaction est {Number.isFinite(meanSatisfaction) ? `${meanSatisfaction.toFixed(1)} / 5` : currentFormateur.scoreMoyen != null ? `${Math.round(currentFormateur.scoreMoyen)} / 100` : 'en cours de collecte'}. {progressionCount > 0 ? `${progressionCount} participant(s) ont progressé entre le test initial et le test final.` : ''}</p>{aiNarratives.map((narrative, index) => <p key={index} className="rounded-lg border border-violet-100 bg-white/80 p-2.5 text-[11px] leading-relaxed text-slate-700">{narrative}</p>)}{aiNarratives.length === 0 && <p className="text-[10px] italic text-slate-500">Aucune synthèse IA validée n’est encore disponible. Le résumé chiffré et les graphiques ci-dessous regroupent les retours reçus.</p>}{aiStrengths.length > 0 && <p className="text-[11px] leading-relaxed text-slate-700"><strong className="text-emerald-800">Points forts récurrents :</strong> {aiStrengths.join(' · ')}</p>}{aiImprovements.length > 0 && <p className="text-[11px] leading-relaxed text-slate-700"><strong className="text-amber-800">À renforcer :</strong> {aiImprovements.join(' · ')}</p>}<p className="text-[9px] font-semibold text-violet-700">Consolidation de {approvedEvaluations.length} synthèse(s) IA validée(s) et des retours de {currentTrainerFeedback.length} apprenant(s).</p></div>
                  <div className="border-t border-violet-100 pt-3">
                    <div className="mb-2 flex items-center justify-between"><span className="text-[10px] font-extrabold uppercase tracking-wide text-slate-500">Compétences perçues</span><span className="text-[10px] font-bold text-slate-500">Moyenne / 5</span></div>
                    <div className="space-y-2">{ratingDimensions.map(dimension => <div key={dimension.id}><div className="mb-1 flex items-center justify-between gap-2 text-[10px]"><span className="truncate font-semibold text-slate-600">{dimension.label}</span><span className="shrink-0 font-extrabold text-[#11162A]">{dimension.average != null ? `${dimension.average.toFixed(1)} / 5` : '—'}</span></div><div className="h-1.5 overflow-hidden rounded-full bg-slate-200"><div className={`h-full rounded-full ${dimension.average == null ? 'bg-slate-300' : dimension.average >= 4 ? 'bg-emerald-500' : dimension.average >= 3 ? 'bg-amber-500' : 'bg-rose-500'}`} style={{ width: `${dimension.average == null ? 0 : dimension.average / 5 * 100}%` }}/></div></div>)}</div>
                  </div>
                  <div className="flex items-center justify-between rounded-lg bg-white/80 px-2.5 py-2"><div className="flex items-center gap-1.5 text-[10px] font-bold text-slate-600"><TrendingUp size={13} className="text-[#1B8F6E]"/> Progression constatée</div><strong className="text-xs text-[#11162A]">{progressionCount} / {currentTrainerFeedback.length} apprenant(s)</strong></div>
                  {ratedFeedback.length > 0 && <div className="text-[9px] text-slate-400">Basé sur {ratedFeedback.length} enquête(s) reçue(s).</div>}
                </section>
              </div>

              {/* Synthèse de l'évaluation */}
              <div className="lg:col-span-2 space-y-4">
                <h3 className="text-base font-extrabold text-[#11162A] flex items-center gap-2">
                  <Award size={18} className="text-[#1B8F6E]" />
                  Synthèse de l'évaluation
                </h3>

                {currentFormateur.notesInternes ? (
                  <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs">
                    <div className="text-[10px] font-bold text-slate-400 uppercase mb-2">
                      Justification de la recommandation et notes internes
                    </div>
                    <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-line">
                      {currentFormateur.notesInternes}
                    </p>
                  </div>
                ) : (
                  <div className="bg-white p-8 rounded-2xl border border-slate-200 text-center text-slate-500">
                    <CheckCircle2 size={32} className="mx-auto text-slate-300 mb-2" />
                    <p className="font-bold text-xs text-slate-700">Aucune synthèse enregistrée pour ce formateur.</p>
                    <p className="text-[11px] text-slate-400 mt-1">
                      Elle apparaît après une évaluation post-session synchronisée.
                    </p>
                  </div>
                )}

                <section className="space-y-3">
                  <div className="flex items-center justify-between gap-3"><div><h4 className="font-extrabold text-sm text-[#11162A]">Enquêtes de satisfaction des apprenants</h4><p className="mt-1 text-[11px] text-slate-500">Les réponses alimentent directement la note et la recommandation de ce formateur.</p></div><span className="rounded-full bg-blue-50 px-2.5 py-1 text-[10px] font-bold text-blue-800">{currentTrainerFeedback.length} réponse(s)</span></div>
                  {currentTrainerFeedback.length ? currentTrainerFeedback.map((feedback, index) => <article key={`${feedback.session_id}-${feedback.participant_id}-${index}`} className="overflow-hidden rounded-xl border border-slate-200 bg-white">
                    <div className="flex flex-wrap items-center justify-between gap-2 bg-slate-50 px-4 py-3"><div><div className="text-xs font-extrabold text-[#11162A]">{feedback.session_titre}</div><div className="mt-0.5 text-[10px] text-slate-500">{feedback.participant_nom} · {feedback.date_evaluation ? new Date(feedback.date_evaluation).toLocaleDateString('fr-FR') : ''}</div></div><div className="flex items-center gap-2"><span className="rounded-lg bg-white px-2.5 py-1 text-xs font-black text-amber-700">★ {feedback.score_satisfaction ?? '—'} / 5</span>{feedback.niveau_initial && feedback.niveau_final && <span className="rounded-lg bg-emerald-50 px-2.5 py-1 text-[10px] font-bold text-emerald-800">{feedback.niveau_initial} → {feedback.niveau_final}</span>}</div></div>
                    <div className="grid gap-2 p-3 sm:grid-cols-2">{(feedback.reponses_satisfaction ?? []).map((answer: any, answerIndex: number) => <div key={answer.question_id ?? answerIndex} className="rounded-lg bg-slate-50 p-2.5"><div className="text-[10px] font-bold uppercase text-slate-400">{answer.question}</div><div className="mt-1 whitespace-pre-line text-xs font-semibold text-slate-700">{answer.answer || '—'}</div></div>)}</div>
                  </article>) : <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-5 text-center text-xs text-slate-500">Aucun apprenant n’a encore envoyé son enquête de satisfaction pour ce formateur.</div>}
                </section>

                <div className="space-y-3">
                  <div className="flex items-center justify-between gap-3">
                    <h4 className="font-extrabold text-sm text-[#11162A]">Évaluations validées</h4>
                    <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-[10px] font-bold text-emerald-800">{approvedEvaluations.length}</span>
                  </div>
                  {historyBusy ? <div className="rounded-xl bg-slate-50 p-4 text-xs text-slate-500">Chargement des évaluations approuvées…</div> : approvedEvaluations.length ? approvedEvaluations.map((review, index) => {
                    const data = review.data ?? review;
                    const score = Number(data.score_global);
                    const recommendation = String(data.recommandation ?? '');
                    const justif = data.justification_recommandation ?? data.synthese ?? data.resume ?? '';
                    const strengths = data.points_forts ?? data.recommandations ?? [];
                    return <article key={review.review_id ?? index} className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xs">
                      <div className="flex flex-wrap items-center justify-between gap-3 bg-gradient-to-r from-emerald-50 via-white to-slate-50 px-4 py-3">
                        <div><div className="text-sm font-extrabold text-[#11162A]">{review.meta?.session_title ?? data.session ?? 'Évaluation post-session'}</div><div className="mt-0.5 text-[10px] text-slate-500">Approuvée le {review.reviewed_at ? new Date(review.reviewed_at).toLocaleDateString('fr-FR') : '—'} · {review.review_id}</div></div>
                        <div className="flex items-center gap-2">{Number.isFinite(score) && <span className={`rounded-xl bg-white px-3 py-1.5 text-lg font-black shadow-xs ${scoreColor(score)}`}>{Math.round(score)}<span className="text-[10px] text-slate-400"> / 100</span></span>}{recommendation && <span className={`rounded-full px-2.5 py-1 text-[10px] font-extrabold ${recommandationStyle(recommendation)}`}>{recommendation}</span>}</div>
                      </div>
                      <div className="space-y-3 p-4">{justif && <p className="text-xs leading-relaxed text-slate-700">{String(justif)}</p>}{Array.isArray(strengths) && strengths.length > 0 && <div><div className="mb-1.5 text-[10px] font-bold uppercase tracking-wide text-slate-400">Points clés</div><ul className="space-y-1">{strengths.map((point: any, i: number) => <li key={i} className="flex gap-2 text-xs text-slate-600"><span className="text-[#1B8F6E]">•</span><span>{typeof point === 'string' ? point : String(point?.point ?? point?.description ?? JSON.stringify(point))}</span></li>)}</ul></div>}{review.reviewer_note && <div className="rounded-lg bg-emerald-50 p-2.5 text-[11px] text-emerald-800"><strong>Note de validation :</strong> {review.reviewer_note}</div>}</div>
                    </article>;
                  }) : <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-5 text-center text-xs text-slate-500">Aucune évaluation approuvée pour ce formateur. Les évaluations apparaissent ici après validation dans l’Espace IA.</div>}
                </div>

                <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-[11px] text-slate-500 flex items-start gap-2">
                  <Info size={14} className="shrink-0 mt-0.5" />
                  <span>
                    Le score du profil est recalculé à partir des notes de satisfaction reçues. La recommandation est mise à jour automatiquement et peut guider l’affectation future selon les compétences requises.
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ONGLET 2 : MATRICE D'ACQUISITION */}
      {activeTab === 'matrice' && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-4">
          <h3 className="text-base font-extrabold text-[#11162A] flex items-center gap-2">
            <BarChart2 size={18} className="text-[#1B8F6E]" />
            Taux d'acquisition par module
          </h3>

          {competencesData.length === 0 && (
            <p className="text-xs text-slate-500 bg-slate-50 p-4 rounded-xl border border-slate-200/80">
              Aucune donnée d'acquisition disponible pour le moment.
            </p>
          )}

          {competencesData.map((item, idx) => (
            <div key={idx}>
              <div className="flex justify-between text-xs font-bold text-slate-700 mb-1">
                <span>{item.module}</span>
                <span className="text-[#1B8F6E]">
                  {item.acquise}% · {item.participants} participants
                </span>
              </div>
              <div className="w-full bg-slate-100 h-2.5 rounded-full overflow-hidden">
                <div className="bg-[#1B8F6E] h-full rounded-full" style={{ width: `${item.acquise}%` }}></div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
