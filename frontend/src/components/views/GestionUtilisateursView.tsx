import React, { useCallback, useEffect, useState } from 'react';
import { Loader2, Plus, RefreshCw, Shield, UserRound, UserX, Users } from 'lucide-react';
import { PageHeader } from '../PageHeader';
import { apiService } from '../../services/api';

type ManagedUser = { id: string; nom: string; email: string; role: 'DIRECTION' | 'ASSISTANT' | 'COMPTABLE' | 'FORMATEUR'; actif: boolean };

export const GestionUtilisateursView: React.FC = () => {
  const [users, setUsers] = useState<ManagedUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [nom, setNom] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<'ASSISTANT' | 'COMPTABLE'>('ASSISTANT');

  const refresh = useCallback(async () => {
    setLoading(true);
    try { setUsers(await apiService.getManagedUsers()); setError(''); }
    catch (e) { setError(e instanceof Error ? e.message : 'Impossible de charger les comptes.'); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);

  const create = async (event: React.FormEvent) => {
    event.preventDefault(); setSaving(true); setError(''); setSuccess('');
    try {
      await apiService.createManagedUser({ nom: nom.trim(), email: email.trim(), password, role });
      setNom(''); setEmail(''); setPassword('');
      setSuccess('Le compte a été créé et rattaché à votre entreprise.');
      await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : 'La création du compte a échoué.'); }
    finally { setSaving(false); }
  };

  const toggleActive = async (user: ManagedUser) => {
    setError(''); setSuccess('');
    try {
      await apiService.updateManagedUser(user.id, { actif: !user.actif });
      setUsers(current => current.map(item => item.id === user.id ? { ...item, actif: !item.actif } : item));
      setSuccess(user.actif ? 'Compte désactivé.' : 'Compte réactivé.');
    } catch (e) { setError(e instanceof Error ? e.message : 'La mise à jour du compte a échoué.'); }
  };
  const roleName = (value: ManagedUser['role']) => ({ DIRECTION: 'Directeur', ASSISTANT: 'Assistant / Secrétaire', COMPTABLE: 'Comptable', FORMATEUR: 'Formateur' })[value];

  return <div className="space-y-6 animate-in fade-in duration-300">
    <PageHeader
      icon={<Users size={22} />}
      badge="Administration"
      title="Gestion des utilisateurs"
      subtitle="Les comptes créés ici voient les données de votre entreprise selon leur rôle."
      actions={
        <button onClick={() => void refresh()} className="inline-flex items-center gap-1.5 rounded-xl border border-white/20 bg-white/15 px-3 py-1.5 text-xs font-semibold text-white hover:bg-white/25 transition-colors cursor-pointer">
          <RefreshCw size={13} />Actualiser
        </button>
      }
    />
    {error && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-xs font-semibold text-red-700">{error}</div>}
    {success && <div role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-xs font-semibold text-emerald-800">{success}</div>}
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
      <form onSubmit={create} className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
        <div><h2 className="font-extrabold text-[#11162A]">Créer un compte d’équipe</h2><p className="mt-1 text-xs text-slate-500">Le compte sera lié à votre espace entreprise.</p></div>
        <label className="block text-xs font-bold text-slate-600">Nom complet<input required value={nom} onChange={e=>setNom(e.target.value)} className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2.5 font-normal text-slate-800"/></label>
        <label className="block text-xs font-bold text-slate-600">Adresse e-mail<input required type="email" value={email} onChange={e=>setEmail(e.target.value)} className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2.5 font-normal text-slate-800"/></label>
        <label className="block text-xs font-bold text-slate-600">Mot de passe initial<input required minLength={8} type="password" value={password} onChange={e=>setPassword(e.target.value)} className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2.5 font-normal text-slate-800"/></label>
        <label className="block text-xs font-bold text-slate-600">Rôle<select value={role} onChange={e=>setRole(e.target.value as typeof role)} className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 font-normal text-slate-800"><option value="ASSISTANT">Assistant / Secrétaire</option><option value="COMPTABLE">Comptable</option></select></label>
        <button disabled={saving} className="flex w-full items-center justify-center gap-2 rounded-xl bg-[#0B1F4D] py-2.5 text-xs font-bold text-white disabled:opacity-50">{saving?<Loader2 size={14} className="animate-spin"/>:<Plus size={14}/>}Créer le compte</button>
      </form>
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
        <div className="mb-4 flex items-center justify-between"><div><h2 className="font-extrabold text-[#11162A]">Comptes de l’entreprise</h2><p className="mt-1 text-xs text-slate-500">Les comptes formateur sont créés lors de l’acceptation de leur candidature.</p></div><Shield className="text-[#0B1F4D]" size={20}/></div>
        {loading ? <div className="flex items-center gap-2 py-8 text-xs text-slate-500"><Loader2 size={15} className="animate-spin"/>Chargement…</div> : <div className="divide-y divide-slate-100">{users.map(user=><div key={user.id} className="flex flex-wrap items-center justify-between gap-3 py-3"><div className="flex min-w-0 items-center gap-3"><div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-600"><UserRound size={17}/></div><div className="min-w-0"><div className="truncate text-sm font-bold text-slate-800">{user.nom}</div><div className="truncate text-xs text-slate-500">{user.email}</div><div className="mt-0.5 text-[10px] font-bold text-[#0B1F4D]">{roleName(user.role)}</div></div></div><div className="flex items-center gap-2"><span className={"rounded-full px-2 py-1 text-[10px] font-bold " + (user.actif ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500')}>{user.actif?'Actif':'Désactivé'}</span>{user.role!=='DIRECTION'&&<button title={user.actif?'Désactiver ce compte':'Réactiver ce compte'} onClick={()=>void toggleActive(user)} className="rounded-lg p-2 text-slate-500 hover:bg-amber-50 hover:text-amber-700"><UserX size={15}/></button>}</div></div>)}{!users.length&&<p className="py-8 text-center text-xs text-slate-500">Aucun compte d’équipe.</p>}</div>}
      </section>
    </div>
  </div>;
};
