/**
 * Configuration d'environnement du frontend.
 * Toutes les valeurs viennent du fichier `.env` (préfixe VITE_ obligatoire).
 */

const rawApiUrl = (import.meta.env.VITE_API_URL ?? '').trim();

/** URL de base du backend, sans slash final. */
export const API_BASE_URL: string = rawApiUrl.replace(/\/+$/, '');

/** Base utilisée par fetch : même origine en développement grâce au proxy Vite. */
export const API_REQUEST_BASE: string = import.meta.env.DEV ? '' : API_BASE_URL;

/** Préfixe des routes REST du backend. */
export const API_PREFIX = '/api/v1';

/** Vrai si VITE_API_URL est renseigné ou si le proxy de développement est actif. */
export const IS_API_CONFIGURED: boolean = import.meta.env.DEV || API_BASE_URL.length > 0;

/** Libellé court (hôte:port) pour l'affichage dans l'interface. */
export const API_HOST_LABEL: string = (() => {
  if (!IS_API_CONFIGURED) return 'non configuré';
  const labelUrl = import.meta.env.DEV ? rawApiUrl || 'http://127.0.0.1:8000' : API_BASE_URL;
  try {
    return new URL(labelUrl).host;
  } catch {
    return labelUrl;
  }
})();
