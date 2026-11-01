import React, { useState } from 'react';
import { Mail, Lock, LogIn, UserPlus, CheckCircle2, ShieldCheck, Zap, ReceiptText, ArrowRight, ArrowLeft, Loader2, User } from 'lucide-react';
import { AuthUser, UserRole, ROLE_LABELS } from '../types';
import { apiService, ApiError } from '../services/api';

interface AuthPageProps {
  onLoginSuccess: (user: AuthUser) => void;
  initialMode?: 'login' | 'register';
  /** Retour vers la page d'accueil publique (optionnel). */
  onBackToHome?: () => void;
}

// Public registration is only for the initial company director account.
// Team and trainer accounts are created from their authenticated workflows.
const ROLE_CHOICES: UserRole[] = ['Dir.'];
const MIN_PASSWORD_LENGTH = 8;

/** Traduit une erreur de l'API en message affichable. */
const describeAuthError = (err: unknown, context: 'login' | 'register'): string => {
  if (err instanceof ApiError) {
    if (err.status === 0) return err.message;
    if (context === 'login') {
      if (err.status === 401) return 'Email ou mot de passe incorrect.';
      if (err.status === 403) return 'Ce compte est désactivé. Contactez la direction.';
    }
    if (context === 'register') {
      if (err.status === 400) return 'Cet email est déjà associé à un compte.';
      if (err.status === 422) return `Informations invalides : ${err.message}`;
    }
    if (err.status >= 500) return 'Erreur du serveur. Veuillez réessayer dans un instant.';
    return err.message;
  }
  return 'Une erreur inattendue est survenue. Veuillez réessayer.';
};

