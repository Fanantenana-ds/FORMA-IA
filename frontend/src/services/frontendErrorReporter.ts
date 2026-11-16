/** Diagnostic du navigateur visible dans le terminal Vite en développement. */
export function reportFrontendError(kind: string, details: { route?: string; status?: number; name?: string; file?: string; line?: number } = {}): void {
  if (!import.meta.env.DEV || typeof window === 'undefined') return;
  const report = {
    kind,
    route: details.route?.slice(0, 100),
    status: details.status,
    name: details.name?.slice(0, 50),
    file: details.file?.slice(0, 100),
    line: details.line,
  };
  void fetch('/__frontend_error', {
    method: 'POST',
    headers: { 'Content-Type': 'text/plain' },
    body: JSON.stringify(report),
    keepalive: true,
  }).catch(() => {});
}

export function installFrontendErrorReporter(): void {
  if (!import.meta.env.DEV || typeof window === 'undefined') return;
  window.addEventListener('error', (event) => {
    reportFrontendError('runtime', {
      name: event.error instanceof Error ? event.error.name : 'Error',
      file: event.filename ? event.filename.split(/[/?#]/).pop() : undefined,
      line: event.lineno,
    });
  });
  window.addEventListener('unhandledrejection', (event) => {
    reportFrontendError('promise', { name: event.reason instanceof Error ? event.reason.name : 'UnhandledRejection' });
  });
}
