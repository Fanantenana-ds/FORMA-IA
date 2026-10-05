import React, { useState } from 'react';
import { Mail, Lock, LogIn, UserPlus, Sparkles, CheckCircle2, ShieldCheck, Zap, ReceiptText, Users, ArrowRight } from 'lucide-react';
import { AuthUser, UserRole } from '../types';

interface AuthPageProps {
  onLoginSuccess: (user: AuthUser) => void;
  initialMode?: 'login' | 'register';
}

export const AuthPage: React.FC<AuthPageProps> = ({
  onLoginSuccess,
  initialMode = 'login'
}) => {
  const [mode, setMode] = useState<'login' | 'register'>(initialMode);

  // Login form state
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');

  // Register form state
  const [regNom, setRegNom] = useState('');
  const [regPrenom, setRegPrenom] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regRole, setRegRole] = useState<UserRole>('Dir.');
  const [regOrg, setRegOrg] = useState('');

  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Quick Demo Logins
  const quickDemoLogin = (role: UserRole) => {
    let demoUser: AuthUser;
    if (role === 'Dir.') {
      demoUser = {
        id: 'user-dir-1',
        nom: 'Raveloson',
        prenom: 'Andry',
        email: 'directeur@forma-ia.mg',
        role: 'Dir.',
        organisation: 'FORMA-IA Madagascar',
        avatarUrl: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&q=80&w=150'
      };
    } else if (role === 'Form.') {
      demoUser = {
        id: 'user-form-1',
        nom: 'Ranaivo',
        prenom: 'Haja',
        email: 'formateur@forma-ia.mg',
        role: 'Form.',
        organisation: 'FORMA-IA Académie',
        avatarUrl: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&q=80&w=150'
      };
    } else {
      demoUser = {
        id: 'user-assis-1',
        nom: 'Razafindrakoto',
        prenom: 'Mialy',
        email: 'assistant@forma-ia.mg',
        role: 'Assis.',
        organisation: 'FORMA-IA Support',
        avatarUrl: 'https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?auto=format&fit=crop&q=80&w=150'
      };
    }

    onLoginSuccess(demoUser);
  };

  const handleLoginSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!loginEmail || !loginPassword) {
      setErrorMsg('Veuillez remplir votre adresse email et votre mot de passe.');
      return;
    }

    let role: UserRole = 'Dir.';
    if (loginEmail.includes('formateur')) role = 'Form.';
    if (loginEmail.includes('assistant')) role = 'Assis.';

    const parts = loginEmail.split('@')[0].split('.');
    const prenom = parts[0] ? parts[0].charAt(0).toUpperCase() + parts[0].slice(1) : 'Utilisateur';
    const nom = parts[1] ? parts[1].charAt(0).toUpperCase() + parts[1].slice(1) : 'FORMA-IA';

    const user: AuthUser = {
      id: `user-${Date.now()}`,
      nom: nom,
      prenom: prenom,
      email: loginEmail,
      role: role,
      organisation: 'FORMA-IA Madagascar'
    };

    onLoginSuccess(user);
  };

  const handleRegisterSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!regNom || !regPrenom || !regEmail || !regPassword) {
      setErrorMsg('Veuillez renseigner tous les champs obligatoires.');
      return;
    }

    const newUser: AuthUser = {
      id: `user-${Date.now()}`,
      nom: regNom,
      prenom: regPrenom,
      email: regEmail,
      role: regRole,
      organisation: regOrg || 'FORMA-IA Madagascar'
    };

    onLoginSuccess(newUser);
  };

  return (
    <div className="min-h-screen w-full bg-[#11162A] flex font-sans text-slate-800 antialiased relative overflow-x-hidden">
      
      {/* Decorative Glow Backgrounds */}
      <div className="absolute top-0 left-1/4 w-96 h-96 bg-[#1B8F6E]/15 rounded-full blur-3xl pointer-events-none"></div>
      <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-blue-600/10 rounded-full blur-3xl pointer-events-none"></div>

      {/* LEFT COLUMN: BRANDING & FEATURES (Hidden on mobile) */}
      <div className="hidden lg:flex lg:w-1/2 bg-[#0c1020] p-12 flex-col justify-between border-r border-slate-800/80 relative z-10">
        <div>
          {/* Logo & Header */}
          <div className="flex items-center gap-3.5 mb-12">
            <div className="w-12 h-12 rounded-2xl bg-[#1B8F6E] flex items-center justify-center font-extrabold text-2xl text-white shadow-xl shadow-[#1B8F6E]/30 tracking-wider border border-white/10">
              FA
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="font-extrabold text-2xl tracking-tight text-white">FORMA-IA</h1>
                <span className="text-[10px] uppercase font-bold tracking-widest px-2 py-0.5 rounded bg-[#1B8F6E]/20 text-[#2dd4bf]">
                  V2.4 PRO
                </span>
              </div>
              <p className="text-xs text-slate-400 font-medium">Plateforme de Gestion de Formation & Veille IA</p>
            </div>
          </div>

          {/* Hero Pitch */}
          <div className="max-w-md space-y-4">
            <h2 className="text-3xl font-extrabold text-white leading-tight tracking-tight">
              Pilotez vos formations avec la puissance de l'Intelligence Artificielle.
            </h2>
            <p className="text-sm text-slate-400 leading-relaxed">
              Consolidez votre activité en temps réel : veille marché automatisée, devis & facturation en Ariary (Ar), suivi des présences et gestion analytique par rôle.
            </p>
          </div>

          {/* Feature Bullets */}
          <div className="mt-10 space-y-4 max-w-md">
            <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 flex items-start gap-3">
              <div className="p-2 rounded-lg bg-[#1B8F6E]/20 text-[#2dd4bf] shrink-0 mt-0.5">
                <ReceiptText size={18} />
              </div>
              <div>
                <h4 className="text-xs font-bold text-white">Facturation & Devis en Ariary (Ar)</h4>
                <p className="text-[11px] text-slate-400 mt-0.5">Génération automatique des pièces comptables avec TVA et suivi des paiements.</p>
              </div>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 flex items-start gap-3">
              <div className="p-2 rounded-lg bg-blue-500/20 text-blue-400 shrink-0 mt-0.5">
                <Zap size={18} />
              </div>
              <div>
                <h4 className="text-xs font-bold text-white">Veille & Opportunités IA</h4>
                <p className="text-[11px] text-slate-400 mt-0.5">Détection proactive des tendances de formation et scoring des opportunités CRM.</p>
              </div>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 flex items-start gap-3">
              <div className="p-2 rounded-lg bg-purple-500/20 text-purple-400 shrink-0 mt-0.5">
                <ShieldCheck size={18} />
              </div>
              <div>
                <h4 className="text-xs font-bold text-white">Accès Multi-Rôles Sécurisé</h4>
                <p className="text-[11px] text-slate-400 mt-0.5">Vues adaptées pour Directeurs, Formateurs référents et Assistants pédagogiques.</p>
              </div>
            </div>
          </div>
        </div>

        {/* Footer info */}
        <div className="pt-6 border-t border-slate-800/60 flex items-center justify-between text-xs text-slate-500">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            <span>Serveur API REST : 127.0.0.1:8000</span>
          </div>
          <span>FORMA-IA © 2026</span>
        </div>
      </div>

      {/* RIGHT COLUMN: LOGIN / REGISTER CARD */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-6 sm:p-12 relative z-10">
        <div className="bg-white rounded-3xl p-8 sm:p-10 shadow-2xl max-w-md w-full border border-slate-100">
          
          {/* Mobile Brand Logo Header */}
          <div className="lg:hidden flex items-center gap-3 mb-6 pb-4 border-b border-slate-100">
            <div className="w-10 h-10 rounded-xl bg-[#1B8F6E] flex items-center justify-center font-extrabold text-xl text-white">
              FA
            </div>
            <div>
              <h1 className="font-extrabold text-lg text-[#11162A]">FORMA-IA</h1>
              <p className="text-[11px] text-slate-500">Plateforme de Gestion IA</p>
            </div>
          </div>

          <div className="text-center mb-6">
            <h2 className="text-2xl font-extrabold text-[#11162A] tracking-tight">
              {mode === 'login' ? 'Espace de Connexion' : 'Créer un Compte'}
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              {mode === 'login' 
                ? 'Accédez à votre tableau de bord et à vos outils de gestion' 
                : 'Inscrivez votre organisme ou rejoignez votre équipe FORMA-IA'
              }
            </p>
          </div>

          {/* Mode Switcher Tabs */}
          <div className="p-1 bg-slate-100 rounded-2xl grid grid-cols-2 text-xs font-bold mb-6">
            <button
              onClick={() => { setMode('login'); setErrorMsg(null); }}
              className={`py-2.5 rounded-xl transition-all flex items-center justify-center gap-2 ${
                mode === 'login' 
                  ? 'bg-white text-[#11162A] shadow-md font-extrabold' 
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              <LogIn size={15} />
              <span>Connexion</span>
            </button>

            <button
              onClick={() => { setMode('register'); setErrorMsg(null); }}
              className={`py-2.5 rounded-xl transition-all flex items-center justify-center gap-2 ${
                mode === 'register' 
                  ? 'bg-white text-[#11162A] shadow-md font-extrabold' 
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              <UserPlus size={15} />
              <span>Inscription</span>
            </button>
          </div>

          {errorMsg && (
            <div className="mb-4 p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs font-semibold">
              {errorMsg}
            </div>
          )}

          {/* FORM: LOGIN */}
          {mode === 'login' && (
            <form onSubmit={handleLoginSubmit} className="space-y-4 text-xs">
              <div>
                <label className="block font-bold text-slate-700 uppercase mb-1">Email Professionnel</label>
                <div className="relative">
                  <Mail size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input
                    type="email"
                    required
                    value={loginEmail}
                    onChange={(e) => setLoginEmail(e.target.value)}
                    placeholder="directeur@forma-ia.mg"
                    className="w-full pl-10 pr-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1B8F6E] transition-all"
                  />
                </div>
              </div>

              <div>
                <label className="block font-bold text-slate-700 uppercase mb-1">Mot de passe</label>
                <div className="relative">
                  <Lock size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input
                    type="password"
                    required
                    value={loginPassword}
                    onChange={(e) => setLoginPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full pl-10 pr-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1B8F6E] transition-all"
                  />
                </div>
              </div>

              <button
                type="submit"
                className="w-full py-3 bg-[#1B8F6E] hover:bg-[#16785c] text-white rounded-xl font-bold text-sm shadow-lg shadow-[#1B8F6E]/20 transition-all flex items-center justify-center gap-2 cursor-pointer mt-2"
              >
                <span>Se connecter</span>
                <ArrowRight size={16} />
              </button>

              {/* DEMO ACCOUNTS QUICK LOGIN */}
              <div className="pt-5 mt-5 border-t border-slate-100">
                <div className="text-[11px] font-extrabold text-slate-500 uppercase mb-2.5 flex items-center gap-1">
                  <Sparkles size={14} className="text-[#1B8F6E]" />
                  <span>Connexion Rapide en 1-Clic (Démonstration) :</span>
                </div>
                
                <div className="grid grid-cols-3 gap-2">
                  <button
                    type="button"
                    onClick={() => quickDemoLogin('Dir.')}
                    className="p-2.5 bg-[#F4F5F3] hover:bg-[#1B8F6E]/10 border border-slate-200 hover:border-[#1B8F6E]/40 rounded-xl text-center transition-all group cursor-pointer"
                  >
                    <div className="font-bold text-xs text-[#11162A] group-hover:text-[#1B8F6E]">Directeur</div>
                    <div className="text-[10px] text-slate-400 mt-0.5">Andry R.</div>
                  </button>

                  <button
                    type="button"
                    onClick={() => quickDemoLogin('Form.')}
                    className="p-2.5 bg-[#F4F5F3] hover:bg-[#1B8F6E]/10 border border-slate-200 hover:border-[#1B8F6E]/40 rounded-xl text-center transition-all group cursor-pointer"
                  >
                    <div className="font-bold text-xs text-[#11162A] group-hover:text-[#1B8F6E]">Formateur</div>
                    <div className="text-[10px] text-slate-400 mt-0.5">Haja R.</div>
                  </button>

                  <button
                    type="button"
                    onClick={() => quickDemoLogin('Assis.')}
                    className="p-2.5 bg-[#F4F5F3] hover:bg-[#1B8F6E]/10 border border-slate-200 hover:border-[#1B8F6E]/40 rounded-xl text-center transition-all group cursor-pointer"
                  >
                    <div className="font-bold text-xs text-[#11162A] group-hover:text-[#1B8F6E]">Assistant</div>
                    <div className="text-[10px] text-slate-400 mt-0.5">Mialy R.</div>
                  </button>
                </div>
              </div>
            </form>
          )}

          {/* FORM: REGISTER */}
          {mode === 'register' && (
            <form onSubmit={handleRegisterSubmit} className="space-y-3.5 text-xs">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-bold text-slate-700 uppercase mb-1">Nom *</label>
                  <input
                    type="text"
                    required
                    value={regNom}
                    onChange={(e) => setRegNom(e.target.value)}
                    placeholder="ex: Rasoanaivo"
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 focus:ring-2 focus:ring-[#1B8F6E] focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block font-bold text-slate-700 uppercase mb-1">Prénom *</label>
                  <input
                    type="text"
                    required
                    value={regPrenom}
                    onChange={(e) => setRegPrenom(e.target.value)}
                    placeholder="ex: Tahina"
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 focus:ring-2 focus:ring-[#1B8F6E] focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block font-bold text-slate-700 uppercase mb-1">Email Professionnel *</label>
                <input
                  type="email"
                  required
                  value={regEmail}
                  onChange={(e) => setRegEmail(e.target.value)}
                  placeholder="t.rasoanaivo@entreprise.mg"
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 focus:ring-2 focus:ring-[#1B8F6E] focus:outline-none"
                />
              </div>

              <div>
                <label className="block font-bold text-slate-700 uppercase mb-1">Mot de passe *</label>
                <input
                  type="password"
                  required
                  value={regPassword}
                  onChange={(e) => setRegPassword(e.target.value)}
                  placeholder="Choisissez un mot de passe"
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 focus:ring-2 focus:ring-[#1B8F6E] focus:outline-none"
                />
              </div>

              <div>
                <label className="block font-bold text-slate-700 uppercase mb-1">Rôle dans la plateforme *</label>
                <div className="grid grid-cols-3 gap-1.5 p-1 bg-slate-100 rounded-xl">
                  <button
                    type="button"
                    onClick={() => setRegRole('Dir.')}
                    className={`py-1.5 rounded-lg font-bold text-xs transition-all ${
                      regRole === 'Dir.' ? 'bg-[#1B8F6E] text-white shadow-xs' : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    Directeur
                  </button>
                  <button
                    type="button"
                    onClick={() => setRegRole('Form.')}
                    className={`py-1.5 rounded-lg font-bold text-xs transition-all ${
                      regRole === 'Form.' ? 'bg-[#1B8F6E] text-white shadow-xs' : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    Formateur
                  </button>
                  <button
                    type="button"
                    onClick={() => setRegRole('Assis.')}
                    className={`py-1.5 rounded-lg font-bold text-xs transition-all ${
                      regRole === 'Assis.' ? 'bg-[#1B8F6E] text-white shadow-xs' : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    Assistant
                  </button>
                </div>
              </div>

              <div>
                <label className="block font-bold text-slate-700 uppercase mb-1">Organisme / Entreprise</label>
                <input
                  type="text"
                  value={regOrg}
                  onChange={(e) => setRegOrg(e.target.value)}
                  placeholder="ex: FORMA-IA Mada / TELMA"
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 focus:ring-2 focus:ring-[#1B8F6E] focus:outline-none"
                />
              </div>

              <button
                type="submit"
                className="w-full py-3 bg-[#1B8F6E] hover:bg-[#16785c] text-white rounded-xl font-bold text-xs shadow-lg shadow-[#1B8F6E]/20 transition-all flex items-center justify-center gap-2 cursor-pointer mt-2"
              >
                <CheckCircle2 size={16} />
                <span>Créer mon compte et accéder à la plateforme</span>
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
