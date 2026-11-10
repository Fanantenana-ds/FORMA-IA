import React, { useState } from 'react';
import { Mail, Lock, LogIn, UserPlus, CheckCircle2, ShieldCheck, Zap, ReceiptText, ArrowRight, ArrowLeft, Loader2, User, Eye, EyeOff } from 'lucide-react';
import { AuthUser, UserRole, ROLE_LABELS } from '../types';
import { apiService, ApiError } from '../services/api';

interface AuthPageProps {
  onLoginSuccess: (user: AuthUser) => void;
  initialMode?: 'login' | 'register';
  /** Retour vers la page d'accueil publique (optionnel). */
  onBackToHome?: () => void;
}

// Public registration creates a Direction account; the other roles use managed workflows.
const PUBLIC_REGISTRATION_ROLE: UserRole = 'Dir.';
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
      if (err.status === 403) return 'Cette inscription crée un compte Direction. Les autres rôles sont gérés depuis l’espace de la Direction.';
      if (err.status === 422) return 'Les informations saisies ne sont pas valides. Vérifiez le nom et l’adresse e-mail.';
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
  const [showRegPassword, setShowRegPassword] = useState(false);
  const [showRegPasswordConfirm, setShowRegPasswordConfirm] = useState(false);

  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [infoMsg, setInfoMsg] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const passwordMismatch = regPasswordConfirm.length > 0 && regPassword !== regPasswordConfirm;

  const switchMode = (next: 'login' | 'register') => {
    setMode(next);
    setErrorMsg(null);
    setInfoMsg(null);
  };

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setInfoMsg(null);

    const email = loginEmail.trim();
    if (!email || !loginPassword) {
      setErrorMsg('Veuillez remplir votre adresse email et votre mot de passe.');
      return;
    }

    setIsSubmitting(true);
    try {
      const user = await apiService.login(email, loginPassword);
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
      await apiService.register({ nom, email, password: regPassword, role: PUBLIC_REGISTRATION_ROLE });
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
      setInfoMsg('Votre compte Direction est créé. La connexion automatique a échoué ; connectez-vous ci-dessous avec vos identifiants.');
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
      <div className="absolute top-0 left-1/4 w-96 h-96 bg-[#0B1F4D]/15 rounded-full blur-3xl pointer-events-none"></div>
      <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-blue-600/10 rounded-full blur-3xl pointer-events-none"></div>

      {/* LEFT COLUMN: BRANDING & FEATURES (Hidden on mobile) */}
      <div className="hidden lg:flex lg:w-1/2 bg-[#0c1020] p-12 flex-col justify-between border-r border-slate-800/80 relative z-10">
        <div>
          {/* Logo & Header */}
          <div className="flex items-center gap-3.5 mb-12">
            <div className="flex h-12 w-12 items-center justify-center overflow-hidden rounded-2xl border border-white/10 bg-white p-0.5 shadow-xl">
              <img src="/logo_altiora_prest.png" alt="Logo ALTIORA PREST" className="h-full w-full object-contain" />
            </div>
            <div>
              <h1 className="font-extrabold text-2xl tracking-tight text-white">FORMA-IA</h1>
              <p className="text-[10px] uppercase tracking-widest text-slate-300">ALTIORA PREST</p>
              <p className="mt-1 text-xs text-slate-400 font-medium">Gestion du cycle de formation</p>
            </div>
          </div>

          {/* Hero Pitch */}
          <div className="max-w-md space-y-4">
            <h2 className="text-3xl font-extrabold text-white leading-tight tracking-tight">
              Pilotez vos formations avec la puissance de l'Intelligence Artificielle.
            </h2>
            <p className="text-sm text-slate-400 leading-relaxed">
              Un espace pour suivre la veille, préparer les documents et gérer les sessions de formation, avec des accès adaptés aux rôles de l’équipe.
            </p>
          </div>

          {/* Feature Bullets */}
          <div className="mt-10 space-y-4 max-w-md">
            <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 flex items-start gap-3">
              <div className="p-2 rounded-lg bg-[#0B1F4D]/20 text-[#2dd4bf] shrink-0 mt-0.5">
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
        <div className="bg-white rounded-3xl p-6 sm:p-8 shadow-2xl max-w-md w-full border border-slate-100">
          
          {/* Mobile Brand Logo Header */}
          <div className="lg:hidden flex items-center gap-3 mb-6 pb-4 border-b border-slate-100">
            <div className="flex h-11 w-11 items-center justify-center overflow-hidden rounded-xl border border-slate-200 bg-white p-0.5">
              <img src="/logo_altiora_prest.png" alt="Logo ALTIORA PREST" className="h-full w-full object-contain" />
            </div>
            <div>
              <h1 className="font-extrabold text-lg text-[#11162A]">FORMA-IA</h1>
              <p className="text-[11px] text-slate-500">ALTIORA PREST</p>
            </div>
          </div>

          <div className="text-center mb-6">
            <h2 className="text-2xl font-extrabold text-[#11162A] tracking-tight">
              {mode === 'login' ? 'Connexion à FORMA-IA' : 'Créer un compte Direction'}
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              {mode === 'login' 
                ? 'Accédez à votre espace de gestion des formations.'
                : 'Créez l’espace Direction de votre organisme. Les autres rôles sont ajoutés depuis cet espace.'
              }
            </p>
          </div>

          {/* Mode Switcher Tabs */}
          <div className="p-1 bg-slate-100 rounded-2xl grid grid-cols-2 text-xs font-bold mb-6">
            <button
              type="button"
              disabled={isSubmitting}
              onClick={() => switchMode('login')}
              className={`py-2.5 rounded-xl transition-all flex items-center justify-center gap-2 disabled:cursor-not-allowed disabled:opacity-60 ${
                mode === 'login' 
                  ? 'bg-white text-[#11162A] shadow-md font-extrabold' 
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              <LogIn size={15} />
              <span>Connexion</span>
            </button>

            <button
              type="button"
              disabled={isSubmitting}
              onClick={() => switchMode('register')}
              className={`py-2.5 rounded-xl transition-all flex items-center justify-center gap-2 disabled:cursor-not-allowed disabled:opacity-60 ${
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
            <div role="status" aria-live="polite" className="mb-4 p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm font-semibold">
              {infoMsg}
            </div>
          )}

          {errorMsg && (
            <div role="alert" aria-live="assertive" className="mb-4 p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm font-semibold">
              {errorMsg}
            </div>
          )}

          {/* FORM: LOGIN */}
          {mode === 'login' && (
            <form onSubmit={handleLoginSubmit} className="space-y-4 text-xs">
              <div>
                <label htmlFor="login-email" className="mb-1 block text-sm font-semibold text-slate-700">Adresse e-mail professionnelle</label>
                <div className="relative">
                  <Mail size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input
                    id="login-email"
                    type="email"
                    required
                    value={loginEmail}
                    autoComplete="email"
                    onChange={(e) => setLoginEmail(e.target.value)}
                    placeholder="nom@organisation.mg"
                    className="w-full rounded-xl border border-slate-300 bg-white py-3 pl-10 pr-3.5 text-sm text-slate-800 transition-all focus:border-[#06132F] focus:outline-none focus:ring-2 focus:ring-[#06132F]/20"
                  />
                </div>
              </div>

              <div>
                <label htmlFor="login-password" className="mb-1 block text-sm font-semibold text-slate-700">Mot de passe</label>
                <div className="relative">
                  <Lock size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input
                    id="login-password"
                    type="password"
                    required
                    value={loginPassword}
                    autoComplete="current-password"
                    onChange={(e) => setLoginPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full rounded-xl border border-slate-300 bg-white py-3 pl-10 pr-3.5 text-sm text-slate-800 transition-all focus:border-[#06132F] focus:outline-none focus:ring-2 focus:ring-[#06132F]/20"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="mt-2 flex w-full items-center justify-center gap-2 rounded-xl bg-[#06132F] py-3.5 text-sm font-bold text-white shadow-lg shadow-emerald-900/15 transition-all hover:bg-[#06132F] focus:outline-none focus:ring-2 focus:ring-[#06132F] focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isSubmitting ? <Loader2 size={16} className="animate-spin" /> : <ArrowRight size={16} />}
                <span>{isSubmitting ? 'Connexion en cours…' : 'Se connecter'}</span>
              </button>
            </form>
          )}

          {/* FORM: REGISTER */}
          {mode === 'register' && (
            <form onSubmit={handleRegisterSubmit} className="space-y-4">
              <div>
                <label htmlFor="registration-name" className="mb-1 block text-sm font-semibold text-slate-700">Nom complet</label>
                <div className="relative">
                  <User size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input
                    id="registration-name"
                    type="text"
                    required
                    value={regNom}
                    autoComplete="name"
                    autoCapitalize="words"
                    onChange={(e) => { setRegNom(e.target.value); setErrorMsg(null); }}
                    placeholder="Prénom et nom"
                    className="w-full rounded-xl border border-slate-300 bg-white py-3 pl-10 pr-3 text-sm text-slate-800 transition focus:border-[#06132F] focus:outline-none focus:ring-2 focus:ring-[#06132F]/20"
                  />
                </div>
              </div>

              <div>
                <label htmlFor="registration-email" className="mb-1 block text-sm font-semibold text-slate-700">Adresse e-mail professionnelle</label>
                <input
                  id="registration-email"
                  type="email"
                  required
                  value={regEmail}
                  autoComplete="email"
                  autoCapitalize="none"
                  spellCheck={false}
                  onChange={(e) => { setRegEmail(e.target.value); setErrorMsg(null); }}
                  placeholder="nom@organisation.mg"
                  className="w-full rounded-xl border border-slate-300 bg-white px-3 py-3 text-sm text-slate-800 transition focus:border-[#06132F] focus:outline-none focus:ring-2 focus:ring-[#06132F]/20"
                />
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  <label htmlFor="registration-password" className="mb-1 block text-sm font-semibold text-slate-700">Mot de passe</label>
                  <div className="relative">
                    <input
                      id="registration-password"
                      type={showRegPassword ? 'text' : 'password'}
                      required
                      minLength={MIN_PASSWORD_LENGTH}
                      value={regPassword}
                      autoComplete="new-password"
                      aria-describedby="registration-password-hint"
                      onChange={(e) => { setRegPassword(e.target.value); setErrorMsg(null); }}
                      placeholder={`${MIN_PASSWORD_LENGTH} caractères minimum`}
                      className="w-full rounded-xl border border-slate-300 bg-white py-3 pl-3 pr-11 text-sm text-slate-800 transition focus:border-[#06132F] focus:outline-none focus:ring-2 focus:ring-[#06132F]/20"
                    />
                    <button
                      type="button"
                      onClick={() => setShowRegPassword((visible) => !visible)}
                      aria-label={showRegPassword ? 'Masquer le mot de passe' : 'Afficher le mot de passe'}
                      aria-pressed={showRegPassword}
                      className="absolute inset-y-0 right-2 flex items-center rounded-lg px-2 text-slate-500 hover:bg-slate-100 hover:text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#06132F]"
                    >
                      {showRegPassword ? <EyeOff size={17} /> : <Eye size={17} />}
                    </button>
                  </div>
                  <p id="registration-password-hint" className="mt-1.5 text-xs text-slate-500">8 caractères minimum.</p>
                </div>
                <div>
                  <label htmlFor="registration-password-confirm" className="mb-1 block text-sm font-semibold text-slate-700">Confirmer le mot de passe</label>
                  <div className="relative">
                    <input
                      id="registration-password-confirm"
                      type={showRegPasswordConfirm ? 'text' : 'password'}
                      required
                      value={regPasswordConfirm}
                      autoComplete="new-password"
                      aria-invalid={passwordMismatch}
                      aria-describedby={passwordMismatch ? 'registration-password-error' : 'registration-password-confirm-hint'}
                      onChange={(e) => { setRegPasswordConfirm(e.target.value); setErrorMsg(null); }}
                      placeholder="Répétez le mot de passe"
                      className={`w-full rounded-xl border bg-white py-3 pl-3 pr-11 text-sm text-slate-800 transition focus:outline-none focus:ring-2 ${passwordMismatch ? 'border-red-400 focus:border-red-500 focus:ring-red-500/20' : 'border-slate-300 focus:border-[#06132F] focus:ring-[#06132F]/20'}`}
                    />
                    <button
                      type="button"
                      onClick={() => setShowRegPasswordConfirm((visible) => !visible)}
                      aria-label={showRegPasswordConfirm ? 'Masquer la confirmation' : 'Afficher la confirmation'}
                      aria-pressed={showRegPasswordConfirm}
                      className="absolute inset-y-0 right-2 flex items-center rounded-lg px-2 text-slate-500 hover:bg-slate-100 hover:text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#06132F]"
                    >
                      {showRegPasswordConfirm ? <EyeOff size={17} /> : <Eye size={17} />}
                    </button>
                  </div>
                  {passwordMismatch ? (
                    <p id="registration-password-error" className="mt-1.5 text-xs font-medium text-red-700">Les deux mots de passe ne correspondent pas.</p>
                  ) : (
                    <p id="registration-password-confirm-hint" className="mt-1.5 text-xs text-slate-500">Saisissez à nouveau le mot de passe.</p>
                  )}
                </div>
              </div>

              <div>
                <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3.5">
                  <div className="flex items-start gap-3">
                    <div className="rounded-lg bg-emerald-100 p-2 text-[#0B1F4D]">
                      <ShieldCheck size={18} aria-hidden="true" />
                    </div>
                    <div>
                      <p className="text-sm font-bold text-slate-800">Rôle attribué : {ROLE_LABELS[PUBLIC_REGISTRATION_ROLE]}</p>
                      <p className="mt-1 text-xs leading-relaxed text-slate-600">
                        Cette inscription crée un compte Direction. Les comptes Assistant et Comptable sont ajoutés par la Direction ; les comptes Formateur suivent le processus de candidature.
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              <button
                type="submit"
                disabled={isSubmitting || passwordMismatch}
                className="w-full rounded-xl bg-[#06132F] py-3.5 text-sm font-bold text-white shadow-lg shadow-emerald-900/15 transition-all hover:bg-[#06132F] focus:outline-none focus:ring-2 focus:ring-[#06132F] focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <span className="inline-flex items-center justify-center gap-2">
                  {isSubmitting ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle2 size={16} />}
                  {isSubmitting ? 'Création du compte…' : 'Créer mon espace Direction'}
                </span>
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
