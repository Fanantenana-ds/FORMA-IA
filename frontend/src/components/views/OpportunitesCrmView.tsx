import React, { useState, useEffect, useRef } from 'react';
import { apiService } from '../../services/api';
import {
  Sparkles,
  Download,
  Check,
  Loader2
} from 'lucide-react';
import { MenuSection, OpportuniteCRM } from '../../types';
import { AcceptedMarket } from '../../types/tdr';
import { AcceptedMarketsList } from '../tdr/AcceptedMarketsList';
import { listenForVoiceAction, type VoiceActionContext } from '../../services/voiceActionContext';

const markdownFor = (value: unknown): string => {
  if (value == null) return '';
  if (typeof value !== 'object') return String(value);
  if (Array.isArray(value)) return value.map(item => `- ${markdownFor(item)}`).join('\n');
  return Object.entries(value as Record<string, unknown>).map(([key, item]) => {
    const label = key.replaceAll('_', ' ').replace(/^./, c => c.toUpperCase());
    const content = typeof item === 'object' && item !== null ? markdownFor(item) : String(item ?? '');
    return `### ${label}\n\n${content}`;
  }).join('\n\n');
};

const updateAtPath = (source: any, path: (string | number)[], value: unknown): any => {
  if (!path.length) return value;
  const [head, ...tail] = path;
  const copy = Array.isArray(source) ? [...source] : { ...(source ?? {}) };
  copy[head] = updateAtPath(copy[head], tail, value);
  return copy;
};

const safeHtml = (text: string) => text.replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char] ?? char));

