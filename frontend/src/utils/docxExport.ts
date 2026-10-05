import { TdrDocModel, OtDocModel } from '../types/tdr';

/**
 * Exports TDR or OT data into a native Word document (.doc) file download.
 */
export function exportDocumentToWord(
  docTab: 'tdr' | 'ot',
  tdrData: TdrDocModel,
  otData: OtDocModel,
  clientName: string
) {
  const isTdr = docTab === 'tdr';
  const sanitizedClient = clientName.replace(/[^a-zA-Z0-9]/g, '_');
  const filename = isTdr
    ? `Termes_de_Reference_${sanitizedClient}.doc`
    : `Offre_Technique_${sanitizedClient}.doc`;

  let htmlContent = '';

  if (isTdr) {
    htmlContent = `
      <html xmlns:o='urn:schemas-microsoft-com:office:office' xmlns:w='urn:schemas-microsoft-com:office:word' xmlns='http://www.w3.org/TR/REC-html40'>
      <head>
        <meta charset='utf-8'>
        <title>${tdrData.projetTitre}</title>
        <style>
          body { font-family: 'Calibri', 'Segoe UI', Arial, sans-serif; margin: 30pt; color: #111; line-height: 1.5; }
          .header-stamp { text-align: right; font-size: 9pt; color: #666; font-style: italic; margin-bottom: 20pt; }
          .inst-header { text-align: center; font-size: 11pt; font-weight: bold; color: #003366; margin-bottom: 30pt; }
          .doc-title { text-align: center; font-size: 24pt; font-weight: bold; color: #11162A; margin: 10pt 0; text-transform: uppercase; }
          .doc-subtitle { text-align: center; font-size: 14pt; font-weight: bold; color: #1B8F6E; margin-bottom: 20pt; }
          .meta-box { border: 1px solid #1B8F6E; background-color: #f8faf9; padding: 12pt; margin-bottom: 20pt; }
          h2 { font-size: 14pt; color: #003366; border-bottom: 1.5pt solid #003366; margin-top: 18pt; padding-bottom: 3pt; text-transform: uppercase; }
          p { font-size: 11pt; text-align: justify; }
          ul { margin-left: 15pt; }
          table { width: 100%; border-collapse: collapse; margin-top: 10pt; margin-bottom: 15pt; }
          th, td { border: 1px solid #777; padding: 6pt; font-size: 10pt; text-align: left; }
          th { background-color: #eaf4f1; font-weight: bold; color: #003366; }
          .signatures-block { margin-top: 40pt; }
          .sig-table td { height: 70pt; vertical-align: top; }
        </style>
      </head>
      <body>
        <div class="header-stamp">TDR — ${tdrData.projetCode} — ${tdrData.clientOrganisme} — ${tdrData.versionDate}</div>
        
        <div class="inst-header">
          ${tdrData.partenaireAcademic}<br/>
          ×<br/>
          ${tdrData.clientOrganisme}
        </div>

        <div class="doc-title">TERMES DE RÉFÉRENCE</div>
        <div class="doc-subtitle">${tdrData.projetTitre}</div>

        <div class="meta-box">
          <strong>Code Projet :</strong> ${tdrData.projetCode}<br/>
          <strong>Année Académique :</strong> ${tdrData.anneeAcademique}<br/>
          <strong>Durée de la Prestation :</strong> ${tdrData.dureePrestation}<br/>
          <strong>Dates d’Exécution :</strong> ${tdrData.datesDebutFin}<br/>
          <strong>Candidat / Étudiant :</strong> ${tdrData.etudiantAssign}<br/>
          <strong>Encadreur Professionnel :</strong> ${tdrData.encadreurPro}<br/>
          <strong>Encadreur Académique :</strong> ${tdrData.encadreurAcademic}
        </div>

        <h2>1. Contexte Général</h2>
        <p><strong>1.1 Présentation :</strong> ${tdrData.presentationClient}</p>
        <p><strong>1.2 Positionnement du projet :</strong> ${tdrData.positionnementProjet}</p>
        <p><strong>1.3 Justification du besoin :</strong> ${tdrData.justificationBesoin}</p>

        <h2>2. Problématique et Objectifs</h2>
        <p><strong>2.1 Problématique :</strong> ${tdrData.problematique}</p>
        <p><strong>2.2 Objectif général :</strong> ${tdrData.objectifGeneral}</p>
        <p><strong>2.3 Objectifs Spécifiques SMART :</strong></p>
        <ul>
          ${tdrData.objectifsSMART.map((o) => `<li>${o}</li>`).join('')}
        </ul>

        <h2>3. Planning d’Exécution (16 semaines)</h2>
        <table>
          <thead>
            <tr>
              <th>Phase</th>
              <th>Semaines</th>
              <th>Activités Principales</th>
              <th>Livrable de Phase</th>
            </tr>
          </thead>
          <tbody>
            ${tdrData.planningPhases
              .map(
                (p) => `
              <tr>
                <td><strong>${p.phase}</strong></td>
                <td>${p.semaines}</td>
                <td>${p.activites}</td>
                <td>${p.livrable}</td>
              </tr>`
              )
              .join('')}
          </tbody>
        </table>

        <h2>4. Profil Requis & Compétences</h2>
        <p><strong>Niveau Requis :</strong> ${tdrData.niveauRequis}</p>
        <p><strong>Compétences Techniques :</strong></p>
        <ul>
          ${tdrData.competencesTech.map((c) => `<li>${c}</li>`).join('')}
        </ul>

        <h2>5. Tableau des Livrables</h2>
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Livrables Attendus</th>
              <th>Échéance</th>
              <th>Destinataire</th>
              <th>Validation</th>
            </tr>
          </thead>
          <tbody>
            ${tdrData.livrablesTable
              .map(
                (l) => `
              <tr>
                <td>${l.id}</td>
                <td>${l.livrable}</td>
                <td>${l.echeance}</td>
                <td>${l.destinataire}</td>
                <td><strong>${l.validation}</strong></td>
              </tr>`
              )
              .join('')}
          </tbody>
        </table>

        <h2>6. Grille d’Évaluation</h2>
        <table>
          <thead>
            <tr>
              <th>Critère d’Évaluation</th>
              <th>Pondération (%)</th>
              <th>Évaluateur Référent</th>
            </tr>
          </thead>
          <tbody>
            ${tdrData.grilleEvaluation
              .map(
                (g) => `
              <tr>
                <td>${g.critere}</td>
                <td><strong>${g.poids}</strong></td>
                <td>${g.evaluateur}</td>
              </tr>`
              )
              .join('')}
          </tbody>
        </table>

        <div class="signatures-block">
          <h2>7. Signatures & Approbations</h2>
          <table class="sig-table">
            <tr>
              <td><strong>Candidat / Stagiaire</strong><br/><br/>Date :</td>
              <td><strong>Encadreur Pro (ALTIORA)</strong><br/><br/>Date :</td>
              <td><strong>Encadreur Acad. (ENI)</strong><br/><br/>Date :</td>
              <td><strong>Direction ALTIORA</strong><br/><br/>Date :</td>
            </tr>
          </table>
        </div>
      </body>
      </html>
    `;
  } else {
    htmlContent = `
      <html xmlns:o='urn:schemas-microsoft-com:office:office' xmlns:w='urn:schemas-microsoft-com:office:word' xmlns='http://www.w3.org/TR/REC-html40'>
      <head>
        <meta charset='utf-8'>
        <title>Offre Technique - ${otData.intituleFormation}</title>
        <style>
          body { font-family: 'Calibri', Arial, sans-serif; margin: 30pt; color: #111; line-height: 1.5; }
          .header-stamp { text-align: right; font-size: 9pt; color: #666; font-style: italic; }
          .doc-title { text-align: center; font-size: 22pt; font-weight: bold; color: #11162A; margin: 10pt 0; text-transform: uppercase; }
          .doc-subtitle { text-align: center; font-size: 14pt; font-weight: bold; color: #1B8F6E; margin-bottom: 20pt; }
          h2 { font-size: 13pt; color: #11162A; border-bottom: 1.5pt solid #11162A; margin-top: 15pt; text-transform: uppercase; }
          table { width: 100%; border-collapse: collapse; margin-top: 10pt; }
          th, td { border: 1px solid #777; padding: 6pt; font-size: 10pt; text-align: left; }
          th { background-color: #f1f5f9; font-weight: bold; }
        </style>
      </head>
      <body>
        <div class="header-stamp">Réf: ${otData.referenceOt} — ${otData.clientOrganisme}</div>
        <div class="doc-title">OFFRE TECHNIQUE & FINANCIÈRE</div>
        <div class="doc-subtitle">${otData.intituleFormation}</div>

        <p><strong>Organisme Client :</strong> ${otData.clientOrganisme}</p>
        <p><strong>Formateur Référent :</strong> ${otData.formateurRef}</p>
        <p><strong>Durée Estimée :</strong> ${otData.dureeAtelier}</p>
        <p><strong>Méthodologie Pédagogique :</strong> ${otData.methodologiePedago}</p>

        <h2>Programme de Formation</h2>
        <table>
          <thead>
            <tr><th>Module</th><th>Durée</th><th>Description</th></tr>
          </thead>
          <tbody>
            ${otData.programmeModules
              .map((m) => `<tr><td><strong>${m.module}</strong></td><td>${m.duree}</td><td>${m.description}</td></tr>`)
              .join('')}
          </tbody>
        </table>

        <h2>Décomposition Budgétaire (Ariary HT)</h2>
        <table>
          <thead>
            <tr><th>Désignation</th><th>Qté</th><th>Prix Unitaire</th><th>Total</th></tr>
          </thead>
          <tbody>
            ${otData.budgetDetails
              .map(
                (b) =>
                  `<tr><td>${b.designation}</td><td>${b.quantite}</td><td>${b.prixUnitaireAr.toLocaleString()} Ar</td><td><strong>${b.totalAr.toLocaleString()} Ar</strong></td></tr>`
              )
              .join('')}
            <tr style="background-color: #e2e8f0; font-weight: bold;">
              <td colSpan="3" style="text-align: right;">TOTAL GÉNÉRAL HT :</td>
              <td>${otData.budgetTotalAr.toLocaleString()} Ar HT</td>
            </tr>
          </tbody>
        </table>

        <h2>Garanties & Propriété Intellectuelle</h2>
        <p>${otData.garantiesEtPropretie}</p>
      </body>
      </html>
    `;
  }

  const blob = new Blob(['\ufeff', htmlContent], {
    type: 'application/msword;charset=utf-8'
  });

  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
