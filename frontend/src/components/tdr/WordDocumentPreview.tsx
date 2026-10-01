import React from 'react';
import { TdrDocModel, OtDocModel } from '../../types/tdr';

interface WordDocumentPreviewProps {
  docTab: 'tdr' | 'ot';
  tdrData: TdrDocModel;
  setTdrData: React.Dispatch<React.SetStateAction<TdrDocModel>>;
  otData: OtDocModel;
  setOtData: React.Dispatch<React.SetStateAction<OtDocModel>>;
}

export const WordDocumentPreview: React.FC<WordDocumentPreviewProps> = ({
  docTab,
  tdrData,
  setTdrData,
  otData,
  setOtData
}) => {
  return (
    <div className="bg-white p-8 rounded-2xl border border-slate-200 shadow-lg font-serif leading-relaxed text-slate-800">
      {/* 1. TERMES DE REFERENCE (TDR) WORD TEMPLATE */}
      {docTab === 'tdr' && (
        <div className="space-y-6 animate-in fade-in duration-200">
          {/* Header Stamp */}
          <div className="text-right text-[11px] font-mono text-slate-500 border-b pb-2 border-slate-200">
            {tdrData.projetCode} — {tdrData.clientOrganisme} — {tdrData.versionDate}
          </div>

          <div className="text-center space-y-2 pt-4 pb-6 border-b border-slate-200">
            <span className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full font-sans font-bold text-xs uppercase tracking-wider">
              Document officiel certifié BPF / ENI
            </span>
            <h1 className="text-2xl md:text-3xl font-black text-[#11162A] tracking-tight uppercase font-sans">
              TERMES DE RÉFÉRENCE (TDR)
            </h1>
            <div className="text-base font-bold text-[#1B8F6E]">{tdrData.projetTitre}</div>
          </div>

          {/* Institutional Header */}
          <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 text-xs font-sans space-y-1 text-center font-bold text-slate-700">
            <div>{tdrData.partenaireAcademic}</div>
            <div className="text-[#1B8F6E]">×</div>
            <div>{tdrData.clientOrganisme}</div>
          </div>

          {/* Section 1 : Contexte */}
          <div className="space-y-3 pt-2">
            <h2 className="text-base font-extrabold text-[#11162A] font-sans uppercase border-b-2 border-[#11162A] pb-1">
              1. Contexte Général & Justification
            </h2>

            <div className="space-y-2 text-xs">
              <div>
                <label className="font-sans font-bold text-slate-500 block uppercase text-[10px]">
                  1.1 Présentation du Client
                </label>
                <textarea
                  rows={3}
                  value={tdrData.presentationClient}
                  onChange={(e) => setTdrData({ ...tdrData, presentationClient: e.target.value })}
                  className="w-full p-2 bg-slate-50 border border-slate-200 rounded font-sans text-xs focus:ring-1 focus:ring-[#1B8F6E]"
                />
              </div>

              <div>
                <label className="font-sans font-bold text-slate-500 block uppercase text-[10px]">
                  1.2 Positionnement du Projet VINA
                </label>
                <textarea
                  rows={2}
                  value={tdrData.positionnementProjet}
                  onChange={(e) => setTdrData({ ...tdrData, positionnementProjet: e.target.value })}
                  className="w-full p-2 bg-slate-50 border border-slate-200 rounded font-sans text-xs focus:ring-1 focus:ring-[#1B8F6E]"
                />
              </div>
            </div>
          </div>

          {/* Section 2 : Objectives */}
          <div className="space-y-3">
            <h2 className="text-base font-extrabold text-[#11162A] font-sans uppercase border-b-2 border-[#11162A] pb-1">
              2. Problématique & Objectifs SMART
            </h2>

            <div className="space-y-2 text-xs font-sans">
              <div>
                <label className="font-bold text-slate-500 block uppercase text-[10px]">Problématique clé</label>
                <input
                  type="text"
                  value={tdrData.problematique}
                  onChange={(e) => setTdrData({ ...tdrData, problematique: e.target.value })}
                  className="w-full p-2 bg-slate-50 border border-slate-200 rounded font-medium text-xs"
                />
              </div>

              <div>
                <label className="font-bold text-slate-500 block uppercase text-[10px]">Objectif Général</label>
                <input
                  type="text"
                  value={tdrData.objectifGeneral}
                  onChange={(e) => setTdrData({ ...tdrData, objectifGeneral: e.target.value })}
                  className="w-full p-2 bg-slate-50 border border-slate-200 rounded font-medium text-xs text-[#1B8F6E]"
                />
              </div>
            </div>
          </div>

          {/* Section 3 : Planning Table */}
          <div className="space-y-3 font-sans">
            <h2 className="text-base font-extrabold text-[#11162A] uppercase border-b-2 border-[#11162A] pb-1">
              3. Planning d’Exécution (16 semaines)
            </h2>

            <div className="overflow-x-auto">
              <table className="w-full text-xs border-collapse border border-slate-300">
                <thead className="bg-slate-100 font-bold text-[#11162A]">
                  <tr>
                    <th className="border border-slate-300 p-2 text-left">Phase</th>
                    <th className="border border-slate-300 p-2 text-center w-20">Semaines</th>
                    <th className="border border-slate-300 p-2 text-left">Activités</th>
                    <th className="border border-slate-300 p-2 text-left">Livrables</th>
                  </tr>
                </thead>
                <tbody>
                  {tdrData.planningPhases.map((p, idx) => (
                    <tr key={idx} className="hover:bg-slate-50">
                      <td className="border border-slate-300 p-1.5 font-bold">{p.phase}</td>
                      <td className="border border-slate-300 p-1.5 text-center font-mono">{p.semaines}</td>
                      <td className="border border-slate-300 p-1.5">{p.activites}</td>
                      <td className="border border-slate-300 p-1.5 font-semibold text-[#1B8F6E]">{p.livrable}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Section 6 : Livrables Table */}
          <div className="space-y-3 font-sans">
            <h2 className="text-base font-extrabold text-[#11162A] uppercase border-b-2 border-[#11162A] pb-1">
              6. Tableau Synthetique des Livrables
            </h2>

            <div className="overflow-x-auto">
              <table className="w-full text-xs border-collapse border border-slate-300">
                <thead className="bg-slate-100 font-bold text-[#11162A]">
                  <tr>
                    <th className="border border-slate-300 p-2 text-center w-8">#</th>
                    <th className="border border-slate-300 p-2 text-left">Livrable Attendus</th>
                    <th className="border border-slate-300 p-2 text-center w-20">Échéance</th>
                    <th className="border border-slate-300 p-2 text-left">Destinataire</th>
                    <th className="border border-slate-300 p-2 text-left">Validation</th>
                  </tr>
                </thead>
                <tbody>
                  {tdrData.livrablesTable.map((l, idx) => (
                    <tr key={idx} className="hover:bg-slate-50">
                      <td className="border border-slate-300 p-1.5 text-center font-bold">{l.id}</td>
                      <td className="border border-slate-300 p-1.5 font-medium">{l.livrable}</td>
                      <td className="border border-slate-300 p-1.5 text-center font-mono">{l.echeance}</td>
                      <td className="border border-slate-300 p-1.5">{l.destinataire}</td>
                      <td className="border border-slate-300 p-1.5 font-bold text-emerald-700">{l.validation}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Section 8 : Signatures */}
          <div className="pt-6 border-t-2 border-slate-300 font-sans space-y-4">
            <h2 className="text-base font-extrabold text-[#11162A] uppercase">8. Signatures & Approbations</h2>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs text-center font-bold">
              <div className="p-4 border border-slate-300 rounded bg-slate-50 min-h-[100px] flex flex-col justify-between">
                <span>Candidat / Stagiaire</span>
                <span className="text-[10px] text-slate-400 font-normal">Signature & Date</span>
              </div>

              <div className="p-4 border border-slate-300 rounded bg-slate-50 min-h-[100px] flex flex-col justify-between">
                <span>Encadreur Pro. (ALTIORA)</span>
                <span className="text-[10px] text-slate-400 font-normal">Signature & Date</span>
              </div>

              <div className="p-4 border border-slate-300 rounded bg-slate-50 min-h-[100px] flex flex-col justify-between">
                <span>Encadreur Acad. (ENI)</span>
                <span className="text-[10px] text-slate-400 font-normal">Signature & Date</span>
              </div>

              <div className="p-4 border border-slate-300 rounded bg-slate-50 min-h-[100px] flex flex-col justify-between">
                <span>Direction Général ALTIORA</span>
                <span className="text-[10px] text-slate-400 font-normal">Cachet & Signature</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 2. OFFRE TECHNIQUE (OT) WORD TEMPLATE */}
      {docTab === 'ot' && (
        <div className="space-y-8 animate-in fade-in duration-200 font-sans">
          {/* Top Ref Stamp */}
          <div className="text-right text-[11px] font-mono text-slate-500 border-b pb-2 border-slate-200">
            Réf : {otData.referenceOt} — {otData.clientOrganisme}
          </div>

          <div className="text-center space-y-2 pt-4 pb-6 border-b border-slate-200">
            <span className="px-3 py-1 bg-emerald-100 text-emerald-800 rounded-full font-bold text-xs uppercase tracking-wider">
              Offre Technique & Pédagogique Certifiée
            </span>
            <h1 className="text-2xl md:text-3xl font-black text-[#11162A] tracking-tight uppercase">
              OFFRE TECHNIQUE & BUDGET
            </h1>
            <div className="text-base font-bold text-[#1B8F6E]">{otData.intituleFormation}</div>
          </div>

          {/* Summary Block */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 bg-slate-50 p-4 rounded-lg border border-slate-300 text-xs">
            <div>
              <label className="font-bold text-slate-500 block uppercase text-[10px]">Client / Organisme Destinataire</label>
              <input
                type="text"
                value={otData.clientOrganisme}
                onChange={(e) => setOtData({ ...otData, clientOrganisme: e.target.value })}
                className="w-full font-extrabold text-slate-800 p-1 bg-white border border-slate-200 rounded"
              />
            </div>

            <div>
              <label className="font-bold text-slate-500 block uppercase text-[10px]">Formateur Référent Attribué</label>
              <input
                type="text"
                value={otData.formateurRef}
                onChange={(e) => setOtData({ ...otData, formateurRef: e.target.value })}
                className="w-full font-extrabold text-slate-800 p-1 bg-white border border-slate-200 rounded"
              />
            </div>
          </div>

          {/* Programme Modules */}
          <div className="space-y-3">
            <h2 className="text-base font-extrabold text-[#11162A] uppercase border-b-2 border-[#11162A] pb-1">
              Découpage du Programme Pédagogique
            </h2>

            <div className="space-y-3">
              {otData.programmeModules.map((mod, idx) => (
                <div key={idx} className="p-3 bg-slate-50 rounded border border-slate-300 space-y-1.5 text-xs">
                  <div className="flex items-center justify-between gap-2">
                    <input
                      type="text"
                      value={mod.module}
                      onChange={(e) => {
                        const newM = [...otData.programmeModules];
                        newM[idx].module = e.target.value;
                        setOtData({ ...otData, programmeModules: newM });
                      }}
                      className="font-extrabold text-[#11162A] w-full p-1 bg-white border border-slate-200 rounded"
                    />

                    <input
                      type="text"
                      value={mod.duree}
                      onChange={(e) => {
                        const newM = [...otData.programmeModules];
                        newM[idx].duree = e.target.value;
                        setOtData({ ...otData, programmeModules: newM });
                      }}
                      className="font-mono text-xs w-28 p-1 bg-white border border-slate-200 rounded text-center shrink-0"
                    />
                  </div>

                  <textarea
                    rows={2}
                    value={mod.description}
                    onChange={(e) => {
                      const newM = [...otData.programmeModules];
                      newM[idx].description = e.target.value;
                      setOtData({ ...otData, programmeModules: newM });
                    }}
                    className="w-full text-xs p-1.5 bg-white border border-slate-200 rounded"
                  ></textarea>
                </div>
              ))}
            </div>
          </div>

          {/* Budget Table */}
          <div className="space-y-3">
            <h2 className="text-base font-extrabold text-[#11162A] uppercase border-b-2 border-[#11162A] pb-1">
              Décomposition Budgétaire (Ariary HT)
            </h2>

            <table className="w-full text-xs border-collapse border border-slate-300">
              <thead className="bg-slate-100 text-[#11162A] font-bold">
                <tr>
                  <th className="border border-slate-300 p-2 text-left">Désignation</th>
                  <th className="border border-slate-300 p-2 text-center w-16">Qté</th>
                  <th className="border border-slate-300 p-2 text-right">Prix Unitaire (Ar HT)</th>
                  <th className="border border-slate-300 p-2 text-right">Total (Ar HT)</th>
                </tr>
              </thead>
              <tbody>
                {otData.budgetDetails.map((b, idx) => (
                  <tr key={idx} className="hover:bg-slate-50">
                    <td className="border border-slate-300 p-1.5 font-semibold">{b.designation}</td>
                    <td className="border border-slate-300 p-1.5 text-center font-bold">{b.quantite}</td>
                    <td className="border border-slate-300 p-1.5 text-right font-mono">
                      {b.prixUnitaireAr.toLocaleString()} Ar
                    </td>
                    <td className="border border-slate-300 p-1.5 text-right font-extrabold text-[#11162A]">
                      {b.totalAr.toLocaleString()} Ar
                    </td>
                  </tr>
                ))}
                <tr className="bg-emerald-50/80 font-black text-sm">
                  <td colSpan={3} className="border border-slate-300 p-3 text-right uppercase text-emerald-900">
                    Total Général HT Estimé :
                  </td>
                  <td className="border border-slate-300 p-3 text-right text-[#1B8F6E]">
                    {otData.budgetTotalAr.toLocaleString()} Ar HT
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* Signatures OT */}
          <div className="pt-6 border-t-2 border-slate-300 space-y-4">
            <div className="grid grid-cols-2 gap-4 text-xs font-bold text-center">
              <div className="p-4 border border-slate-300 rounded bg-slate-50 min-h-[100px] flex flex-col justify-between">
                <span>Représentant du Client ({otData.clientOrganisme})</span>
                <span className="text-[10px] text-slate-400 font-normal">Bon pour accord & Signature</span>
              </div>

              <div className="p-4 border border-slate-300 rounded bg-slate-50 min-h-[100px] flex flex-col justify-between">
                <span>Direction Technique FORMA-IA / ALTIORA</span>
                <span className="text-[10px] text-slate-400 font-normal">Cachet & Signature</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