const markdownToExportHtml = (markdown: string) => {
  const output: string[] = [];
  let inList = false;
  for (const line of markdown.split('\n')) {
    const content = safeHtml(line).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    if (/^- /.test(line)) {
      if (!inList) { output.push('<ul>'); inList = true; }
      output.push(`<li>${content.slice(2)}</li>`);
      continue;
    }
    if (inList) { output.push('</ul>'); inList = false; }
    if (/^### /.test(line)) output.push(`<h3>${content.slice(4)}</h3>`);
    else if (/^## /.test(line)) output.push(`<h2>${content.slice(3)}</h2>`);
    else if (/^# /.test(line)) output.push(`<h1>${content.slice(2)}</h1>`);
    else if (content.trim()) output.push(`<p>${content}</p>`);
  }
  if (inList) output.push('</ul>');
  return output.join('\n');
};

const financialDocumentHtml = (document: Record<string, any>): string => {
  const costs = document.details_couts ?? {};
  const recap = document.recapitulatif ?? {};
  const currency = safeHtml(String(document.devise ?? 'MGA'));
  const amount = (value: unknown) => `${Number(value ?? 0).toLocaleString('fr-FR')} ${currency}`;
  const lines = [
    ['Honoraires du formateur', `${costs.honoraires_formateur?.nb_jours ?? '—'} jour(s) × ${amount(costs.honoraires_formateur?.tarif_journalier)}`, costs.honoraires_formateur?.sous_total],
    ['Location de salle', `${costs.location_salle?.nb_jours ?? '—'} jour(s) × ${amount(costs.location_salle?.tarif_journalier)}`, costs.location_salle?.sous_total],
    ['Supports pédagogiques', `${costs.supports_pedagogiques?.nb_participants ?? '—'} participant(s) × ${amount(costs.supports_pedagogiques?.forfait_participant)}`, costs.supports_pedagogiques?.sous_total],
    ['Logistique', costs.logistique?.description ?? 'Frais logistiques', costs.logistique?.montant],
    ['Frais d’administration', `${costs.administration?.pourcentage ?? 0}% de ${amount(costs.administration?.base)}`, costs.administration?.montant],
  ].filter(([, detail, value]) => detail !== undefined || value !== undefined);
  const costTable = `<h2>Détail des coûts</h2><table class="financial-table"><thead><tr><th>Poste</th><th>Base de calcul</th><th>Montant (${currency})</th></tr></thead><tbody>${lines.map(([label, detail, value]) => `<tr><td>${safeHtml(String(label))}</td><td>${safeHtml(String(detail ?? '—'))}</td><td class="amount">${amount(value)}</td></tr>`).join('')}</tbody></table>`;
  const discounts = Array.isArray(recap.remises) ? recap.remises : [];
  const recapRows = [
    ['Sous-total hors taxes', amount(recap.sous_total_ht)],
    [`TVA (${recap.tva?.taux ?? 0}%)`, amount(recap.tva?.montant)],
    ['Total toutes taxes comprises', amount(recap.total_ttc)],
    ...discounts.map((discount: any, index: number) => [`Remise${discount.description ? ` · ${discount.description}` : ` ${index + 1}`}`, `− ${amount(discount.montant)}`]),
    ['Net à payer', amount(recap.net_a_payer)],
  ];
  const recapTable = `<h2>Récapitulatif financier</h2><table class="summary-table"><tbody>${recapRows.map(([label, value], index) => `<tr class="${index === recapRows.length - 1 ? 'grand-total' : ''}"><th>${safeHtml(String(label))}</th><td>${safeHtml(String(value))}</td></tr>`).join('')}</tbody></table>`;
  const installments = Array.isArray(document.echeancier) ? document.echeancier : [];
  const scheduleTable = installments.length ? `<h2>Échéancier de paiement</h2><table class="financial-table"><thead><tr><th>Échéance</th><th>Part</th><th>Montant</th></tr></thead><tbody>${installments.map((item: any, index: number) => `<tr><td>${safeHtml(String(item.libelle ?? item.etape ?? item.echeance ?? `Échéance ${index + 1}`))}</td><td>${safeHtml(String(item.pourcentage ?? '—'))}%</td><td class="amount">${amount(item.montant)}</td></tr>`).join('')}</tbody></table>` : '';
  const excluded = new Set(['titre_offre', 'reference', 'date_emission', 'devise', 'details_couts', 'recapitulatif', 'echeancier']);
  const flatten = (value: unknown, prefix = ''): Array<[string, string]> => {
    if (Array.isArray(value)) return value.flatMap((item, index) => flatten(item, `${prefix} ${index + 1}`.trim()));
    if (value && typeof value === 'object') return Object.entries(value as Record<string, unknown>).flatMap(([key, item]) => flatten(item, prefix ? `${prefix} · ${key.replaceAll('_', ' ')}` : key.replaceAll('_', ' ')));
    if (value == null || value === '') return [];
    return [[prefix.replace(/^./, character => character.toUpperCase()), String(value)]];
  };
  const infoRows = Object.entries(document).filter(([key]) => !excluded.has(key)).flatMap(([key, value]) => flatten(value, key.replaceAll('_', ' ')));
  const infoTable = infoRows.length ? `<h2>Conditions et informations complémentaires</h2><table class="info-table"><tbody>${infoRows.map(([label, value]) => `<tr><th>${safeHtml(label)}</th><td>${safeHtml(value)}</td></tr>`).join('')}</tbody></table>` : '';
  return `${costTable}${recapTable}${scheduleTable}${infoTable}`;
};

const FinancialOfferPreview: React.FC<{ document: Record<string, any> }> = ({ document }) => {
  const costs = document.details_couts ?? {};
  const recap = document.recapitulatif ?? {};
  const currency = document.devise ?? 'MGA';
  const amount = (value: unknown) => `${Number(value ?? 0).toLocaleString('fr-FR')} ${currency}`;
  const rows = [
    ['Honoraires du formateur', `${costs.honoraires_formateur?.nb_jours ?? '—'} jour(s) × ${amount(costs.honoraires_formateur?.tarif_journalier)}`, costs.honoraires_formateur?.sous_total],
    ['Location de salle', `${costs.location_salle?.nb_jours ?? '—'} jour(s) × ${amount(costs.location_salle?.tarif_journalier)}`, costs.location_salle?.sous_total],
    ['Supports pédagogiques', `${costs.supports_pedagogiques?.nb_participants ?? '—'} participant(s) × ${amount(costs.supports_pedagogiques?.forfait_participant)}`, costs.supports_pedagogiques?.sous_total],
    ['Logistique', costs.logistique?.description ?? 'Frais logistiques', costs.logistique?.montant],
    ['Frais d’administration', `${costs.administration?.pourcentage ?? 0}% de ${amount(costs.administration?.base)}`, costs.administration?.montant],
  ];
  const recapRows = [
    ['Sous-total hors taxes', amount(recap.sous_total_ht)],
    [`TVA (${recap.tva?.taux ?? 0}%)`, amount(recap.tva?.montant)],
    ['Total toutes taxes comprises', amount(recap.total_ttc)],
    ...(Array.isArray(recap.remises) ? recap.remises.map((discount: any, index: number) => [`Remise ${discount.description ?? index + 1}`, `− ${amount(discount.montant)}`]) : []),
    ['Net à payer', amount(recap.net_a_payer)],
  ];
  return <div className="space-y-4 text-left">
    <div><h2 className="mb-2 text-sm font-extrabold text-[#11162A]">Détail des coûts</h2><div className="overflow-x-auto rounded-lg border border-slate-200"><table className="w-full border-collapse text-xs"><thead className="bg-slate-100 text-slate-600"><tr><th className="p-2 text-left">Poste</th><th className="p-2 text-left">Base de calcul</th><th className="p-2 text-right">Montant ({currency})</th></tr></thead><tbody>{rows.map(([label, detail, value], index) => <tr key={index} className="border-t border-slate-200"><td className="p-2 font-semibold text-slate-800">{label}</td><td className="p-2 text-slate-600">{detail}</td><td className="p-2 text-right font-semibold tabular-nums text-slate-800">{amount(value)}</td></tr>)}</tbody></table></div></div>
    <div><h2 className="mb-2 text-sm font-extrabold text-[#11162A]">Récapitulatif financier</h2><div className="overflow-hidden rounded-lg border border-slate-200"><table className="w-full border-collapse text-xs"><tbody>{recapRows.map(([label, value], index) => <tr key={index} className={`border-t border-slate-200 first:border-t-0 ${index === recapRows.length - 1 ? 'bg-emerald-50 font-extrabold text-emerald-800' : ''}`}><th className="p-2 text-left">{label}</th><td className="p-2 text-right tabular-nums">{value}</td></tr>)}</tbody></table></div></div>
    {Array.isArray(document.echeancier) && document.echeancier.length > 0 && <div><h2 className="mb-2 text-sm font-extrabold text-[#11162A]">Échéancier de paiement</h2><div className="overflow-x-auto rounded-lg border border-slate-200"><table className="w-full border-collapse text-xs"><thead className="bg-slate-100"><tr><th className="p-2 text-left">Échéance</th><th className="p-2 text-right">Part</th><th className="p-2 text-right">Montant</th></tr></thead><tbody>{document.echeancier.map((item: any, index: number) => <tr key={index} className="border-t border-slate-200"><td className="p-2">{item.libelle ?? item.etape ?? item.echeance ?? `Échéance ${index + 1}`}</td><td className="p-2 text-right">{item.pourcentage ?? '—'}%</td><td className="p-2 text-right font-semibold">{amount(item.montant)}</td></tr>)}</tbody></table></div></div>}
  </div>;
};

const renderMarkdown = (markdown: string) => markdown.split('\n').map((line, index) => {
  if (line.startsWith('### ')) return <h3 key={index} className="mt-4 mb-2 text-sm font-extrabold text-[#11162A]">{line.slice(4)}</h3>;
  if (line.startsWith('## ')) return <h2 key={index} className="mt-5 mb-2 text-base font-extrabold text-[#11162A]">{line.slice(3)}</h2>;
  if (line.startsWith('# ')) return <h1 key={index} className="mt-2 mb-3 text-lg font-extrabold text-[#11162A]">{line.slice(2)}</h1>;
  if (line.startsWith('- ')) return <div key={index} className="ml-4 list-item list-disc text-sm text-slate-700">{line.slice(2)}</div>;
  return line ? <p key={index} className="my-1 whitespace-pre-wrap text-sm text-slate-700">{line}</p> : <div key={index} className="h-1" />;
});

interface OpportunitesCrmViewProps {
  opportunites: OpportuniteCRM[];
  onOpenNewOpportunity?: () => void;
  onRefreshData?: () => Promise<void> | void;
  canDeleteOpportunities?: boolean;
  onNavigateToSection?: (section: MenuSection) => void;
}

export const OpportunitesCrmView: React.FC<OpportunitesCrmViewProps> = ({
  opportunites,
  onOpenNewOpportunity,
  onRefreshData,
  canDeleteOpportunities = false,
  onNavigateToSection
}) => {
  const acceptedMarkets: AcceptedMarket[] = opportunites.map((opportunity) => ({
    id: opportunity.id,
    titre: opportunity.entreprise || 'Opportunité enregistrée',
    client: opportunity.entreprise || 'Client à préciser',
    domaine: opportunity.domaineIA,
    budgetAr: opportunity.montantEstime,
    duree: 'À définir',
    date: opportunity.dateDetection,
    statut: opportunity.etape
  }));

  const [selectedMarketId, setSelectedMarketId] = useState<string>(() => {
    try {
      const saved = sessionStorage.getItem('formaia-active-market');
      if (saved && acceptedMarkets.some(market => market.id === saved)) return saved;
    } catch { /* stockage désactivé */ }
    return acceptedMarkets[0]?.id ?? '';
  });
  useEffect(() => { try { sessionStorage.setItem('formaia-active-market', selectedMarketId); } catch { /* stockage désactivé */ } }, [selectedMarketId]);

  const activeMarket: AcceptedMarket | undefined =
    acceptedMarkets.find((m) => m.id === selectedMarketId) ?? acceptedMarkets[0];

  const [docTab, setDocTab] = useState<'tdr' | 'technical' | 'financial'>('tdr');
  const [tdrBrief, setTdrBrief] = useState({ client: '', objectifs: '', public: '', duree: '', format: 'Présentiel', budget: '', lieu: '', deadline: '' });
  const [enrichFromRag, setEnrichFromRag] = useState(false);
  const [generatedTdr, setGeneratedTdr] = useState<Record<string, any> | null>(null);
  const [tdrEditMode, setTdrEditMode] = useState(false);
  const [tdrFiles, setTdrFiles] = useState<{ docx?: string; pdf?: string }>({});
  const [tdrReviewId, setTdrReviewId] = useState('');
  const [tdrApproved, setTdrApproved] = useState(false);
  const [tdrSynchronized, setTdrSynchronized] = useState(false);
  const [tdrReviewNote, setTdrReviewNote] = useState('');
  const [techniqueDocument, setTechniqueDocument] = useState<Record<string, any> | null>(null);
  const [techniqueRequest, setTechniqueRequest] = useState<{ tdr_data: Record<string, any>; session_info: Record<string, any> } | null>(null);
  const [techniqueEditMode, setTechniqueEditMode] = useState(false);
  const [techniqueReviewId, setTechniqueReviewId] = useState('');
  const [techniqueApproved, setTechniqueApproved] = useState(false);
  const [financeDocument, setFinanceDocument] = useState<Record<string, any> | null>(null);
  const [financeReviewId, setFinanceReviewId] = useState('');
  const [financeApproved, setFinanceApproved] = useState(false);
  const [offerSaved, setOfferSaved] = useState(false);
  const [financeInputs, setFinanceInputs] = useState({ trainerRate: 0, trainerDays: 0, roomRate: 0, roomDays: 0, supportRate: 0, participants: 0, logistics: 0, adminPercent: 0 });
  const [offerOptions, setOfferOptions] = useState({ participants: 20, trainerType: 'senior', roomType: 'standard', vat: true, logistics: true, administration: true });
  const [includePortfolioRag, setIncludePortfolioRag] = useState(false);
  const [reviewNote, setReviewNote] = useState('');
  const [generationBusy, setGenerationBusy] = useState(false);
  const [activeAction, setActiveAction] = useState<'tdr' | 'technical' | 'financial' | 'review' | 'export' | null>(null);
  const [generationMessage, setGenerationMessage] = useState('');
  const [generationError, setGenerationError] = useState('');
  const [deleteError, setDeleteError] = useState('');
  const [deletingOpportunityId, setDeletingOpportunityId] = useState('');
  const restoredWorkflowMarket = useRef('');
  const skipWorkflowWrite = useRef(false);
  const voicePrefillRef = useRef<Record<string, unknown> | null>(null);
  const acceptedMarketsRef = useRef(acceptedMarkets);
  acceptedMarketsRef.current = acceptedMarkets;

  const applyVoiceAction = (context: VoiceActionContext) => {
    const prefill = context.prefill ?? {};
    const targetId = String(prefill.opportunite_id ?? prefill.opportunity_id ?? prefill.market_id ?? '');
    const targetLabel = String(prefill.objectifs ?? prefill.titre ?? prefill.opportunite ?? '');
    let match = acceptedMarketsRef.current.find(market => market.id === targetId);
    if (!match && targetLabel) {
      const normalized = targetLabel.toLocaleLowerCase('fr-FR').trim();
      const matches = acceptedMarketsRef.current.filter(market => market.titre.toLocaleLowerCase('fr-FR').trim() === normalized);
      if (matches.length === 1) match = matches[0];
    }
    if (match) setSelectedMarketId(match.id);
    const brief = Object.fromEntries(
      ['client', 'objectifs', 'public', 'duree', 'format', 'budget', 'lieu', 'deadline']
        .filter(key => prefill[key] != null && String(prefill[key]).trim())
        .map(key => [key, String(prefill[key])]),
    );
    voicePrefillRef.current = brief;
    if (Object.keys(brief).length) setTdrBrief(previous => ({ ...previous, ...brief }));
    setDocTab(context.action === 'ouvrir_formulaire_offre' ? 'technical' : 'tdr');
  };

  useEffect(() => listenForVoiceAction(['ouvrir_formulaire_tdr', 'ouvrir_formulaire_offre'], applyVoiceAction), []);
  const pendingDocumentReview = docTab === 'tdr' && !tdrApproved ? tdrReviewId
    : docTab === 'technical' && !techniqueApproved ? techniqueReviewId
      : docTab === 'financial' && !financeApproved ? financeReviewId : '';
  const openDocumentReview = () => {
    if (!pendingDocumentReview) return;
    try { sessionStorage.setItem('formaia-review-focus', pendingDocumentReview); } catch { /* stockage désactivé */ }
    onNavigateToSection?.('espace_ia');
  };

  const deleteOpportunity = async (id: string, title: string) => {
    if (!window.confirm(`Supprimer l’opportunité acceptée « ${title} » ?`)) return;
    setDeletingOpportunityId(id);
    setDeleteError('');
    try {
      await apiService.deleteOpportunity(id);
      const remaining = acceptedMarkets.filter((market) => market.id !== id);
      if (selectedMarketId === id) setSelectedMarketId(remaining[0]?.id ?? '');
      try { sessionStorage.removeItem(`formaia-m2-m3-${id}`); } catch { /* stockage désactivé */ }
      await onRefreshData?.();
    } catch (error) {
      setDeleteError(error instanceof Error ? error.message : 'La suppression de l’opportunité a échoué.');
    } finally {
      setDeletingOpportunityId('');
    }
  };

  useEffect(() => {
    if (!activeMarket) return;
    let restored: any = null;
    try { restored = JSON.parse(sessionStorage.getItem(`formaia-m2-m3-${activeMarket.id}`) ?? 'null'); } catch { restored = null; }
    restoredWorkflowMarket.current = activeMarket.id;
    skipWorkflowWrite.current = true;
    if (restored) {
      setDocTab(restored.docTab ?? 'tdr'); setTdrBrief(restored.tdrBrief ?? { client: '', objectifs: activeMarket.titre, public: '', duree: '', format: 'Présentiel', budget: '', lieu: '', deadline: '' });
      setEnrichFromRag(!!restored.enrichFromRag); setGeneratedTdr(restored.generatedTdr ?? null); setTdrEditMode(false); setTdrFiles(restored.tdrFiles ?? {}); setTdrReviewId(restored.tdrReviewId ?? ''); setTdrApproved(!!restored.tdrApproved); setTdrSynchronized(!!restored.tdrSynchronized); setTdrReviewNote(restored.tdrReviewNote ?? '');
      setTechniqueDocument(restored.techniqueDocument ?? null); setTechniqueRequest(restored.techniqueRequest ?? null); setTechniqueEditMode(false); setTechniqueReviewId(restored.techniqueReviewId ?? ''); setTechniqueApproved(!!restored.techniqueApproved);
      setFinanceDocument(restored.financeDocument ?? null); setFinanceReviewId(restored.financeReviewId ?? ''); setFinanceApproved(!!restored.financeApproved); setOfferSaved(!!restored.offerSaved);
      setFinanceInputs(restored.financeInputs ?? { trainerRate: 0, trainerDays: 0, roomRate: 0, roomDays: 0, supportRate: 0, participants: 0, logistics: 0, adminPercent: 0 });
      setOfferOptions(restored.offerOptions ?? { participants: 20, trainerType: 'senior', roomType: 'standard', vat: true, logistics: true, administration: true }); setIncludePortfolioRag(!!restored.includePortfolioRag); setReviewNote(restored.reviewNote ?? '');
    } else {
      setDocTab('tdr'); setTdrBrief({ client: '', objectifs: activeMarket.titre, public: '', duree: '', format: 'Présentiel', budget: activeMarket.budgetAr ? String(activeMarket.budgetAr) : '', lieu: '', deadline: '' });
      setEnrichFromRag(false); setGeneratedTdr(null); setTdrEditMode(false); setTdrFiles({}); setTdrReviewId(''); setTdrApproved(false); setTdrSynchronized(false); setTdrReviewNote('');
      setTechniqueDocument(null); setTechniqueRequest(null); setTechniqueEditMode(false); setTechniqueReviewId(''); setTechniqueApproved(false); setFinanceDocument(null); setFinanceReviewId(''); setFinanceApproved(false); setOfferSaved(false);
      setFinanceInputs({ trainerRate: 0, trainerDays: 0, roomRate: 0, roomDays: 0, supportRate: 0, participants: 0, logistics: 0, adminPercent: 0 }); setOfferOptions({ participants: 20, trainerType: 'senior', roomType: 'standard', vat: true, logistics: true, administration: true }); setIncludePortfolioRag(false); setReviewNote('');
    }
    setGenerationMessage(''); setGenerationError('');
    let cancelled = false;
    apiService.getTdrBriefFromOpportunity(activeMarket.id).then((result) => {
      if (cancelled || restored?.tdrBrief) return;
      const brief = result.brief ?? {};
        setTdrBrief({
        // Seul l'organisme explicite de l'avis préremplit le client. Le titre
        // de l'appel n'est pas un nom d'organisation ; si la source ne le
        // fournit pas, le champ reste à confirmer par la direction.
        client: brief.client ?? '',
        objectifs: brief.objectifs || activeMarket.titre,
        public: brief.public || '', duree: brief.duree || '', format: brief.format || 'Présentiel',
        budget: brief.budget || (activeMarket.budgetAr ? String(activeMarket.budgetAr) : ''),
        lieu: brief.lieu || '', deadline: brief.deadline || '',
        ...(voicePrefillRef.current ?? {}),
        });
    }).catch(() => {
      if (!cancelled) setTdrBrief({ client: '', objectifs: `${activeMarket.titre}\n\n${opportunites.find(o => o.id === activeMarket.id)?.besoinFormation ?? ''}`.trim(), public: '', duree: '', format: 'Présentiel', budget: activeMarket.budgetAr ? String(activeMarket.budgetAr) : '', lieu: '', deadline: '', ...(voicePrefillRef.current ?? {}) });
    });
    return () => { cancelled = true; };
  }, [selectedMarketId, activeMarket?.id]);

  useEffect(() => {
    if (!activeMarket || restoredWorkflowMarket.current !== activeMarket.id) return;
    if (skipWorkflowWrite.current) { skipWorkflowWrite.current = false; return; }
    try {
      sessionStorage.setItem(`formaia-m2-m3-${activeMarket.id}`, JSON.stringify({
        docTab, tdrBrief, enrichFromRag, generatedTdr, tdrFiles, tdrReviewId, tdrApproved, tdrSynchronized, tdrReviewNote,
        techniqueDocument, techniqueRequest, techniqueReviewId, techniqueApproved, financeDocument, financeReviewId, financeApproved, offerSaved,
        financeInputs, offerOptions, includePortfolioRag, reviewNote
      }));
    } catch { /* le stockage de session peut être désactivé */ }
  }, [activeMarket?.id, docTab, tdrBrief, enrichFromRag, generatedTdr, tdrFiles, tdrReviewId, tdrApproved, tdrSynchronized, tdrReviewNote, techniqueDocument, techniqueRequest, techniqueReviewId, techniqueApproved, financeDocument, financeReviewId, financeApproved, offerSaved, financeInputs, offerOptions, includePortfolioRag, reviewNote]);

  const downloadBlob = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob); const anchor = document.createElement('a');
    anchor.href = url; anchor.download = filename; anchor.click(); URL.revokeObjectURL(url);
  };

  const generateTdr = async () => {
    if (!activeMarket) return;
    if (tdrBrief.client.trim().length < 2 || tdrBrief.objectifs.trim().length < 5 || tdrBrief.public.trim().length < 2 || !tdrBrief.duree.trim()) {
      setGenerationError('Renseignez le client, les objectifs, le public cible et la durée avant de générer le TDR.'); return;
    }
    setGenerationBusy(true); setGenerationError(''); setGenerationMessage('');
    try {
      setActiveAction('tdr');
      let objectifs = tdrBrief.objectifs.trim();
      if (enrichFromRag) {
        const rag = await apiService.searchRagDocuments(`${tdrBrief.client} ${tdrBrief.objectifs}`);
        const sources = (rag.data ?? []).map((row: any) => row.contenu ?? row.texte ?? row.extrait).filter(Boolean).slice(0, 3);
        if (sources.length) objectifs += `\n\nRéférences issues des formations passées (RAG) :\n${sources.join('\n')}`;
      }
      const result = await apiService.generateTdr({
        ...tdrBrief, client: tdrBrief.client.trim(), objectifs,
        opportunite_id: activeMarket.id, domaine: activeMarket.domaine
      });
      if (!result.success || !result.review_id) throw new Error(result.error || 'Le backend n’a pas créé de validation TDR.');
      setGeneratedTdr(result.data ?? {}); setTdrFiles(result.files ?? {}); setTdrReviewId(result.review_id); setTdrApproved(false); setTdrSynchronized(false);
      setGenerationMessage(`TDR généré. Vérifiez l’aperçu puis approuvez-le ou rejetez-le (référence ${result.review_id}).`);
    } catch (error) { setGenerationError(error instanceof Error ? error.message : 'Génération TDR impossible.'); }
    finally { setGenerationBusy(false); setActiveAction(null); }
  };

  const reviewTdr = async (approve: boolean) => {
    if (!tdrReviewId) return;
    if (!approve && tdrReviewNote.trim().length < 3) { setGenerationError('Indiquez le motif du rejet (3 caractères minimum).'); return; }
    setGenerationBusy(true); setGenerationError(''); setGenerationMessage('');
    try {
      setActiveAction('review');
      if (approve) {
        await apiService.approveTdr(tdrReviewId, tdrReviewNote.trim() || 'OK');
        setTdrApproved(true);
        try { await apiService.syncTdr(tdrReviewId, activeMarket?.id); setTdrSynchronized(true); setGenerationMessage('TDR approuvé et enregistré dans le backend. Les exports Word et PDF sont disponibles.'); }
        catch (syncError) { setGenerationError(`TDR approuvé, mais son enregistrement dans le dossier Backend a échoué : ${syncError instanceof Error ? syncError.message : 'erreur inconnue'}`); }
      } else {
        await apiService.rejectTdr(tdrReviewId, tdrReviewNote.trim()); setGeneratedTdr(null); setTdrReviewId(''); setGenerationMessage('TDR rejeté. Vous pouvez corriger le brief et relancer la génération.');
      }
    } catch (error) { setGenerationError(error instanceof Error ? error.message : 'La validation du TDR a échoué.'); }
    finally { setGenerationBusy(false); setActiveAction(null); }
  };

  const rectifyTdr = async () => {
    const feedback = tdrReviewNote.trim();
    if (!tdrReviewId || feedback.length < 5) { setGenerationError('Décrivez les rectifications à demander à l’IA (5 caractères minimum).'); return; }
    if (/^ok[.!\s]*$/i.test(feedback)) { await reviewTdr(true); return; }
    setGenerationBusy(true); setGenerationError(''); setGenerationMessage(''); setActiveAction('tdr');
    try {
      const result = await apiService.rectifyTdr({
        review_id: tdrReviewId,
        feedback,
        brief: { ...tdrBrief, client: tdrBrief.client.trim(), opportunite_id: activeMarket?.id, domaine: activeMarket?.domaine }
      });
      if (!result.success || !result.review_id) throw new Error(result.error || 'La nouvelle version TDR n’a pas été créée.');
      setGeneratedTdr(result.data ?? {}); setTdrFiles(result.files ?? {}); setTdrReviewId(result.review_id);
      setTdrApproved(false); setTdrSynchronized(false); setTdrReviewNote('');
      setGenerationMessage('Le TDR a été corrigé par l’IA. Vérifiez cette nouvelle version avant de l’approuver.');
    } catch (error) { setGenerationError(error instanceof Error ? error.message : 'La rectification IA du TDR a échoué.'); }
    finally { setGenerationBusy(false); setActiveAction(null); }
  };

  const retryTdrSync = async () => {
    if (!tdrReviewId || !activeMarket) return;
    setGenerationBusy(true); setGenerationError('');
    try { await apiService.syncTdr(tdrReviewId, activeMarket.id); setTdrSynchronized(true); setGenerationMessage('TDR synchronisé avec le backend.'); }
    catch (error) { setGenerationError(error instanceof Error ? error.message : 'La synchronisation du TDR a échoué.'); }
    finally { setGenerationBusy(false); }
  };

  const generateTechnique = async () => {
    if (!activeMarket || !generatedTdr || !tdrApproved) return;
    setGenerationBusy(true); setGenerationError(''); setGenerationMessage(''); setActiveAction('technical');
    try {
      let tdrForOffer = structuredClone(generatedTdr);
      if (includePortfolioRag) {
        const rag = await apiService.searchRagDocuments(`${tdrBrief.client} ${tdrBrief.objectifs}`);
        const refs = (rag.data ?? []).map((row: any) => row.contenu ?? row.texte ?? row.extrait).filter(Boolean).slice(0, 5);
        tdrForOffer = { ...tdrForOffer, references_portfolio: refs };
      }
      const request = { tdr_data: tdrForOffer, session_info: { titre: activeMarket.titre, client: tdrBrief.client, opportunite_id: activeMarket.id, domaine: activeMarket.domaine, duree: tdrBrief.duree } };
      const result = await apiService.generateOfferTechnique(request);
      if (!result.success || !result.review_id) throw new Error(result.message || 'Le backend n’a pas créé le review de l’offre technique.');
      setTechniqueDocument(result.data ?? {}); setTechniqueRequest(request); setTechniqueReviewId(result.review_id); setTechniqueApproved(false); setFinanceDocument(null); setFinanceReviewId(''); setFinanceApproved(false); setOfferSaved(false);
      setGenerationMessage(`Offre technique générée. Vérifiez et validez-la avant de passer au volet financier (${result.review_id}).`);
      setDocTab('technical');
    } catch (error) { setGenerationError(error instanceof Error ? error.message : 'Génération de l’offre technique impossible.'); }
    finally { setGenerationBusy(false); setActiveAction(null); }
  };

  const reviewTechnique = async (approve: boolean) => {
    if (!techniqueReviewId) return;
    if (!approve && reviewNote.trim().length < 3) { setGenerationError('Indiquez le motif du rejet (3 caractères minimum).'); return; }
    setGenerationBusy(true); setGenerationError(''); setGenerationMessage(''); setActiveAction('review');
    try {
      if (approve) { await apiService.approveOfferReview(techniqueReviewId, reviewNote.trim() || 'OK'); setTechniqueApproved(true); setGenerationMessage('Offre technique approuvée. Vous pouvez maintenant préparer l’offre financière.'); }
      else { await apiService.rejectOfferReview(techniqueReviewId, reviewNote.trim()); setTechniqueDocument(null); setTechniqueReviewId(''); setTechniqueApproved(false); setGenerationMessage('Offre technique rejetée. Générez une nouvelle version après correction du TDR.'); }
      setReviewNote('');
    } catch (error) { setGenerationError(error instanceof Error ? error.message : 'La validation technique a échoué.'); }
    finally { setGenerationBusy(false); setActiveAction(null); }
  };

  const rectifyTechnique = async () => {
    const feedback = reviewNote.trim();
    if (!techniqueReviewId || feedback.length < 5) { setGenerationError('Décrivez les rectifications à demander à l’IA (5 caractères minimum).'); return; }
    if (/^ok[.!\s]*$/i.test(feedback)) { await reviewTechnique(true); return; }
    if (!generatedTdr || !activeMarket) return;
    setGenerationBusy(true); setGenerationError(''); setGenerationMessage(''); setActiveAction('technical');
    try {
      const result = await apiService.rectifyOfferTechnique({
        review_id: techniqueReviewId, feedback, tdr_data: generatedTdr,
        session_info: { titre: activeMarket.titre, client: tdrBrief.client, opportunite_id: activeMarket.id, domaine: activeMarket.domaine, duree: tdrBrief.duree }
      });
      const corrected = result.data ?? {};
      if (!result.success || !result.review_id) throw new Error(result.message || 'La nouvelle offre technique n’a pas été créée.');
      setTechniqueDocument(corrected); setTechniqueReviewId(result.review_id); setTechniqueApproved(false); setReviewNote('');
      setGenerationMessage('L’offre technique a été corrigée par son agent IA. Vérifiez cette nouvelle version avant de l’approuver.');
    } catch (error) { setGenerationError(error instanceof Error ? error.message : 'La rectification IA de l’offre technique a échoué.'); }
    finally { setGenerationBusy(false); setActiveAction(null); }
  };

  const generateFinance = async () => {
    if (!techniqueApproved || !techniqueDocument || !techniqueReviewId || !activeMarket) return;
    setGenerationBusy(true); setGenerationError(''); setGenerationMessage(''); setActiveAction('financial');
    try {
      const approvedReview = await apiService.getOfferReview(techniqueReviewId);
      if (approvedReview.review?.status !== 'approved') {
        setTechniqueApproved(false);
        throw new Error('L’offre technique doit être approuvée avant la génération financière.');
      }
      const technicalForPricing = structuredClone(techniqueDocument);
      const durationInOffer = Number.parseInt(String(techniqueDocument.programme?.duree_totale ?? ''), 10);
      const durationDays = Math.max(1, financeInputs.trainerDays || durationInOffer || 1);
      if (technicalForPricing.programme) technicalForPricing.programme.duree_totale = `${durationDays} jours`;
      const result = await apiService.generateOfferFinanciere({ offre_technique: technicalForPricing, options: { nb_participants: offerOptions.participants, type_formateur: offerOptions.trainerType, type_salle: offerOptions.roomType, tva_applicable: offerOptions.vat, inclure_logistique: offerOptions.logistics, inclure_administration: offerOptions.administration } });
      if (!result.success || !result.review_id) throw new Error(result.message || 'Le backend n’a pas créé le review financier.');
      const financial = result.data ?? {};
      const costs = financial.details_couts ?? {};
      setFinanceInputs({
        trainerRate: Number(costs.honoraires_formateur?.tarif_journalier ?? 0), trainerDays: Number(costs.honoraires_formateur?.nb_jours ?? durationDays),
        roomRate: Number(costs.location_salle?.tarif_journalier ?? 0), roomDays: Number(costs.location_salle?.nb_jours ?? durationDays),
        supportRate: Number(costs.supports_pedagogiques?.forfait_participant ?? 0), participants: Number(costs.supports_pedagogiques?.nb_participants ?? offerOptions.participants),
        logistics: Number(costs.logistique?.montant ?? 0), adminPercent: Number(costs.administration?.pourcentage ?? 0)
      });
      setFinanceDocument(financial); setFinanceReviewId(result.review_id); setFinanceApproved(false); setOfferSaved(false); setDocTab('financial');
      setGenerationMessage(`Offre financière générée. Ajustez les lignes, puis validez les deux volets séparément (${result.review_id}).`);
    } catch (error) { setGenerationError(error instanceof Error ? error.message : 'Génération de l’offre financière impossible.'); }
    finally { setGenerationBusy(false); setActiveAction(null); }
  };

  const adjustedFinance = (() => {
    const trainer = financeInputs.trainerRate * financeInputs.trainerDays;
    const room = financeInputs.roomRate * financeInputs.roomDays;
    const supports = financeInputs.supportRate * financeInputs.participants;
    const beforeAdmin = trainer + room + supports + financeInputs.logistics;
    const admin = Math.round(beforeAdmin * financeInputs.adminPercent / 100);
    const subtotal = beforeAdmin + admin;
    const taxRate = financeDocument?.recapitulatif?.tva?.applicable === false ? 0 : Number(financeDocument?.recapitulatif?.tva?.taux ?? 20);
    const tax = Math.round(subtotal * taxRate / 100);
    const discountPercent = Number(financeDocument?.recapitulatif?.remises?.[0]?.pourcentage ?? 0);
    const discount = Math.round((subtotal + tax) * discountPercent / 100);
    const total = subtotal + tax - discount;
    return { trainer, room, supports, logistics: financeInputs.logistics, admin, subtotal, taxRate, tax, discount, total };
  })();

  const finalFinancial = financeDocument ? {
        ...financeDocument,
        details_couts: {
          honoraires_formateur: { tarif_journalier: financeInputs.trainerRate, nb_jours: financeInputs.trainerDays, sous_total: adjustedFinance.trainer },
          location_salle: { tarif_journalier: financeInputs.roomRate, nb_jours: financeInputs.roomDays, sous_total: adjustedFinance.room },
          supports_pedagogiques: { forfait_participant: financeInputs.supportRate, nb_participants: financeInputs.participants, sous_total: adjustedFinance.supports },
          logistique: { description: 'Déplacements, repas, pauses', montant: adjustedFinance.logistics },
          administration: { pourcentage: financeInputs.adminPercent, base: adjustedFinance.trainer + adjustedFinance.room + adjustedFinance.supports + adjustedFinance.logistics, montant: adjustedFinance.admin }
        },
        recapitulatif: { ...financeDocument.recapitulatif, sous_total_ht: adjustedFinance.subtotal, tva: { taux: adjustedFinance.taxRate, montant: adjustedFinance.tax, applicable: adjustedFinance.taxRate > 0 }, total_ttc: adjustedFinance.subtotal + adjustedFinance.tax, remises: (financeDocument.recapitulatif?.remises ?? []).map((row: any) => ({ ...row, montant: adjustedFinance.discount })), net_a_payer: adjustedFinance.total }
  } : null;

  const saveApprovedOffer = async (financeJustApproved = false) => {
    if (!activeMarket || !techniqueApproved || (!financeApproved && !financeJustApproved) || !techniqueDocument || !finalFinancial) return;
    setGenerationBusy(true); setGenerationError(''); setGenerationMessage(''); setActiveAction('review');
    try {
      await apiService.createOffer({
        titre: techniqueDocument.titre_offre ?? activeMarket.titre, client: tdrBrief.client.trim().slice(0, 100),
        opportunite_id: activeMarket.id, description: `TDR ${generatedTdr?.titre ?? activeMarket.titre}`,
        trame_technique: JSON.stringify(techniqueDocument), trame_financiere: JSON.stringify(finalFinancial),
        montant_ht: adjustedFinance.subtotal, tva_taux: adjustedFinance.taxRate, statut: 'EN_ATTENTE'
      });
      setFinanceDocument(finalFinancial); setOfferSaved(true); setGenerationMessage('Offre technique et financière enregistrée dans le backend après validation des deux volets.');
    } catch (error) { setGenerationError(error instanceof Error ? error.message : 'Enregistrement de l’offre impossible.'); }
    finally { setGenerationBusy(false); setActiveAction(null); }
  };

  const reviewFinance = async (approve: boolean) => {
    if (!financeReviewId) return;
    if (!approve && reviewNote.trim().length < 3) { setGenerationError('Indiquez le motif du rejet (3 caractères minimum).'); return; }
    setGenerationBusy(true); setGenerationError(''); setGenerationMessage(''); setActiveAction('review');
    try {
      if (approve) {
        if (!finalFinancial) throw new Error('Le document financier est introuvable.');
        const current = (await apiService.getOfferReview(financeReviewId)).review;
        if (current?.status !== 'pending_review' || !current.updated_at) throw new Error('Cette version financière n’est plus en attente de validation.');
        const content = Object.fromEntries(Object.entries(finalFinancial).filter(([key]) => !key.startsWith('_') && !['success', 'metadata'].includes(key)));
        const original = Object.fromEntries(Object.entries(current.data ?? {}).filter(([key]) => !key.startsWith('_') && !['success', 'metadata'].includes(key)));
        if (JSON.stringify(content) !== JSON.stringify(original)) await apiService.updateReviewDocument(financeReviewId, content, current.updated_at);
        await apiService.approveOfferReview(financeReviewId, reviewNote.trim() || 'OK');
        setFinanceDocument(finalFinancial);
        setFinanceApproved(true);
        setGenerationMessage('Offre financière approuvée. Enregistrement dans le backend…');
        await saveApprovedOffer(true);
      }
      else { await apiService.rejectOfferReview(financeReviewId, reviewNote.trim()); setFinanceDocument(null); setFinanceReviewId(''); setFinanceApproved(false); setGenerationMessage('Offre financière rejetée. Corrigez les paramètres et relancez la génération.'); }
      setReviewNote('');
    } catch (error) { setGenerationError(error instanceof Error ? error.message : 'La validation financière a échoué.'); }
    finally { setGenerationBusy(false); setActiveAction(null); }
  };

  const rectifyFinance = async () => {
    const feedback = reviewNote.trim();
    if (!financeReviewId || feedback.length < 5) { setGenerationError('Décrivez les rectifications à demander à l’IA (5 caractères minimum).'); return; }
    if (/^ok[.!\s]*$/i.test(feedback)) { await reviewFinance(true); return; }
    if (!techniqueDocument) return;
    setGenerationBusy(true); setGenerationError(''); setGenerationMessage(''); setActiveAction('financial');
    try {
      const result = await apiService.rectifyOfferFinanciere({
        review_id: financeReviewId, feedback, offre_technique: techniqueDocument,
        options: { nb_participants: financeInputs.participants || offerOptions.participants, type_formateur: offerOptions.trainerType, type_salle: offerOptions.roomType, tva_applicable: offerOptions.vat, inclure_logistique: offerOptions.logistics, inclure_administration: offerOptions.administration }
      });
      const corrected = result.data ?? {};
      if (!result.success || !result.review_id) throw new Error(result.message || 'La nouvelle offre financière n’a pas été créée.');
      setFinanceDocument(corrected); setFinanceReviewId(result.review_id); setFinanceApproved(false); setOfferSaved(false); setReviewNote('');
      const costs = corrected.details_couts ?? {};
      setFinanceInputs(previous => ({
        ...previous,
        trainerRate: Number(costs.honoraires_formateur?.tarif_journalier ?? previous.trainerRate),
        trainerDays: Number(costs.honoraires_formateur?.nb_jours ?? previous.trainerDays),
        roomRate: Number(costs.location_salle?.tarif_journalier ?? previous.roomRate),
        roomDays: Number(costs.location_salle?.nb_jours ?? previous.roomDays),
        supportRate: Number(costs.supports_pedagogiques?.forfait_participant ?? previous.supportRate),
        participants: Number(costs.supports_pedagogiques?.nb_participants ?? previous.participants),
        logistics: Number(costs.logistique?.montant ?? previous.logistics),
        adminPercent: Number(costs.administration?.pourcentage ?? previous.adminPercent)
      }));
      setGenerationMessage('L’offre financière a été révisée par son agent IA. Vérifiez les montants calculés et le document avant de l’approuver.');
    } catch (error) { setGenerationError(error instanceof Error ? error.message : 'La rectification IA de l’offre financière a échoué.'); }
    finally { setGenerationBusy(false); setActiveAction(null); }
  };

  const downloadOffer = (kind: 'technical' | 'financial', format: 'word' | 'pdf') => {
    const doc = kind === 'technical' ? techniqueDocument : financeDocument;
    if (!doc || !((kind === 'technical' && techniqueApproved) || (kind === 'financial' && financeApproved))) return;
    if (kind === 'financial' && !offerSaved) { setGenerationError('Enregistrez d’abord l’offre financière validée pour exporter les montants modifiés.'); return; }
    const title = kind === 'technical' ? 'Offre technique' : 'Offre financière';
    const { titre_offre: _documentTitle, ...offerContent } = doc;
    const markdown = markdownFor(offerContent);
    const documentBody = kind === 'financial' ? financialDocumentHtml(doc) : markdownToExportHtml(markdown);
    const html = `<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="ProgId" content="Word.Document"><meta name="Generator" content="Microsoft Word"><title>${safeHtml(title)}</title><style>
      @page WordSection1{size:595.3pt 841.9pt;margin:56pt 56pt 54pt;mso-footer:yes;mso-header:yes}div.WordSection1{page:WordSection1}
      @page{size:A4;margin:20mm 20mm 19mm;@bottom-left{content:'ALTIORA PREST · Document confidentiel';color:#667085;font:8pt Arial}@bottom-right{content:'Page ' counter(page);color:#667085;font:8pt Arial}}
      *{box-sizing:border-box}body{font-family:Arial,Helvetica,sans-serif;max-width:850px;margin:34px auto;line-height:1.58;color:#202938;background:#fff;font-size:10.5pt}
      .brand-header{border-bottom:3px solid #1B8F6E;padding:0;margin:0 0 30px}.brand-table{width:100%;border-collapse:collapse;margin:0}.brand-table td{border:0;background:transparent;padding:0 0 12px;vertical-align:middle}.brand-table .brand-right{text-align:right}.brand-mark{display:inline-block;padding:8px 9px;margin-right:10px;border-radius:8px;background:#11162A;color:#fff;font-size:10pt;font-weight:800}.brand-name{color:#11162A;font-size:10pt;font-weight:800;letter-spacing:.06em}.brand-sub{display:block;color:#667085;font-size:7.5pt;margin-top:3px}.doc-kind{color:#1B8F6E;font-size:8pt;font-weight:700;letter-spacing:.08em;text-transform:uppercase}
      .cover{padding:4px 0 22px;margin-bottom:22px;border-bottom:1px solid #dfe5eb}.eyebrow{color:#1B8F6E;font-size:8pt;font-weight:700;letter-spacing:.12em;text-transform:uppercase}.cover h1{font-size:27pt;line-height:1.16;color:#11162A;margin:9px 0}.subtitle{font-size:12pt;color:#667085;margin:0 0 18px}.meta-table{width:100%;border-collapse:separate;border-spacing:7px 0;margin:0 0 10px}.meta-table td{width:33.33%;background:#f2f8f6;border:0;border-left:3px solid #1B8F6E;padding:9px 12px;vertical-align:top}.meta-label{display:block;color:#667085;font-size:7.5pt;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px}.meta-value{font-weight:700;color:#11162A;font-size:9pt}
      h1{font-size:22pt;line-height:1.2;color:#11162A;margin:0 0 14px}h2{font-size:14pt;color:#11162A;margin:24px 0 9px;padding-left:10px;border-left:4px solid #1B8F6E;page-break-after:avoid}h3{font-size:11pt;color:#1B8F6E;margin:17px 0 7px;page-break-after:avoid}
      p,li{font-size:10pt}p{margin:0 0 10px}ul,ol{padding-left:23px}li{margin:4px 0}table{border-collapse:collapse;width:100%;margin:12px 0 18px;font-size:9pt;page-break-inside:avoid}th{background:#11162A;color:#fff;text-align:left;padding:8px}td{border-bottom:1px solid #dfe5eb;padding:7px;vertical-align:top}tr:nth-child(even) td{background:#f3f6f8}.financial-table .amount{text-align:right;white-space:nowrap;font-weight:700}.summary-table{max-width:540px;margin-left:auto}.summary-table th{width:62%;background:#f1f4f8;color:#11162A}.summary-table td{text-align:right;white-space:nowrap}.summary-table .grand-total th,.summary-table .grand-total td{background:#e8f4f0;color:#11162A;font-size:10pt;font-weight:800;border-top:2px solid #1B8F6E}.info-table th{width:34%;background:#f1f4f8;color:#11162A}.info-table td{white-space:pre-wrap}.doc-footer{margin-top:32px;padding-top:9px;border-top:1px solid #dfe5eb;color:#667085;font-size:8pt}
      @media print{body{max-width:none;margin:0}.brand-header{margin-bottom:22px}h2,h3{break-after:avoid}tr{break-inside:avoid}}
      </style></head><body><div class="WordSection1"><header class="brand-header"><table class="brand-table"><tbody><tr><td><span class="brand-mark">AP</span><strong class="brand-name">ALTIORA PREST</strong><small class="brand-sub">Cabinet de conseil et de formation</small></td><td class="brand-right"><span class="doc-kind">${kind === 'technical' ? 'Offre technique' : 'Offre financière'}</span></td></tr></tbody></table></header><section class="cover"><span class="eyebrow">Proposition commerciale</span><h1>${safeHtml(title)}</h1><p class="subtitle">${safeHtml(activeMarket?.titre ?? '')}</p><table class="meta-table"><tbody><tr><td><span class="meta-label">Client</span><span class="meta-value">${safeHtml(tdrBrief.client || 'À préciser')}</span></td><td><span class="meta-label">Référence</span><span class="meta-value">${safeHtml(activeMarket?.id.slice(0, 8) ?? '—')}</span></td><td><span class="meta-label">Date d’émission</span><span class="meta-value">${new Date().toLocaleDateString('fr-FR')}</span></td></tr></tbody></table></section><main>${documentBody}</main><footer class="doc-footer">ALTIORA PREST · Antananarivo, Madagascar · Document soumis à validation humaine</footer></div></body></html>`;
    if (format === 'word') downloadBlob(new Blob(['\ufeff', html], { type: 'application/msword;charset=utf-8' }), `${kind === 'technical' ? 'offre-technique' : 'offre-financiere'}-${activeMarket?.id.slice(0, 8)}.doc`);
    else { const popup = window.open('', '_blank'); if (!popup) { setGenerationError('Autorisez la fenêtre d’impression pour enregistrer le PDF.'); return; } popup.document.write(html); popup.document.close(); popup.focus(); popup.print(); }
  };

  const textField = (key: keyof typeof tdrBrief, label: string, type: string = 'text', rows?: number) => (
    <label className="block text-[11px] font-bold uppercase text-slate-600">{label}
      {rows ? <textarea rows={rows} value={tdrBrief[key]} onChange={e => setTdrBrief(prev => ({ ...prev, [key]: e.target.value }))} className="mt-1 w-full p-3 rounded-xl bg-slate-50 border border-slate-300 text-sm font-normal normal-case text-slate-800" />
        : <input type={type} value={tdrBrief[key]} onChange={e => setTdrBrief(prev => ({ ...prev, [key]: e.target.value }))} className="mt-1 w-full px-3 py-2.5 rounded-xl bg-slate-50 border border-slate-300 text-sm font-normal normal-case text-slate-800" />}
    </label>
  );

  const field = (label: string, value: number, key: keyof typeof financeInputs) => <label className="block text-[11px] font-bold text-slate-600">{label}<input type="number" min="0" step="1" value={value} disabled={financeApproved} onChange={e => setFinanceInputs(prev => ({ ...prev, [key]: Number(e.target.value) || 0 }))} className="mt-1 w-full px-3 py-2.5 rounded-xl border border-slate-300 bg-white text-sm text-slate-800 disabled:bg-slate-100 disabled:text-slate-500" /></label>;

  const renderTdrEditor = (value: any, path: (string | number)[] = []): React.ReactNode => {
    if (Array.isArray(value)) return <div className="space-y-2">{value.map((item, index) => <div key={[...path, index].join('.')} className="rounded-lg border border-slate-200 bg-white p-3"><div className="mb-1 text-[10px] font-bold uppercase text-slate-500">Élément {index + 1}</div>{renderTdrEditor(item, [...path, index])}</div>)}</div>;
    if (value && typeof value === 'object') return <div className="space-y-3">{Object.entries(value).map(([key, child]) => <div key={[...path, key].join('.')}><label className="mb-1 block text-[10px] font-bold uppercase text-slate-600">{key.replaceAll('_', ' ')}</label>{renderTdrEditor(child, [...path, key])}</div>)}</div>;
    const shown = value == null ? '' : String(value);
    const saveField = (next: string) => {
      const updatedValue = typeof value === 'number' ? (Number(next) || 0) : next;
      if (path[0] === 'technique') setTechniqueDocument(current => current ? updateAtPath(current, path.slice(1), updatedValue) : current);
      else setGeneratedTdr(current => current ? updateAtPath(current, path, updatedValue) : current);
    };
    return shown.length > 100 || shown.includes('\n')
      ? <textarea key={[...path, 'textarea'].join('.')} defaultValue={shown} onBlur={e => saveField(e.currentTarget.value)} rows={Math.min(8, Math.max(3, shown.split('\n').length))} className="w-full rounded-lg border border-slate-300 bg-white p-2.5 text-sm font-normal normal-case text-slate-800 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-100" />
      : <input key={[...path, 'input'].join('.')} defaultValue={shown} onBlur={e => saveField(e.currentTarget.value)} className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-normal normal-case text-slate-800 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-100" />;
  };

  return <div className="space-y-6 animate-in fade-in duration-300">
    <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
      <div><div className="flex items-center gap-2 mb-1"><span className="px-2.5 py-0.5 rounded text-[11px] font-extrabold bg-blue-100 text-blue-800">Cabinet BPO & Projets Contractuels</span><span className="text-xs text-slate-400 font-medium">• M2 TDR · M3 offres</span></div><h1 className="text-2xl font-extrabold text-[#11162A]">Opportunités & Contrats CRM</h1><p className="text-slate-600 text-xs mt-1">Préparez les documents contractuels à partir d’une opportunité, puis faites valider chaque volet.</p></div>
      {generationBusy && <div className="flex items-center gap-2 text-xs font-semibold text-[#1B8F6E]"><Loader2 className="animate-spin" size={16}/>{activeAction === 'tdr' || activeAction === 'technical' || activeAction === 'financial' ? 'Génération en cours…' : 'Enregistrement…'}</div>}
    </div>

    {generationError && <div role="alert" className="p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs font-semibold">{generationError}</div>}
    {deleteError && <div role="alert" className="p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs font-semibold">{deleteError}</div>}
    {generationMessage && <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold">{generationMessage}</div>}

    <AcceptedMarketsList markets={acceptedMarkets} selectedMarketId={selectedMarketId} onSelectMarket={setSelectedMarketId} onOpenNewOpportunity={onOpenNewOpportunity} onDeleteMarket={(id, title) => void deleteOpportunity(id, title)} canDeleteMarkets={canDeleteOpportunities && !deletingOpportunityId} />

    <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-xs flex flex-wrap gap-2">
      {([['tdr','1. Termes de Référence'],['technical','2. Offre technique'],['financial','3. Offre financière']] as const).map(([id,label]) => <button key={id} onClick={() => setDocTab(id)} className={`px-4 py-2 rounded-lg text-xs font-bold transition-all ${docTab === id ? 'bg-[#11162A] text-white shadow-xs' : 'bg-slate-100 text-slate-600 hover:text-slate-900'}`}>{label}</button>)}
    </div>

    {pendingDocumentReview && <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-blue-200 bg-blue-50 p-4 text-xs text-blue-900">
      <span>Ce document attend votre validation. Les corrections IA et modifications manuelles se font dans l’Espace IA.</span>
      <button type="button" onClick={openDocumentReview} className="rounded-lg bg-blue-800 px-4 py-2 font-bold text-white">Ouvrir la validation IA</button>
    </div>}

    {docTab === 'tdr' && <div className="grid lg:grid-cols-[0.9fr_1.1fr] gap-4">
      <section className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-3"><div><h2 className="font-extrabold text-[#11162A]">Brief TDR prérempli depuis l’opportunité</h2><p className="mt-1 text-[11px] text-slate-500">Complétez les champs métier avant de lancer la génération.</p></div>
        {textField('client','Client / organisme *')}{textField('objectifs','Objectifs et contexte *','text',4)}{textField('public','Public cible *')}
        <div className="grid grid-cols-2 gap-3">{textField('duree','Durée *')}{textField('format','Format')}</div>
        <div className="grid grid-cols-2 gap-3">{textField('budget','Budget estimatif')}{textField('lieu','Lieu')}</div>{textField('deadline','Date limite','date')}
        <label className="flex items-center gap-2 text-xs font-semibold text-slate-700"><input type="checkbox" checked={enrichFromRag} onChange={e => setEnrichFromRag(e.target.checked)} className="accent-[#1B8F6E]"/>Enrichir depuis nos formations passées (RAG)</label>
        <button disabled={!activeMarket || generationBusy} onClick={() => void generateTdr()} className="w-full py-2.5 rounded-xl bg-[#1B8F6E] text-white text-xs font-bold flex items-center justify-center gap-2 disabled:opacity-50"><Sparkles size={15}/>Générer le TDR</button>
      </section>
      <section className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs">
        <div className="flex items-center justify-between gap-3"><h2 className="font-extrabold text-[#11162A]">Aperçu complet du TDR</h2><div className="flex items-center gap-2">{tdrApproved && <span className="px-2 py-1 bg-emerald-50 text-emerald-700 rounded-full text-[10px] font-bold">Approuvé</span>}</div></div>
        {generatedTdr ? <div className="mt-4 max-h-[560px] overflow-auto rounded-xl border border-slate-200 bg-slate-50 p-4">{tdrEditMode ? <><p className="mb-4 rounded-lg bg-blue-50 p-3 text-xs text-blue-800">Modifiez les champs générés ici, puis revenez à l’aperçu pour vérifier le document avant validation.</p>{renderTdrEditor(generatedTdr)}</> : renderMarkdown(`# ${generatedTdr.titre ?? tdrBrief.client}\n\n${markdownFor(generatedTdr)}`)}</div> : <p className="mt-4 p-8 rounded-xl bg-slate-50 border border-slate-200 text-center text-xs text-slate-500">La génération backend affichera ici le contenu complet du TDR.</p>}
        {tdrReviewId && !tdrApproved && <button type="button" disabled={generationBusy} onClick={openDocumentReview} className="mt-4 rounded-lg bg-blue-800 px-4 py-2 text-xs font-bold text-white disabled:opacity-50">Vérifier, modifier ou valider dans l’Espace IA</button>}
        {tdrApproved && <div className="mt-4 flex flex-wrap gap-2">{tdrFiles.docx && <button onClick={() => void apiService.downloadTdr(tdrFiles.docx!).then(blob => downloadBlob(blob, tdrFiles.docx!)).catch(e => setGenerationError(e.message))} className="px-4 py-2 bg-slate-100 rounded-lg text-xs font-bold flex items-center gap-1.5"><Download size={14}/>Télécharger Word</button>}{tdrFiles.pdf && <button onClick={() => void apiService.downloadTdr(tdrFiles.pdf!).then(blob => downloadBlob(blob, tdrFiles.pdf!)).catch(e => setGenerationError(e.message))} className="px-4 py-2 bg-slate-100 rounded-lg text-xs font-bold flex items-center gap-1.5"><Download size={14}/>Télécharger PDF</button>}{!tdrSynchronized && <button disabled={generationBusy} onClick={() => void retryTdrSync()} className="px-4 py-2 bg-amber-50 text-amber-800 rounded-lg text-xs font-bold">Réessayer l’enregistrement backend</button>}</div>}
      </section>
    </div>}

    {docTab === 'technical' && <div className="grid lg:grid-cols-[0.75fr_1.25fr] gap-4">
      <section className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-3"><h2 className="font-extrabold text-[#11162A]">Offre technique</h2><p className="text-xs text-slate-500">La génération est ouverte après validation du TDR.</p><label className="flex items-center gap-2 text-xs font-semibold text-slate-700"><input type="checkbox" checked={includePortfolioRag} onChange={e=>setIncludePortfolioRag(e.target.checked)} className="accent-[#1B8F6E]"/>Inclure notre portfolio de formations passées (RAG)</label><button disabled={!tdrApproved || generationBusy} onClick={() => void generateTechnique()} className="w-full py-2.5 rounded-xl bg-[#1B8F6E] text-white text-xs font-bold flex items-center justify-center gap-2 disabled:opacity-50"><Sparkles size={15}/>Générer l’offre technique</button>{techniqueApproved && <div className="p-3 bg-emerald-50 text-emerald-800 rounded-xl text-xs font-semibold">Volet technique approuvé.</div>}</section>
      <section className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs"><div className="flex justify-between items-center"><h2 className="font-extrabold text-[#11162A]">Aperçu technique</h2><div className="flex items-center gap-2">{techniqueApproved && <span className="px-2 py-1 bg-emerald-50 text-emerald-700 rounded-full text-[10px] font-bold">Approuvé</span>}</div></div>{techniqueDocument ? <div className="mt-3 max-h-[530px] overflow-auto rounded-xl border border-slate-200 bg-slate-50 p-4">{techniqueEditMode ? <><p className="mb-4 rounded-lg bg-blue-50 p-3 text-xs text-blue-800">Modifiez les informations de l’offre technique, puis revenez à l’aperçu avant la validation.</p>{renderTdrEditor(techniqueDocument, ['technique'])}</> : renderMarkdown(`# ${techniqueDocument.titre_offre ?? 'Offre technique'}\n\n${markdownFor(techniqueDocument)}`)}</div> : <p className="mt-3 p-8 rounded-xl bg-slate-50 border border-slate-200 text-center text-xs text-slate-500">L’offre technique générée apparaîtra ici.</p>}{techniqueReviewId && !techniqueApproved && <button type="button" disabled={generationBusy} onClick={openDocumentReview} className="mt-4 rounded-lg bg-blue-800 px-4 py-2 text-xs font-bold text-white disabled:opacity-50">Vérifier, modifier ou valider dans l’Espace IA</button>}{techniqueApproved && <div className="mt-4 flex gap-2"><button onClick={() => downloadOffer('technical','word')} className="px-3 py-2 bg-slate-100 rounded-lg text-xs font-bold"><Download size={13} className="inline mr-1"/>Word</button><button onClick={() => downloadOffer('technical','pdf')} className="px-3 py-2 bg-slate-100 rounded-lg text-xs font-bold">PDF / Imprimer</button></div>}</section>
    </div>}

    {docTab === 'financial' && <div className="space-y-4">
      {!financeDocument && <section className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-3"><h2 className="font-extrabold text-[#11162A]">Paramètres de calcul financier</h2><p className="text-xs text-slate-500">Les catégories de tarif sont celles prises en charge par la grille du backend; la durée et chaque ligne restent ajustables dans le tableau après génération.</p><div className="grid md:grid-cols-4 gap-3"><label className="text-[11px] font-bold text-slate-600">Participants<input type="number" min="1" value={offerOptions.participants} onChange={e=>setOfferOptions(p=>({...p,participants:Math.max(1,Number(e.target.value)||1)}))} className="mt-1 w-full p-2.5 rounded-xl border border-slate-300"/></label><label className="text-[11px] font-bold text-slate-600">Formateur<select value={offerOptions.trainerType} onChange={e=>setOfferOptions(p=>({...p,trainerType:e.target.value}))} className="mt-1 w-full p-2.5 rounded-xl border border-slate-300"><option value="senior">Senior</option><option value="junior">Junior</option></select></label><label className="text-[11px] font-bold text-slate-600">Salle<select value={offerOptions.roomType} onChange={e=>setOfferOptions(p=>({...p,roomType:e.target.value}))} className="mt-1 w-full p-2.5 rounded-xl border border-slate-300"><option value="standard">Standard</option><option value="premium">Premium</option></select></label><label className="text-[11px] font-bold text-slate-600">Durée (jours)<input type="number" min="1" value={financeInputs.trainerDays || ''} onChange={e=>setFinanceInputs(p=>({...p,trainerDays:Number(e.target.value)||0,roomDays:Number(e.target.value)||0}))} className="mt-1 w-full p-2.5 rounded-xl border border-slate-300" placeholder="Selon l’offre technique"/></label></div><div className="flex flex-wrap gap-4 text-xs font-semibold text-slate-700"><label className="flex gap-2 items-center"><input type="checkbox" checked={offerOptions.vat} onChange={e=>setOfferOptions(p=>({...p,vat:e.target.checked}))}/>TVA</label><label className="flex gap-2 items-center"><input type="checkbox" checked={offerOptions.logistics} onChange={e=>setOfferOptions(p=>({...p,logistics:e.target.checked}))}/>Logistique</label><label className="flex gap-2 items-center"><input type="checkbox" checked={offerOptions.administration} onChange={e=>setOfferOptions(p=>({...p,administration:e.target.checked}))}/>Administration</label></div><button disabled={!techniqueApproved || generationBusy} onClick={() => void generateFinance()} className="px-4 py-2.5 rounded-xl bg-[#1B8F6E] text-white text-xs font-bold flex gap-2 items-center disabled:opacity-50"><Sparkles size={15}/>Générer l’offre financière</button>{!techniqueApproved && <p className="text-[11px] text-amber-700">Validez d’abord l’offre technique.</p>}</section>}
      {financeDocument && <div className="grid lg:grid-cols-[1.05fr_0.95fr] gap-4"><section className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs"><div className="flex justify-between items-center mb-3"><h2 className="font-extrabold text-[#11162A]">Tableau financier modifiable</h2>{financeApproved && <span className="px-2 py-1 bg-emerald-50 text-emerald-700 rounded-full text-[10px] font-bold">Approuvé</span>}</div><div className="grid grid-cols-2 gap-3">{field('Jours formateur',financeInputs.trainerDays,'trainerDays')}{field('Tarif/jour formateur (MGA)',financeInputs.trainerRate,'trainerRate')}{field('Jours de salle',financeInputs.roomDays,'roomDays')}{field('Tarif/jour salle (MGA)',financeInputs.roomRate,'roomRate')}{field('Participants',financeInputs.participants,'participants')}{field('Forfait support / personne (MGA)',financeInputs.supportRate,'supportRate')}{field('Frais logistiques (MGA)',financeInputs.logistics,'logistics')}{field('Frais administratifs (%)',financeInputs.adminPercent,'adminPercent')}</div><div className="mt-4 space-y-2 rounded-xl bg-slate-50 p-4 text-xs"><div className="flex justify-between"><span>Honoraires formateur</span><strong>{adjustedFinance.trainer.toLocaleString()} MGA</strong></div><div className="flex justify-between"><span>Location salle</span><strong>{adjustedFinance.room.toLocaleString()} MGA</strong></div><div className="flex justify-between"><span>Supports participants</span><strong>{adjustedFinance.supports.toLocaleString()} MGA</strong></div><div className="flex justify-between"><span>Logistique et administration</span><strong>{(adjustedFinance.logistics+adjustedFinance.admin).toLocaleString()} MGA</strong></div><div className="flex justify-between border-t pt-2"><span>Sous-total HT</span><strong>{adjustedFinance.subtotal.toLocaleString()} MGA</strong></div><div className="flex justify-between"><span>TVA ({adjustedFinance.taxRate}%)</span><strong>{adjustedFinance.tax.toLocaleString()} MGA</strong></div><div className="flex justify-between"><span>Remise</span><strong>−{adjustedFinance.discount.toLocaleString()} MGA</strong></div><div className="flex justify-between border-t pt-2 text-sm font-extrabold text-[#11162A]"><span>Net à payer</span><strong>{adjustedFinance.total.toLocaleString()} MGA</strong></div></div>{financeReviewId && !financeApproved && <button type="button" disabled={generationBusy} onClick={openDocumentReview} className="mt-4 rounded-lg bg-blue-800 px-4 py-2 text-xs font-bold text-white disabled:opacity-50">Vérifier, modifier ou valider dans l’Espace IA</button>}{financeApproved && !offerSaved && <button disabled={generationBusy || !techniqueApproved} onClick={() => void saveApprovedOffer()} className="mt-4 w-full px-4 py-2.5 rounded-xl bg-[#11162A] text-white text-xs font-bold">Enregistrer les deux offres validées</button>}{offerSaved && <div className="mt-4 p-3 bg-emerald-50 text-emerald-800 rounded-xl text-xs font-semibold">Offre enregistrée dans le backend.</div>}</section>
        <section className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs"><div className="flex justify-between items-center"><h2 className="font-extrabold text-[#11162A]">Aperçu de l’offre financière</h2><button onClick={() => void downloadOffer('financial','word')} disabled={!financeApproved || !offerSaved} className="px-3 py-2 bg-slate-100 rounded-lg text-xs font-bold disabled:opacity-50"><Download size={13} className="inline mr-1"/>Word</button></div><div className="mt-3 max-h-[520px] overflow-auto rounded-xl border border-slate-200 bg-slate-50 p-4"><h1 className="mb-4 text-lg font-extrabold text-[#11162A]">{financeDocument.titre_offre ?? 'Offre financière'}</h1><FinancialOfferPreview document={financeDocument}/></div><button disabled={!financeApproved || !offerSaved} onClick={() => downloadOffer('financial','pdf')} className="mt-3 px-3 py-2 bg-slate-100 rounded-lg text-xs font-bold disabled:opacity-50">PDF / Imprimer</button></section></div>}
      {techniqueApproved && financeApproved && <section className="bg-white p-4 rounded-2xl border border-slate-200 shadow-xs flex flex-wrap items-center justify-between gap-3"><p className="text-xs font-bold text-slate-700">Les deux volets sont approuvés. Enregistrez l’offre pour exporter la version financière ajustée.</p><div className="flex flex-wrap gap-2"><button onClick={() => downloadOffer('technical','word')} className="px-3 py-2 bg-slate-100 rounded-lg text-xs font-bold">Word technique</button><button onClick={() => downloadOffer('technical','pdf')} className="px-3 py-2 bg-slate-100 rounded-lg text-xs font-bold">PDF technique / Imprimer</button><button onClick={() => downloadOffer('financial','word')} disabled={!offerSaved} className="px-3 py-2 bg-slate-100 rounded-lg text-xs font-bold disabled:opacity-50">Word financier</button><button onClick={() => downloadOffer('financial','pdf')} disabled={!offerSaved} className="px-3 py-2 bg-[#1B8F6E] text-white rounded-lg text-xs font-bold disabled:opacity-50">PDF financier / Imprimer</button></div></section>}
    </div>}
  </div>;
};
