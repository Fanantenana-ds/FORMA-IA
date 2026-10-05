import React from 'react';
import { TdrDocModel } from '../../types/tdr';

interface TdrFormEditorProps {
  tdrData: TdrDocModel;
  setTdrData: React.Dispatch<React.SetStateAction<TdrDocModel>>;
}

export const TdrFormEditor: React.FC<TdrFormEditorProps> = ({ tdrData, setTdrData }) => {
  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-5 text-xs">
      <h3 className="font-extrabold text-[#11162A] text-sm uppercase tracking-wide border-b border-slate-100 pb-2">
        Édition Rapide des Métadonnées & Paramètres TDR
      </h3>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="font-extrabold text-slate-700 block mb-1">Code Projet *</label>
          <input
            type="text"
            value={tdrData.projetCode}
            onChange={(e) => setTdrData({ ...tdrData, projetCode: e.target.value })}
            className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl font-bold"
          />
        </div>

        <div>
          <label className="font-extrabold text-slate-700 block mb-1">Partenaire Académique / Université *</label>
          <input
            type="text"
            value={tdrData.partenaireAcademic}
            onChange={(e) => setTdrData({ ...tdrData, partenaireAcademic: e.target.value })}
            className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl font-bold"
          />
        </div>

        <div>
          <label className="font-extrabold text-slate-700 block mb-1">Étudiant / Candidat Attribué *</label>
          <input
            type="text"
            value={tdrData.etudiantAssign}
            onChange={(e) => setTdrData({ ...tdrData, etudiantAssign: e.target.value })}
            className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl font-bold"
          />
        </div>

        <div>
          <label className="font-extrabold text-slate-700 block mb-1">Encadreur Professionnel *</label>
          <input
            type="text"
            value={tdrData.encadreurPro}
            onChange={(e) => setTdrData({ ...tdrData, encadreurPro: e.target.value })}
            className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl font-bold"
          />
        </div>
      </div>

      <div>
        <label className="font-extrabold text-slate-700 block mb-1">Intitulé Officiel du Projet *</label>
        <input
          type="text"
          value={tdrData.projetTitre}
          onChange={(e) => setTdrData({ ...tdrData, projetTitre: e.target.value })}
          className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl font-bold text-[#1B8F6E]"
        />
      </div>

      <div>
        <label className="font-extrabold text-slate-700 block mb-1">Justification du Besoin *</label>
        <textarea
          rows={3}
          value={tdrData.justificationBesoin}
          onChange={(e) => setTdrData({ ...tdrData, justificationBesoin: e.target.value })}
          className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl font-medium"
        ></textarea>
      </div>
    </div>
  );
};
