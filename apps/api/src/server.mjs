import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import { pipeline } from 'node:stream/promises';
import { analyzeMedia } from './media-service.mjs';
import { parseSupportedUrl, supportedPlatforms } from './platforms.mjs';

const MAX_BODY_BYTES = 16 * 1024;

const sendJson = (response, status, body, headers = {}) => {
  response.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff',
    ...headers
  });
  response.end(JSON.stringify(body));
};

const readJson = async (request) => {
  const chunks = [];
  let size = 0;
  for await (const chunk of request) {
    size += chunk.length;
    if (size > MAX_BODY_BYTES) throw new RangeError('La solicitud es demasiado grande.');
    chunks.push(chunk);
  }
  try {
    return JSON.parse(Buffer.concat(chunks).toString('utf8') || '{}');
  } catch {
    throw new TypeError('El cuerpo JSON no es válido.');
  }
};

const safeFilename = (title, extension) => {
  const base = (title || 'beetales-media')
    .normalize('NFKD')
    .replace(/[^\p{L}\p{N}._ -]+/gu, '')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 100) || 'beetales-media';
  return `${base}.${extension}`;
};

class RateLimiter {
  constructor(limit = 30, windowMs = 60_000) {
    this.limit = limit;
    this.windowMs = windowMs;
    this.clients = new Map();
  }

  allow(key) {
    const now = Date.now();
    const existing = this.clients.get(key);
    if (!existing || existing.resetAt <= now) {
      this.clients.set(key, { count: 1, resetAt: now + this.windowMs });
      return true;
    }
    existing.count += 1;
    return existing.count <= this.limit;
  }
}

export function createServer(config, jobs) {
  // El frontend consulta el progreso aproximadamente una vez por segundo.
  // El límite deja margen para ese flujo sin permitir ráfagas ilimitadas.
  const limiter = new RateLimiter(180);

  return http.createServer(async (request, response) => {
    const origin = request.headers.origin?.replace(/\/$/, '');
    const corsAllowed = !origin || config.publicOrigins.has(origin);
    const corsHeaders = corsAllowed && origin ? {
      'Access-Control-Allow-Origin': origin,
      'Access-Control-Allow-Methods': 'GET,POST,DELETE,OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
      'Vary': 'Origin'
    } : {};

    Object.entries(corsHeaders).forEach(([name, value]) => response.setHeader(name, value));
    response.setHeader('Referrer-Policy', 'no-referrer');
    response.setHeader('X-Frame-Options', 'DENY');

    if (request.method === 'OPTIONS') {
      response.writeHead(corsAllowed ? 204 : 403);
      response.end();
      return;
    }
    if (!corsAllowed) return sendJson(response, 403, { error: 'Origen no permitido.' });

    const client = request.socket.remoteAddress ?? 'unknown';
    if (!limiter.allow(client)) return sendJson(response, 429, { error: 'Demasiadas solicitudes. Intenta nuevamente en un minuto.' });

    const url = new URL(request.url, 'http://localhost');
    try {
      if (request.method === 'GET' && url.pathname === '/health') {
        return sendJson(response, 200, { status: 'ok', platforms: supportedPlatforms });
      }

      if (request.method === 'POST' && url.pathname === '/api/v1/analyze') {
        const body = await readJson(request);
        const media = await analyzeMedia(body.url, config);
        return sendJson(response, 200, media);
      }

      if (request.method === 'POST' && url.pathname === '/api/v1/downloads') {
        const body = await readJson(request);
        const parsed = parseSupportedUrl(body.url);
        if (!['video', 'audio'].includes(body.type)) throw new TypeError('Selecciona video o audio.');
        const job = jobs.create({
          url: parsed.url,
          type: body.type,
          quality: Number(body.quality),
          audioBitrate: Number(body.audioBitrate)
        }, typeof body.title === 'string' ? body.title.slice(0, 300) : '');
        return sendJson(response, 202, job);
      }

      const match = /^\/api\/v1\/downloads\/([0-9a-f-]+)(\/file)?$/.exec(url.pathname);
      if (match && request.method === 'GET' && !match[2]) {
        const job = jobs.get(match[1]);
        return job ? sendJson(response, 200, job) : sendJson(response, 404, { error: 'Trabajo no encontrado.' });
      }

      if (match && request.method === 'DELETE' && !match[2]) {
        const cancelled = await jobs.cancel(match[1]);
        return cancelled ? sendJson(response, 200, { status: 'cancelled' }) : sendJson(response, 404, { error: 'Trabajo no encontrado.' });
      }

      if (match && request.method === 'GET' && match[2]) {
        const file = jobs.getFile(match[1]);
        if (!file) return sendJson(response, 404, { error: 'El archivo no está listo o ya expiró.' });
        const stats = await fs.promises.stat(file.path);
        const extension = file.type === 'audio' ? 'mp3' : 'mp4';
        response.writeHead(200, {
          'Content-Type': file.type === 'audio' ? 'audio/mpeg' : 'video/mp4',
          'Content-Length': stats.size,
          'Content-Disposition': `attachment; filename*=UTF-8''${encodeURIComponent(safeFilename(file.title, extension))}`,
          'Cache-Control': 'private, no-store',
          'X-Content-Type-Options': 'nosniff'
        });
        await pipeline(fs.createReadStream(file.path), response);
        return;
      }

      return sendJson(response, 404, { error: 'Ruta no encontrada.' });
    } catch (error) {
      const status = error instanceof TypeError ? 400 : error instanceof RangeError ? 413 : error.name === 'ProcessError' ? 422 : 500;
      const safeMessage = status === 500 ? 'Ocurrió un error interno.' : error.message;
      if (!response.headersSent) sendJson(response, status, { error: safeMessage });
      else response.destroy();
    }
  });
}
