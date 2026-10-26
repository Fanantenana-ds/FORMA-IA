import React, { useEffect, useRef, useState } from 'react';

interface Metric {
  target: number;
  label: string;
  prefix?: string;
  suffix?: string;
}

const METRICS: Metric[] = [
  { target: 13, label: 'Endpoints IA spécialisés' },
  { target: 6, label: 'Agents IA autonomes' },
  { target: 99, suffix: '%', label: 'Disponibilité garantie' },
  { target: 3, prefix: '< ', suffix: 's', label: 'Latence moyenne de réponse' },
];

/** Compteur animé de 0 → target (1,8 s) une fois `start` à true. */
const useCountUp = (target: number, start: boolean, duration = 1800) => {
  const [value, setValue] = useState(0);
  useEffect(() => {
    if (!start) return;
    const stepTime = 30;
    const increment = target / (duration / stepTime);
    let current = 0;
    const timer = setInterval(() => {
      current += increment;
      if (current >= target) {
        setValue(target);
        clearInterval(timer);
      } else {
        setValue(Math.ceil(current));
      }
    }, stepTime);
    return () => clearInterval(timer);
  }, [start, target, duration]);
  return value;
};

const MetricCard: React.FC<{ metric: Metric; start: boolean }> = ({ metric, start }) => {
  const value = useCountUp(metric.target, start);
  return (
    <div className="p-6 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-sm hover:border-brand-gold/50 transition-colors">
      <div className="text-4xl sm:text-5xl font-black text-brand-gold tracking-tight">
        {metric.prefix}
        {value}
        {metric.suffix}
      </div>
      <p className="text-sm font-medium text-slate-300 mt-2">{metric.label}</p>
    </div>
  );
};

export const MetricsSection: React.FC = () => {
  const ref = useRef<HTMLElement>(null);
  const [started, setStarted] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setStarted(true);
          observer.disconnect();
        }
      },
      { threshold: 0.3 }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <section ref={ref} id="metrics" className="py-20 bg-brand-navy relative overflow-hidden text-white">
      <div className="absolute inset-0 bg-radial from-brand-gold/10 via-transparent to-transparent pointer-events-none" />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <div className="text-center max-w-2xl mx-auto mb-14">
          <p className="text-xs uppercase tracking-widest text-brand-gold font-bold mb-2">Performances &amp; Fiabilité</p>
          <h2 className="text-3xl sm:text-4xl font-extrabold">FORMA-IA en chiffres</h2>
          <p className="text-slate-300 mt-2 text-sm">
            Une infrastructure robuste pensée pour soutenir la croissance de vos sessions de formation.
          </p>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
          {METRICS.map((m) => (
            <MetricCard key={m.label} metric={m} start={started} />
          ))}
        </div>
      </div>
    </section>
  );
};
