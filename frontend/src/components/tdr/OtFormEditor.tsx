import React from 'react';
import { OtDocModel } from '../../types/tdr';

interface OtFormEditorProps {
  otData: OtDocModel;
  setOtData: React.Dispatch<React.SetStateAction<OtDocModel>>;
}

export const OtFormEditor: React.FC<OtFormEditorProps> = ({ otData, setOtData }) => {
  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-4 text-xs">
      <h3 className="font-extrabold text-[#11162A] text-sm uppercase tracking-wide border-b border-slate-100 pb-2">
        Paramètres Offre Technique & Financière
      </h3>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="font-extrabold text-slate-700 block mb-1">Référence Offre Technique *</label>
          <input
            type="text"
            value={otData.referenceOt}
            onChange={(e) => setOtData({ ...otData, referenceOt: e.target.value })}
            className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl font-bold"
          />
        </div>

        <div>
          <label className="font-extrabold text-slate-700 block mb-1">Client / Destinataire *</label>
          <input
            type="text"
            value={otData.clientOrganisme}
            onChange={(e) => setOtData({ ...otData, clientOrganisme: e.target.value })}
            className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl font-bold"
          />
        </div>

        <div>
          <label className="font-extrabold text-slate-700 block mb-1">Formateur Référent *</label>
          <input
            type="text"
            value={otData.formateurRef}
            onChange={(e) => setOtData({ ...otData, formateurRef: e.target.value })}
            className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl font-bold"
          />
        </div>

        <div>
          <label className="font-extrabold text-slate-700 block mb-1">Budget Total HT (Ariary) *</label>
          <input
            type="number"
            value={otData.budgetTotalAr}
            onChange={(e) => setOtData({ ...otData, budgetTotalAr: Number(e.target.value) })}
            className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl font-extrabold text-[#1B8F6E]"
          />
        </div>
      </div>
    </div>
  );
};
