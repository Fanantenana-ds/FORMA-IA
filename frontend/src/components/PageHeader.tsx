import React from 'react';

interface PageHeaderProps {
  icon: React.ReactNode;
  badge: string;
  title: string;
  subtitle: string;
  actions?: React.ReactNode;
}

export const PageHeader: React.FC<PageHeaderProps> = ({ icon, badge, title, subtitle, actions }) => (
  <div className="w-full overflow-hidden rounded-2xl shadow-md mb-6">
    <div
      className="relative px-6 py-5 text-white"
      style={{ background: 'linear-gradient(135deg, #06132F 0%, #0B1F4D 60%, #0d2460 100%)' }}
    >
      {/* Cercles décoratifs */}
      <div className="pointer-events-none absolute -right-10 -top-10 h-44 w-44 rounded-full border border-brand-gold/20" />
      <div className="pointer-events-none absolute -right-3 -top-3 h-24 w-24 rounded-full border border-brand-gold/12" />

      <div className="relative flex items-center justify-between gap-4">
        <div className="flex items-center gap-4 min-w-0">
          {/* Icône */}
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-brand-gold/35 bg-brand-gold/15 text-brand-gold">
            {icon}
          </div>
          <div className="min-w-0">
            {/* Badge */}
            <div className="mb-1 inline-flex items-center rounded-full border border-white/20 bg-white/10 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white/75">
              {badge}
            </div>
            <h1 className="text-xl font-extrabold leading-tight text-white truncate">{title}</h1>
            <p className="mt-0.5 text-xs text-white/55 truncate">{subtitle}</p>
          </div>
        </div>
        {/* Actions optionnelles (boutons, filtres…) */}
        {actions && <div className="shrink-0 flex items-center gap-2">{actions}</div>}
      </div>
    </div>
  </div>
);
