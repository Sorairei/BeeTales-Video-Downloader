import test from 'node:test';
import assert from 'node:assert/strict';
import { once } from 'node:events';
import { createServer } from '../apps/api/src/server.mjs';

const config = {
  publicOrigins: new Set(['https://beetales.example'])
};

const jobs = {
  get: () => null,
  getFile: () => null,
  cancel: async () => false
};

test('health informa plataformas y aplica CORS por allowlist', async (context) => {
  const server = createServer(config, jobs);
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  context.after(() => server.close());
  const { port } = server.address();

  const allowed = await fetch(`http://127.0.0.1:${port}/health`, {
    headers: { Origin: 'https://beetales.example' }
  });
  assert.equal(allowed.status, 200);
  assert.equal(allowed.headers.get('access-control-allow-origin'), 'https://beetales.example');
  assert.deepEqual((await allowed.json()).platforms.map((item) => item.id), ['youtube', 'tiktok', 'instagram', 'x']);

  const denied = await fetch(`http://127.0.0.1:${port}/health`, {
    headers: { Origin: 'https://untrusted.example' }
  });
  assert.equal(denied.status, 403);
});
