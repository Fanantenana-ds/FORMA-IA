const assert = require('node:assert/strict');
const { test } = require('node:test');
const path = require('node:path');
const vm = require('node:vm');
const { buildSync } = require('esbuild');

const bundle = buildSync({
  entryPoints: [path.join(__dirname, '../src/services/api.ts')],
  bundle: true,
  write: false,
  platform: 'node',
  format: 'cjs',
  define: { 'import.meta.env': JSON.stringify({ DEV: true }) },
}).outputFiles[0].text;

function client(crypto, payload, responseOverride = null, token = null) {
  const module = { exports: {} };
  const context = vm.createContext({
    module, exports: module.exports, crypto,
    URL, URLSearchParams, Headers, FormData, Blob, AbortController, AbortSignal, TextDecoder,
    setTimeout, clearTimeout,
    localStorage: { getItem: () => token },
    fetch: async () => responseOverride ?? new Response(JSON.stringify({ success: true, data: payload }), {
      status: 200, headers: { 'Content-Type': 'application/json' },
    }),
  });
  vm.runInContext(bundle, context);
  return module.exports.apiService;
}

test('détection sans randomUUID : affiche les fiches sans ID et préserve les ID backend', async () => {
  const api = client({}, {
    opportunities: [{ title: 'Formation IA' }, { title: 'Formation Data' }, { id: 'backend-123', title: 'Avis enregistré' }],
    total: 3,
  });
  const result = await api.runDetection({ syncBackend: false });
  assert.equal(result.markets.length, 3);
  assert.ok(result.markets[0].id);
  assert.notEqual(result.markets[0].id, result.markets[1].id);
  assert.equal(result.markets[2].id, 'backend-123');
});

test('flux de démonstration : étapes reçues et résultats finaux sans enregistrement automatique', async () => {
  const frames = [
    'event: debut\ndata: {"message":"Début"}\n\n',
    'event: requete\ndata: {"message":"Recherche"}\n\n',
    'event: opportunite\ndata: {"titre":"Formation IA","score":82}\n\n',
    'event: fin\ndata: {"status":"success","total":1,"opportunites":[{"title":"Formation IA","score":82,"demo_data_type":"archive_reelle"}]}\n\n',
  ];
  const stream = new ReadableStream({ start(controller) {
    for (const frame of frames) controller.enqueue(new TextEncoder().encode(frame));
    controller.close();
  } });
  const response = new Response(stream, { headers: { 'Content-Type': 'text/event-stream' } });
  const events = [];
  const api = client({}, null, response, 'session-test');
  const result = await api.streamDetection((event) => events.push(event), { syncBackend: true });
  assert.equal(events.join(','), 'debut,requete,opportunite,fin');
  assert.equal(result.demoMode, true);
  assert.equal(result.markets.length, 1);
  assert.ok(result.markets[0].id);
  assert.equal(result.statistics.backend_sync.enabled, false);
});

test('recherche sans objet crypto : affiche aussi une fiche sans ID', async () => {
  const result = await client(undefined, { opportunities: [{ title: 'Formation IA' }] }).searchMarkets('formation');
  assert.equal(result.markets.length, 1);
  assert.ok(result.markets[0].id);
});

test('contexte sécurisé : utilise randomUUID quand il est disponible', async () => {
  const result = await client({ randomUUID: () => 'uuid-navigateur' }, {
    opportunities: [{ title: 'Formation IA' }], total: 1,
  }).runDetection();
  assert.equal(result.markets[0].id, 'uuid-navigateur');
});