export const AuthPage: React.FC<AuthPageProps> = ({
  onLoginSuccess,
  initialMode = 'login',
  onBackToHome
}) => {
  const [mode, setMode] = useState<'login' | 'register'>(initialMode);

  // Login form state
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');

  // Register form state
  const [regNom, setRegNom] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regPasswordConfirm, setRegPasswordConfirm] = useState('');
  const [regRole, setRegRole] = useState<UserRole>('Assis.');

  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [infoMsg, setInfoMsg] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const switchMode = (next: 'login' | 'register') => {
    setMode(next);
    setErrorMsg(null);
    setInfoMsg(null);
  };

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setInfoMsg(null);

    if (!loginEmail.trim() || !loginPassword) {
      setErrorMsg('Veuillez remplir votre adresse email et votre mot de passe.');
      return;
    }

    setIsSubmitting(true);
    try {
      const user = await apiService.login(loginEmail.trim(), loginPassword);
      onLoginSuccess(user);
    } catch (err) {
      setErrorMsg(describeAuthError(err, 'login'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRegisterSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setInfoMsg(null);

    const nom = regNom.trim();
    const email = regEmail.trim();

    if (!nom || !email || !regPassword) {
      setErrorMsg('Veuillez renseigner tous les champs obligatoires.');
      return;
    }
    if (regPassword.length < MIN_PASSWORD_LENGTH) {
      setErrorMsg(`Le mot de passe doit contenir au moins ${MIN_PASSWORD_LENGTH} caractères.`);
      return;
    }
    if (regPassword !== regPasswordConfirm) {
      setErrorMsg('Les deux mots de passe ne correspondent pas.');
      return;
    }

    setIsSubmitting(true);
    try {
      await apiService.register({ nom, email, password: regPassword, role: regRole });
    } catch (err) {
      setErrorMsg(describeAuthError(err, 'register'));
      setIsSubmitting(false);
      return;
    }

    // Compte créé : connexion automatique
    try {
      const user = await apiService.login(email, regPassword);
      onLoginSuccess(user);
    } catch (err) {
      setLoginEmail(email);
      setLoginPassword('');
      setMode('login');
      setInfoMsg('Votre compte a bien été créé. Connectez-vous pour accéder à la plateforme.');
      if (err instanceof ApiError && err.status === 0) {
        setErrorMsg(err.message);
      }
    } finally {
      setIsSubmitting(false);
    }
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
        <div className="pt-6 border-t border-slate-800/60 flex items-center justify-end text-xs text-slate-500">
          <span>FORMA-IA © 2026</span>
        </div>
      </div>

      {/* RIGHT COLUMN: LOGIN / REGISTER CARD */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-6 sm:p-12 relative z-10">
        {onBackToHome && (
          <button
            type="button"
            onClick={onBackToHome}
            className="absolute top-5 left-5 sm:top-6 sm:left-6 inline-flex items-center gap-2 text-xs font-semibold text-slate-300 hover:text-white bg-white/5 hover:bg-white/10 border border-white/10 px-3 py-2 rounded-lg transition"
          >
            <ArrowLeft size={14} />
            Retour à l'accueil
          </button>
        )}
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
              onClick={() => switchMode('login')}
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
              onClick={() => switchMode('register')}
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

          {infoMsg && (
            <div className="mb-4 p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold">
              {infoMsg}
            </div>
          )}

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
                    autoComplete="email"
                    onChange={(e) => setLoginEmail(e.target.value)}
                    placeholder="nom@organisation.mg"
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
                    autoComplete="current-password"
                    onChange={(e) => setLoginPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full pl-10 pr-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1B8F6E] transition-all"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full py-3 bg-[#1B8F6E] hover:bg-[#16785c] text-white rounded-xl font-bold text-sm shadow-lg shadow-[#1B8F6E]/20 transition-all flex items-center justify-center gap-2 cursor-pointer mt-2 disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {isSubmitting ? <Loader2 size={16} className="animate-spin" /> : <ArrowRight size={16} />}
                <span>{isSubmitting ? 'Connexion en cours…' : 'Se connecter'}</span>
              </button>
            </form>
          )}

          {/* FORM: REGISTER */}
          {mode === 'register' && (
            <form onSubmit={handleRegisterSubmit} className="space-y-3.5 text-xs">
              <div>
                <label className="block font-bold text-slate-700 uppercase mb-1">Nom complet *</label>
                <div className="relative">
                  <User size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input
                    type="text"
                    required
                    value={regNom}
                    autoComplete="name"
                    onChange={(e) => setRegNom(e.target.value)}
                    placeholder="Prénom et nom"
                    className="w-full pl-10 pr-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 focus:ring-2 focus:ring-[#1B8F6E] focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block font-bold text-slate-700 uppercase mb-1">Email Professionnel *</label>
                <input
                  type="email"
                  required
                  value={regEmail}
                  autoComplete="email"
                  onChange={(e) => setRegEmail(e.target.value)}
                  placeholder="nom@organisation.mg"
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 focus:ring-2 focus:ring-[#1B8F6E] focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-bold text-slate-700 uppercase mb-1">Mot de passe *</label>
                  <input
                    type="password"
                    required
                    minLength={MIN_PASSWORD_LENGTH}
                    value={regPassword}
                    autoComplete="new-password"
                    onChange={(e) => setRegPassword(e.target.value)}
                    placeholder={`${MIN_PASSWORD_LENGTH} caractères min.`}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 focus:ring-2 focus:ring-[#1B8F6E] focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block font-bold text-slate-700 uppercase mb-1">Confirmation *</label>
                  <input
                    type="password"
                    required
                    value={regPasswordConfirm}
                    autoComplete="new-password"
                    onChange={(e) => setRegPasswordConfirm(e.target.value)}
                    placeholder="Répétez le mot de passe"
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 focus:ring-2 focus:ring-[#1B8F6E] focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block font-bold text-slate-700 uppercase mb-1">Rôle dans la plateforme *</label>
                <div className="grid grid-cols-2 gap-1.5 p-1 bg-slate-100 rounded-xl">
                  {ROLE_CHOICES.map((role) => (
                    <button
                      key={role}
                      type="button"
                      onClick={() => setRegRole(role)}
                      className={`py-1.5 rounded-lg font-bold text-xs transition-all ${
                        regRole === role ? 'bg-[#1B8F6E] text-white shadow-xs' : 'text-slate-600 hover:text-slate-900'
                      }`}
                    >
                      {ROLE_LABELS[role]}
                    </button>
                  ))}
                </div>
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full py-3 bg-[#1B8F6E] hover:bg-[#16785c] text-white rounded-xl font-bold text-xs shadow-lg shadow-[#1B8F6E]/20 transition-all flex items-center justify-center gap-2 cursor-pointer mt-2 disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {isSubmitting ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle2 size={16} />}
                <span>{isSubmitting ? 'Création du compte…' : 'Créer mon compte et accéder à la plateforme'}</span>
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
