import { VeilleMarche } from '../types';

const KEY = 'forma_ia_veille_last';

interface CachedSearch {
  query: string;
  markets: VeilleMarche[];
}

/** Dernière recherche IA, conservée le temps de la session du navigateur. */
export const veilleCache = {
  get(): CachedSearch | null {
    try {
      const raw = sessionStorage.getItem(KEY);
      return raw ? (JSON.parse(raw) as CachedSearch) : null;
    } catch {
      return null;
    }
  },
  set(value: CachedSearch): void {
    try {
      sessionStorage.setItem(KEY, JSON.stringify(value));
    } catch {
      /* stockage indisponible */
    }
  },
  clear(): void {
    try {
      sessionStorage.removeItem(KEY);
    } catch {
      /* rien à faire */
    }
  }
};
