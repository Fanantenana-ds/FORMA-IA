import { ApiError } from './api';

/** Traduit une erreur des routes de veille en message affichable. */
export const describeVeilleError = (err: unknown, action: 'search' | 'accept' | 'detect'): string => {
  if (err instanceof ApiError) {
    if (err.status === 0) return err.message;
    if (err.status === 401) {
      return action === 'accept'
        ? 'Votre session a expiré. Veuillez vous reconnecter.'
        : 'Le backend a refusé votre session pour la veille. Reconnectez-vous puis réessayez.';
    }
    if (err.status === 403) {
      return 'Votre rôle ne permet pas cette action (réservée à la Direction et aux Assistants).';
    }
    if (err.status === 409) return err.message;
    if (err.status === 429) {
      return "Le quota mensuel de recherches web est atteint. Réessayez le mois prochain ou contactez l'administrateur.";
    }
    if (err.status === 422) return `Requête invalide : ${err.message}`;
    if (err.status >= 500) return `Erreur du serveur : ${err.message}`;
    return err.message;
  }
  return 'Une erreur inattendue est survenue.';
};
