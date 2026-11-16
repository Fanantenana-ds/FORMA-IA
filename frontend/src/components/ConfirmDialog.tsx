import React from 'react';
import { AlertTriangle, Trash2, X } from 'lucide-react';

export interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'danger' | 'warning' | 'info';
  onConfirm: () => void;
  onCancel: () => void;
}

export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  open,
  title,
  message,
  confirmLabel = 'Confirmer',
  cancelLabel = 'Annuler',
  variant = 'danger',
  onConfirm,
  onCancel,
}) => {
  if (!open) return null;

  const iconBg = {
    danger: 'bg-red-50 text-red-600',
    warning: 'bg-amber-50 text-amber-600',
    info: 'bg-brand-navy/8 text-brand-navy',
  }[variant];

  const confirmBtn = {
    danger: 'bg-red-600 hover:bg-red-700 focus-visible:ring-red-500',
    warning: 'bg-amber-500 hover:bg-amber-600 focus-visible:ring-amber-400',
    info: 'bg-brand-navy hover:bg-brand-darkNavy focus-visible:ring-brand-navy',
  }[variant];

  const Icon = variant === 'danger' ? Trash2 : AlertTriangle;

  return (
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-dialog-title"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-slate-900/50 backdrop-blur-sm"
        onClick={onCancel}
      />

      {/* Panel */}
      <div className="relative w-full max-w-md overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl animate-[fadeInUp_0.18s_ease-out]">
        {/* Close button */}
        <button
          type="button"
          onClick={onCancel}
          className="absolute right-4 top-4 flex h-7 w-7 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition"
          aria-label="Fermer"
        >
          <X size={15} />
        </button>

        <div className="p-6">
          {/* Icon + title */}
          <div className="flex items-start gap-4">
            <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${iconBg}`}>
              <Icon size={20} />
            </div>
            <div className="min-w-0 pt-0.5">
              <h2 id="confirm-dialog-title" className="text-base font-extrabold text-slate-900 leading-tight">
                {title}
              </h2>
              <p className="mt-1.5 text-sm leading-relaxed text-slate-500">{message}</p>
            </div>
          </div>

          {/* Divider */}
          <div className="my-5 h-px bg-slate-100" />

          {/* Actions */}
          <div className="flex items-center justify-end gap-2.5">
            <button
              type="button"
              onClick={onCancel}
              className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-300"
            >
              {cancelLabel}
            </button>
            <button
              type="button"
              onClick={onConfirm}
              className={`rounded-xl px-4 py-2 text-sm font-bold text-white transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 ${confirmBtn}`}
            >
              {confirmLabel}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

// Hook utilitaire pour gérer l'état du dialog
export function useConfirmDialog() {
  const [state, setState] = React.useState<{
    open: boolean;
    title: string;
    message: string;
    confirmLabel?: string;
    variant?: ConfirmDialogProps['variant'];
    resolve?: (ok: boolean) => void;
  }>({ open: false, title: '', message: '' });

  const confirm = React.useCallback(
    (opts: { title: string; message: string; confirmLabel?: string; variant?: ConfirmDialogProps['variant'] }) =>
      new Promise<boolean>((resolve) => {
        setState({ open: true, ...opts, resolve });
      }),
    []
  );

  const handleConfirm = () => {
    state.resolve?.(true);
    setState((s) => ({ ...s, open: false }));
  };

  const handleCancel = () => {
    state.resolve?.(false);
    setState((s) => ({ ...s, open: false }));
  };

  const dialogProps: ConfirmDialogProps = {
    open: state.open,
    title: state.title,
    message: state.message,
    confirmLabel: state.confirmLabel,
    variant: state.variant,
    onConfirm: handleConfirm,
    onCancel: handleCancel,
  };

  return { confirm, dialogProps };
}
