import React, { useState } from 'react';
import {
  Mail, Lock, ArrowRight, ArrowLeft, Loader2, BrainCircuit,
  Eye, EyeOff, Sparkles, Shield, Zap
} from 'lucide-react';
import { AuthUser } from '../types';
import { apiService, ApiError } from '../services/api';

interface AuthPageProps {
  onLoginSuccess: (user: AuthUser) => void;
  initialMode?: 'login' | 'register';
  onBackToHome?: () => void;
}

const describeAuthError = (err: unknown): string => {
  if (err instanceof ApiError) {
    if (err.status === 0) return err.message;
    if (err.status === 401) return 'Email ou mot de passe incorrect.';
    if (err.status === 403) return 'Ce compte est désactivé. Contactez la direction.';
    if (err.status >= 500) return 'Erreur du serveur. Veuillez réessayer dans un instant.';
    return err.message;
  }
  return 'Une erreur inattendue est survenue. Veuillez réessayer.';
};

export const AuthPage: React.FC<AuthPageProps> = ({ onLoginSuccess, onBackToHome }) => {
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
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
      setErrorMsg(describeAuthError(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex font-sans antialiased overflow-hidden">

      {/* ══════════════ LEFT PANEL — PREMIUM ══════════════ */}
      <div className="hidden lg:flex lg:w-[55%] relative flex-col items-center justify-center overflow-hidden"
        style={{ background: 'linear-gradient(160deg, #020810 0%, #050F22 30%, #081528 55%, #0B1F4D 80%, #0d2460 100%)' }}>

        {/* ── Grille fine dorée ── */}
        <svg className="absolute inset-0 w-full h-full pointer-events-none" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <pattern id="finegrid" width="60" height="60" patternUnits="userSpaceOnUse">
              <path d="M 60 0 L 0 0 0 60" fill="none" stroke="#D4AF37" strokeWidth="0.5" opacity="0.08"/>
            </pattern>
            <pattern id="finedots" width="120" height="120" patternUnits="userSpaceOnUse">
              <circle cx="60" cy="60" r="1" fill="#D4AF37" opacity="0.12"/>
            </pattern>
            {/* Anneau central */}
            <radialGradient id="ringGrad" cx="50%" cy="50%" r="50%">
              <stop offset="40%" stopColor="transparent"/>
              <stop offset="70%" stopColor="#D4AF37" stopOpacity="0.06"/>
              <stop offset="100%" stopColor="transparent"/>
            </radialGradient>
          </defs>
          <rect width="100%" height="100%" fill="url(#finegrid)"/>
          <rect width="100%" height="100%" fill="url(#finedots)"/>
          {/* Cercles concentriques — rotation lente */}
          <g style={{ transformOrigin: '50% 50%', animation: 'rotateDisc 40s linear infinite' }}>
            <circle cx="50%" cy="50%" r="260" fill="none" stroke="#D4AF37" strokeWidth="0.6" opacity="0.07"
              strokeDasharray="8 16"/>
          </g>
          <g style={{ transformOrigin: '50% 50%', animation: 'rotateDisc 60s linear infinite reverse' }}>
            <circle cx="50%" cy="50%" r="360" fill="none" stroke="#D4AF37" strokeWidth="0.5" opacity="0.045"
              strokeDasharray="4 20"/>
          </g>
          <g style={{ transformOrigin: '50% 50%', animation: 'rotateDisc 80s linear infinite' }}>
            <circle cx="50%" cy="50%" r="460" fill="none" stroke="#38BDF8" strokeWidth="0.5" opacity="0.035"
              strokeDasharray="6 24"/>
          </g>
          {/* Lignes croisées */}
          <line x1="0%" y1="0%" x2="100%" y2="100%" stroke="#D4AF37" strokeWidth="0.5" opacity="0.04"/>
          <line x1="100%" y1="0%" x2="0%" y2="100%" stroke="#D4AF37" strokeWidth="0.5" opacity="0.03"/>
          {/* Particules flottantes animées */}
          <circle cx="12%" cy="18%" r="1.5" fill="#D4AF37"
            style={{ animation: 'floatParticle1 7s ease-in-out infinite' }} opacity="0.4"/>
          <circle cx="88%" cy="10%" r="2"   fill="#D4AF37"
            style={{ animation: 'floatParticle2 9s ease-in-out infinite 1s' }} opacity="0.3"/>
          <circle cx="94%" cy="52%" r="1.2" fill="#38BDF8"
            style={{ animation: 'floatParticle3 6s ease-in-out infinite 2s' }} opacity="0.35"/>
          <circle cx="75%" cy="82%" r="1.8" fill="#D4AF37"
            style={{ animation: 'floatParticle1 11s ease-in-out infinite 3s' }} opacity="0.25"/>
          <circle cx="20%" cy="88%" r="1.5" fill="#D4AF37"
            style={{ animation: 'floatParticle2 8s ease-in-out infinite 0.5s' }} opacity="0.3"/>
          <circle cx="6%"  cy="68%" r="1"   fill="#38BDF8"
            style={{ animation: 'floatParticle3 10s ease-in-out infinite 4s' }} opacity="0.25"/>
          <circle cx="50%" cy="8%"  r="1.2" fill="#D4AF37"
            style={{ animation: 'floatParticle1 8s ease-in-out infinite 1.5s' }} opacity="0.3"/>
          <circle cx="40%" cy="92%" r="1"   fill="#38BDF8"
            style={{ animation: 'floatParticle2 12s ease-in-out infinite 2.5s' }} opacity="0.2"/>
        </svg>

        {/* ── Halos animés ── */}
        {/* Halo or haut-gauche — pulse lent */}
        <div className="absolute -top-40 -left-40 w-[600px] h-[600px] rounded-full pointer-events-none"
          style={{
            background: 'radial-gradient(circle, rgba(212,175,55,0.14) 0%, rgba(212,175,55,0.03) 50%, transparent 70%)',
            animation: 'pulseHalo 6s ease-in-out infinite',
          }} />
        {/* Halo cyan droite — pulse décalé */}
        <div className="absolute top-1/3 -right-32 w-[450px] h-[450px] rounded-full pointer-events-none"
          style={{
            background: 'radial-gradient(circle, rgba(56,189,248,0.1) 0%, transparent 65%)',
            animation: 'pulseHaloAlt 8s ease-in-out infinite 2s',
          }} />
        {/* Halo or bas — drift */}
        <div className="absolute -bottom-20 left-1/3 w-[380px] h-[380px] rounded-full pointer-events-none"
          style={{
            background: 'radial-gradient(circle, rgba(212,175,55,0.08) 0%, transparent 65%)',
            animation: 'driftLeft 10s ease-in-out infinite',
          }} />
        {/* Halo central — drift inverse */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] rounded-full pointer-events-none"
          style={{
            background: 'radial-gradient(circle, rgba(212,175,55,0.04) 50%, transparent 80%)',
            animation: 'driftRight 12s ease-in-out infinite 1s',
          }} />

        {/* ── Ligne lumineuse haut ── */}
        <div className="absolute top-0 left-0 right-0 h-[2px] overflow-hidden pointer-events-none"
          style={{ background: 'linear-gradient(90deg, transparent 0%, rgba(212,175,55,0.3) 25%, rgba(212,175,55,0.7) 50%, rgba(212,175,55,0.3) 75%, transparent 100%)' }}>
          <div className="absolute inset-y-0 w-1/4"
            style={{
              background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.9), transparent)',
              animation: 'shimmerLine 3s ease-in-out infinite',
            }} />
        </div>
        {/* ── Ligne lumineuse gauche ── */}
        <div className="absolute top-0 bottom-0 left-0 w-[2px] pointer-events-none"
          style={{ background: 'linear-gradient(180deg, rgba(212,175,55,0.8) 0%, rgba(212,175,55,0.1) 40%, transparent 100%)' }} />

        {/* ══ CONTENU CENTRÉ ══ */}
        <div className="relative z-10 flex flex-col items-center text-center px-12 py-10 max-w-xl w-full">

          {/* Logo monument */}
          <div className="mb-8 relative">
            {/* Anneau externe lumineux */}
            <div className="absolute -inset-3 rounded-3xl pointer-events-none"
              style={{ background: 'radial-gradient(circle, rgba(212,175,55,0.15) 0%, transparent 70%)' }} />
            <div className="relative flex h-24 w-24 items-center justify-center overflow-hidden rounded-3xl bg-white mx-auto"
              style={{
                boxShadow: '0 0 0 1px rgba(212,175,55,0.4), 0 0 0 4px rgba(212,175,55,0.08), 0 20px 60px rgba(0,0,0,0.6), 0 0 40px rgba(212,175,55,0.2)',
              }}>
              <img src="/logo_altiora_prest.png" alt="Logo ALTIORA PREST" className="h-[80%] w-[80%] object-contain" />
              {/* Reflet haut */}
              <div className="absolute top-0 left-0 right-0 h-1/2 rounded-t-3xl pointer-events-none"
                style={{ background: 'linear-gradient(180deg, rgba(255,255,255,0.2) 0%, transparent 100%)' }} />
            </div>
          </div>

          {/* Nom + sous-titre */}
          <div className="mb-2">
            <h1 className="font-black text-5xl tracking-tight text-white leading-none"
              style={{ textShadow: '0 0 60px rgba(212,175,55,0.3), 0 4px 20px rgba(0,0,0,0.5)' }}>
              FORMA<span style={{
                background: 'linear-gradient(135deg, #FDE68A, #D4AF37)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
              }}>-IA</span>
            </h1>
            <div className="mt-2 flex items-center justify-center gap-3">
              <div className="h-px flex-1 max-w-[60px]"
                style={{ background: 'linear-gradient(90deg, transparent, rgba(212,175,55,0.5))' }} />
              <p className="text-[11px] uppercase tracking-[0.3em] font-bold"
                style={{ color: 'rgba(212,175,55,0.7)' }}>ALTIORA PREST</p>
              <div className="h-px flex-1 max-w-[60px]"
                style={{ background: 'linear-gradient(90deg, rgba(212,175,55,0.5), transparent)' }} />
            </div>
          </div>

          {/* Badge IA */}
          <div className="mt-5 mb-8 inline-flex items-center gap-2.5 rounded-full px-5 py-2.5"
            style={{
              background: 'linear-gradient(135deg, rgba(212,175,55,0.14) 0%, rgba(212,175,55,0.05) 100%)',
              border: '1px solid rgba(212,175,55,0.35)',
              boxShadow: '0 0 20px rgba(212,175,55,0.1), inset 0 1px 0 rgba(212,175,55,0.15)',
            }}>
            <div className="relative flex h-3.5 w-3.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-50"
                style={{ background: '#D4AF37' }}/>
              <span className="relative inline-flex rounded-full h-3.5 w-3.5"
                style={{ background: '#D4AF37' }}/>
            </div>
            <span className="text-xs font-bold uppercase tracking-[0.15em]"
              style={{ color: 'rgba(212,175,55,0.95)' }}>
              Gestion intelligente des formations
            </span>
          </div>

          {/* Tagline principal */}
          <h2 className="text-[42px] font-black leading-[1.1] tracking-tight mb-4"
            style={{ textShadow: '0 4px 40px rgba(0,0,0,0.5)' }}>
            <span className="text-white">Pilotez le cycle</span>
            <br />
            <span style={{
              background: 'linear-gradient(135deg, #FDE68A 0%, #F59E0B 30%, #D4AF37 60%, #FDE68A 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
              filter: 'drop-shadow(0 2px 12px rgba(212,175,55,0.5))',
            }}>
              de vos formations
            </span>
          </h2>

          <p className="text-sm text-white/45 leading-relaxed max-w-sm mb-10">
            De la détection du marché à la facturation chaque étape assistée par l'IA avec validation humaine intégrée.
          </p>

          {/* 3 feature cards horizontales */}
          <div className="w-full grid grid-cols-3 gap-3 mb-10">
            {[
              { icon: Sparkles, title: 'Détection IA', desc: 'Veille & opportunités', color: '#D4AF37' },
              { icon: Zap,      title: 'Automatisé',   desc: 'TDR, offres, devis',    color: '#38BDF8' },
              { icon: Shield,   title: 'Sécurisé',     desc: 'Rôles & accès',         color: '#A78BFA' },
            ].map(({ icon: Icon, title, desc, color }) => (
              <div key={title} className="flex flex-col items-center gap-2 rounded-2xl px-3 py-4"
                style={{
                  background: 'rgba(255,255,255,0.03)',
                  border: '1px solid rgba(255,255,255,0.07)',
                  backdropFilter: 'blur(12px)',
                }}>
                <div className="flex h-9 w-9 items-center justify-center rounded-xl"
                  style={{ background: `${color}18`, border: `1px solid ${color}30`, boxShadow: `0 0 12px ${color}20` }}>
                  <Icon size={16} style={{ color, filter: `drop-shadow(0 0 4px ${color}80)` }} />
                </div>
                <p className="text-xs font-bold text-white/85 leading-none">{title}</p>
                <p className="text-[10px] text-white/35 leading-none">{desc}</p>
              </div>
            ))}
          </div>

          {/* Stats bar */}
          <div className="w-full flex items-center justify-center gap-6 py-4 px-6 rounded-2xl mb-8"
            style={{
              background: 'rgba(255,255,255,0.025)',
              border: '1px solid rgba(255,255,255,0.06)',
            }}>
            {[
              { val: 'IA', label: 'Assisté' },
              { val: '4', label: 'Rôles' },
              { val: 'Ar', label: 'Facturation' },
              { val: 'MG', label: 'Madagascar' },
            ].map(({ val, label }, i) => (
              <React.Fragment key={label}>
                {i > 0 && <div className="h-6 w-px" style={{ background: 'rgba(255,255,255,0.08)' }} />}
                <div className="flex flex-col items-center gap-0.5">
                  <span className="text-base font-black leading-none"
                    style={{ color: '#D4AF37', textShadow: '0 0 10px rgba(212,175,55,0.5)' }}>{val}</span>
                  <span className="text-[9px] uppercase tracking-widest text-white/30">{label}</span>
                </div>
              </React.Fragment>
            ))}
          </div>

          {/* Footer */}
          <div className="flex items-center gap-3 w-full">
            <div className="h-px flex-1" style={{ background: 'linear-gradient(90deg, transparent, rgba(212,175,55,0.3))' }} />
            <span className="text-[10px] uppercase tracking-[0.2em] font-semibold" style={{ color: 'rgba(212,175,55,0.3)' }}>
              FORMA-IA © 2026
            </span>
            <div className="h-px flex-1" style={{ background: 'linear-gradient(90deg, rgba(212,175,55,0.3), transparent)' }} />
          </div>
        </div>
      </div>

      {/* ══════════════ RIGHT PANEL ══════════════ */}
      <div className="w-full lg:w-[45%] flex items-center justify-center bg-[#F4F5F7] p-6 sm:p-10 relative">

        {onBackToHome && (
          <button
            type="button"
            onClick={onBackToHome}
            className="absolute top-5 left-5 inline-flex items-center gap-2 text-xs font-semibold text-slate-500 hover:text-slate-800 bg-white border border-slate-200 hover:border-slate-300 px-3 py-2 rounded-lg transition shadow-sm"
          >
            <ArrowLeft size={13} />
            Retour à l'accueil
          </button>
        )}

        <div className="w-full max-w-sm">

          {/* Mobile logo */}
          <div className="lg:hidden flex items-center gap-3 mb-8">
            <div className="flex h-12 w-12 items-center justify-center overflow-hidden rounded-xl border border-slate-200 bg-white p-0.5">
              <img src="/logo_altiora_prest.png" alt="Logo" className="h-full w-full object-contain" />
            </div>
            <div>
              <p className="font-extrabold text-lg text-brand-navy">FORMA-IA</p>
              <p className="text-[10px] text-slate-400">ALTIORA PREST</p>
            </div>
          </div>

          {/* Login card */}
          <div className="bg-white rounded-3xl shadow-xl shadow-slate-200/70 border border-slate-100/80 p-8">

            {/* Card header */}
            <div className="mb-7">
              <div className="mb-4 inline-flex h-14 w-14 items-center justify-center rounded-2xl text-brand-gold shadow-lg shadow-brand-navy/25"
                style={{ background: 'linear-gradient(135deg, #0B1F4D 0%, #06132F 100%)' }}>
                <BrainCircuit size={26} />
              </div>
              <h2 className="text-2xl font-extrabold text-brand-navy tracking-tight leading-tight">
                Connexion à FORMA-IA
              </h2>
              <p className="text-sm text-slate-400 mt-1.5">
                Accédez à votre espace de gestion des formations.
              </p>
            </div>

            {errorMsg && (
              <div role="alert" className="mb-5 rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm font-semibold text-red-700">
                {errorMsg}
              </div>
            )}

            <form onSubmit={handleLoginSubmit} className="space-y-5">
              {/* Email */}
              <div>
                <label htmlFor="login-email" className="mb-2 block text-xs font-bold uppercase tracking-widest text-slate-500">
                  Adresse e-mail
                </label>
                <div className="relative">
                  <Mail size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                  <input
                    id="login-email"
                    type="email"
                    required
                    value={loginEmail}
                    autoComplete="email"
                    onChange={(e) => { setLoginEmail(e.target.value); setErrorMsg(null); }}
                    placeholder="nom@organisation.mg"
                    className="w-full rounded-xl border border-slate-200 bg-slate-50 py-3.5 pl-11 pr-4 text-sm text-slate-800 transition-all focus:border-brand-navy focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-navy/12 placeholder:text-slate-400"
                  />
                </div>
              </div>

              {/* Password */}
              <div>
                <label htmlFor="login-password" className="mb-2 block text-xs font-bold uppercase tracking-widest text-slate-500">
                  Mot de passe
                </label>
                <div className="relative">
                  <Lock size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                  <input
                    id="login-password"
                    type={showPassword ? 'text' : 'password'}
                    required
                    value={loginPassword}
                    autoComplete="current-password"
                    onChange={(e) => { setLoginPassword(e.target.value); setErrorMsg(null); }}
                    placeholder="••••••••"
                    className="w-full rounded-xl border border-slate-200 bg-slate-50 py-3.5 pl-11 pr-12 text-sm text-slate-800 transition-all focus:border-brand-navy focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-navy/12 placeholder:text-slate-400"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(v => !v)}
                    aria-label={showPassword ? 'Masquer le mot de passe' : 'Afficher le mot de passe'}
                    className="absolute right-3 top-1/2 -translate-y-1/2 flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition-colors"
                  >
                    {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
                  </button>
                </div>
              </div>

              {/* Submit */}
              <button
                type="submit"
                disabled={isSubmitting}
                className="mt-1 flex w-full items-center justify-center gap-2.5 rounded-xl py-4 text-sm font-bold text-white transition-all focus:outline-none focus:ring-2 focus:ring-brand-navy focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
                style={{
                  background: 'linear-gradient(135deg, #0B1F4D 0%, #06132F 100%)',
                  boxShadow: '0 6px 24px rgba(11,31,77,0.30)',
                }}
              >
                {isSubmitting
                  ? <Loader2 size={17} className="animate-spin" />
                  : <ArrowRight size={17} />}
                <span className="text-base">{isSubmitting ? 'Connexion en cours…' : 'Se connecter'}</span>
              </button>
            </form>

            {/* Divider doré */}
            <div className="mt-7 pt-6 border-t border-slate-100 flex items-center gap-3">
              <div className="h-px flex-1" style={{ background: 'linear-gradient(to right, transparent, rgba(212,175,55,0.5), transparent)' }} />
              <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Accès sécurisé</span>
              <div className="h-px flex-1" style={{ background: 'linear-gradient(to right, transparent, rgba(212,175,55,0.5), transparent)' }} />
            </div>

            {/* Role badges */}
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              {['Direction', 'Formateur', 'Assistant', 'Comptable'].map(role => (
                <span key={role} className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] font-semibold text-slate-500">
                  {role}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
