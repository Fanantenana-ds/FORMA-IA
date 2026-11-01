const toDateInput = (date: Date): string => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

export const addDaysToDate = (value: string, days: number): string => {
  const [year, month, day] = value.split('-').map(Number);
  const date = new Date(year, month - 1, day);
  date.setDate(date.getDate() + days);
  return toDateInput(date);
};

/** Ajoute des mois calendaires en conservant le jour quand il existe. */
export const addMonthsToDate = (value: string, months: number): string => {
  const [year, month, day] = value.split('-').map(Number);
  const date = new Date(year, month - 1, 1);
  date.setMonth(date.getMonth() + months);
  const lastDay = new Date(date.getFullYear(), date.getMonth() + 1, 0).getDate();
  date.setDate(Math.min(day, lastDay));
  return toDateInput(date);
};

export const defaultSessionDates = (): { dateDebut: string; dateFin: string } => {
  const dateDebut = addDaysToDate(toDateInput(new Date()), 7);
  return { dateDebut, dateFin: addMonthsToDate(dateDebut, 1) };
};
