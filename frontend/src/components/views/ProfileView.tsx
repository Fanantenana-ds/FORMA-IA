import React, { useEffect, useRef, useState } from 'react';
import { ArrowLeft, BadgeCheck, Camera, Check, ImagePlus, Mail, Trash2, UserRound } from 'lucide-react';
import { AuthUser, ROLE_LABELS } from '../../types';

interface ProfileViewProps {
  authUser: AuthUser;
  avatarUrl: string | null;
  onUploadAvatar: (file: File) => Promise<void>;
  onDeleteAvatar: () => Promise<void>;
  onUpdateUser: (updates: Pick<AuthUser, 'nom' | 'email'>) => Promise<void>;
  onBack: () => void;
}

const initials = (name: string) => name.trim().split(/\s+/).slice(0, 2).map(part => part[0]?.toUpperCase() ?? '').join('');

export const ProfileView: React.FC<ProfileViewProps> = ({ authUser, avatarUrl, onUploadAvatar, onDeleteAvatar, onUpdateUser, onBack }) => {
  const fileInput = useRef<HTMLInputElement>(null);
  const [nom, setNom] = useState(authUser.nom);
  const [email, setEmail] = useState(authUser.email);
  const [saving, setSaving] = useState(false);
  const [avatarSaving, setAvatarSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  useEffect(() => {
    setNom(authUser.nom);
    setEmail(authUser.email);
  }, [authUser.email, authUser.nom]);

  const handlePhoto = async (file?: File) => {
    if (!file) return;
    setError('');
    setNotice('');
    setAvatarSaving(true);
    try {
      await onUploadAvatar(file);
      setNotice('Votre photo est enregistrée sur votre compte FORMA-IA.');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Impossible d’enregistrer la photo.');
    } finally {
      setAvatarSaving(false);
      if (fileInput.current) fileInput.current.value = '';
    }
  };

  const handleSave = async (event: React.FormEvent) => {
    event.preventDefault();
    const nextNom = nom.trim();
    const nextEmail = email.trim();
    if (!nextNom || !nextEmail) {
      setError('Le nom et l’adresse e-mail sont obligatoires.');
      return;
    }
    setError('');
    setNotice('');
    setSaving(true);
    try {
      await onUpdateUser({ nom: nextNom, email: nextEmail });
      setNotice('Les informations de votre compte ont été mises à jour.');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'La mise à jour du compte a échoué.');
    } finally {
      setSaving(false);
    }
  };

  const handleRemovePhoto = async () => {
    setError('');
    setNotice('');
    setAvatarSaving(true);
    try {
      await onDeleteAvatar();
      setNotice('La photo a été supprimée de votre compte FORMA-IA.');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Impossible de supprimer la photo.');
    } finally {
      setAvatarSaving(false);
    }
  };

  return (
    <div className="mx-auto max-w-5xl space-y-6 pb-10">
      <button type="button" onClick={onBack} className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-sm font-semibold text-slate-700 shadow-sm transition hover:border-emerald-200 hover:bg-emerald-50 hover:text-[#17694f] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#16785c] focus-visible:ring-offset-2">
        <ArrowLeft size={16} />
        Retour
      </button>
      <header className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
          <div className="relative mx-auto sm:mx-0">
            <div className="flex h-24 w-24 items-center justify-center overflow-hidden rounded-full border-4 border-white bg-emerald-50 text-2xl font-extrabold text-[#17694f] shadow-md ring-1 ring-slate-200 sm:h-28 sm:w-28">
              {avatarUrl ? <img src={avatarUrl} alt={`Photo de profil de ${authUser.nom}`} className="h-full w-full object-cover" /> : initials(authUser.nom) || <UserRound size={32} />}
            </div>
            <button
              type="button"
              onClick={() => fileInput.current?.click()}
              disabled={avatarSaving}
              aria-label="Choisir une photo de profil"
              className="absolute bottom-0 right-0 flex h-9 w-9 items-center justify-center rounded-full border-2 border-white bg-[#16785c] text-white shadow-sm transition hover:bg-[#125f49] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#16785c] focus-visible:ring-offset-2 disabled:opacity-60"
            >
              {avatarSaving ? <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" /> : <Camera size={16} />}
            </button>
            <input ref={fileInput} type="file" accept="image/*" tabIndex={-1} className="sr-only" onChange={event => void handlePhoto(event.target.files?.[0])} />
          </div>
          <div className="min-w-0 flex-1 text-center sm:text-left">
            <div className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-bold text-[#17694f]">
              <BadgeCheck size={14} />
              {ROLE_LABELS[authUser.role]}
            </div>
            <h1 className="mt-2 break-words text-2xl font-extrabold tracking-tight text-[#11162A] sm:text-3xl">Mon profil</h1>
            <p className="mt-1 text-sm text-slate-600">Gérez votre identité et votre photo dans FORMA-IA.</p>
          </div>
          {avatarUrl && (
            <button type="button" onClick={() => void handleRemovePhoto()} disabled={avatarSaving} className="inline-flex items-center justify-center gap-2 self-center rounded-xl border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-600 transition hover:border-red-200 hover:bg-red-50 hover:text-red-700 disabled:opacity-50 sm:self-start">
              <Trash2 size={14} /> Supprimer la photo
            </button>
          )}
        </div>
        <p className="mt-5 flex items-start gap-2 rounded-xl border border-blue-100 bg-blue-50 px-3.5 py-3 text-xs leading-relaxed text-blue-900">
          <ImagePlus size={15} className="mt-0.5 shrink-0" />
          La photo est enregistrée sur votre compte et sera disponible après connexion depuis vos autres appareils.
        </p>
      </header>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
        <div className="mb-5 flex items-start gap-3">
          <div className="rounded-xl bg-slate-100 p-2.5 text-slate-600"><UserRound size={18} /></div>
          <div>
            <h2 className="font-bold text-[#11162A]">Informations du compte</h2>
            <p className="mt-1 text-xs text-slate-500">Ces informations identifient votre accès à la plateforme.</p>
          </div>
        </div>

        <form onSubmit={handleSave} className="space-y-4">
          <label className="block">
            <span className="mb-1.5 block text-xs font-bold text-slate-700">Nom affiché</span>
            <span className="relative block">
              <UserRound size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input value={nom} onChange={event => { setNom(event.target.value); setError(''); setNotice(''); }} disabled={saving} required autoComplete="name" className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-9 pr-3 text-sm text-slate-800 outline-none transition focus:border-[#16785c] focus:ring-2 focus:ring-[#16785c]/15 disabled:bg-slate-50 disabled:text-slate-600" />
            </span>
          </label>
          <label className="block">
            <span className="mb-1.5 block text-xs font-bold text-slate-700">Adresse e-mail</span>
            <span className="relative block">
              <Mail size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input type="email" value={email} onChange={event => { setEmail(event.target.value); setError(''); setNotice(''); }} disabled={saving} required autoComplete="email" className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-9 pr-3 text-sm text-slate-800 outline-none transition focus:border-[#16785c] focus:ring-2 focus:ring-[#16785c]/15 disabled:bg-slate-50 disabled:text-slate-600" />
            </span>
          </label>

          {error && <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-xs font-semibold text-red-700">{error}</p>}
          {notice && <p role="status" className="flex items-center gap-2 rounded-lg bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-800"><Check size={14} />{notice}</p>}

          <div className="flex flex-col-reverse gap-3 border-t border-slate-100 pt-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-[11px] text-slate-500">Les changements sont enregistrés sur votre compte Backend.</p>
            <button type="submit" disabled={saving || (nom.trim() === authUser.nom && email.trim() === authUser.email)} aria-busy={saving} className="rounded-xl bg-[#16785c] px-4 py-2.5 text-sm font-bold text-white shadow-sm transition hover:bg-[#125f49] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#16785c] focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50">
              {saving ? 'Enregistrement…' : 'Enregistrer mon profil'}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
};
