import os from 'node:os';
import path from 'node:path';

const integer = (name, fallback, min, max) => {
  const raw = process.env[name];
  const value = raw === undefined ? fallback : Number.parseInt(raw, 10);
  if (!Number.isInteger(value) || value < min || value > max) {
    throw new Error(`${name} debe ser un entero entre ${min} y ${max}`);
  }
  return value;
};

const origins = (process.env.PUBLIC_ORIGINS ?? 'http://localhost:4173,http://127.0.0.1:4173')
  .split(',')
  .map((origin) => origin.trim().replace(/\/$/, ''))
  .filter(Boolean);

export const config = Object.freeze({
  host: process.env.HOST ?? '0.0.0.0',
  port: integer('PORT', 8787, 1, 65535),
  publicOrigins: new Set(origins),
  ytDlpPath: process.env.YT_DLP_PATH ?? 'yt-dlp',
  ffmpegLocation: process.env.FFMPEG_LOCATION || undefined,
  tempRoot: process.env.TEMP_ROOT || path.join(os.tmpdir(), 'beetales-downloads'),
  maxConcurrentJobs: integer('MAX_CONCURRENT_JOBS', 2, 1, 8),
  maxActiveJobs: integer('MAX_ACTIVE_JOBS', 50, 1, 500),
  jobTtlMs: integer('JOB_TTL_MINUTES', 30, 1, 240) * 60_000,
  maxDurationSeconds: integer('MAX_MEDIA_DURATION_SECONDS', 7200, 1, 86_400),
  maxFileSizeMb: integer('MAX_FILE_SIZE_MB', 1024, 10, 10_240),
  analyzeTimeoutMs: integer('ANALYZE_TIMEOUT_SECONDS', 30, 5, 120) * 1_000,
  downloadTimeoutMs: integer('DOWNLOAD_TIMEOUT_MINUTES', 20, 1, 180) * 60_000
});
