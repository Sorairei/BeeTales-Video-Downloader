import fs from 'node:fs/promises';
import path from 'node:path';
import { parseSupportedUrl } from './platforms.mjs';
import { runProcess } from './process-runner.mjs';

const VIDEO_QUALITIES = new Set([360, 480, 720, 1080, 1440, 2160]);
const AUDIO_BITRATES = new Set([128, 192, 256, 320]);

const cleanText = (value, fallback = '') =>
  typeof value === 'string' ? value.replace(/[\u0000-\u001f\u007f]/g, '').slice(0, 500) : fallback;

export function buildAnalyzeArgs(url, config) {
  const args = [
    '--dump-single-json',
    '--skip-download',
    '--no-playlist',
    '--no-cache-dir',
    '--no-warnings',
    '--socket-timeout', '15',
    '--', url
  ];
  if (config.ffmpegLocation) args.unshift('--ffmpeg-location', config.ffmpegLocation);
  return args;
}

export function buildDownloadArgs(request, outputTemplate, config) {
  const common = [
    '--no-playlist',
    '--no-cache-dir',
    '--no-warnings',
    '--newline',
    '--progress',
    '--progress-template', 'download:%(progress._percent_str)s',
    '--socket-timeout', '20',
    '--max-filesize', `${config.maxFileSizeMb}M`,
    '--output', outputTemplate
  ];

  if (config.ffmpegLocation) common.push('--ffmpeg-location', config.ffmpegLocation);

  if (request.type === 'audio') {
    const bitrate = AUDIO_BITRATES.has(request.audioBitrate) ? request.audioBitrate : 192;
    common.push(
      '--format', 'bestaudio/best',
      '--extract-audio',
      '--audio-format', 'mp3',
      '--audio-quality', `${bitrate}K`,
      '--embed-metadata'
    );
  } else {
    const quality = VIDEO_QUALITIES.has(request.quality) ? request.quality : 1080;
    common.push(
      '--format', `bestvideo*[height<=?${quality}]+bestaudio/best[height<=?${quality}]`,
      '--merge-output-format', 'mp4',
      '--remux-video', 'mp4'
    );
  }

  common.push('--', request.url);
  return common;
}

function normalizeMetadata(info, platform, maxDurationSeconds) {
  const duration = Number.isFinite(info.duration) ? Math.round(info.duration) : null;
  if (duration && duration > maxDurationSeconds) {
    throw new RangeError(`El contenido supera el límite de ${maxDurationSeconds} segundos.`);
  }

  const qualities = [...new Set((info.formats ?? [])
    .map((format) => Number(format.height))
    .filter((height) => VIDEO_QUALITIES.has(height)))]
    .sort((a, b) => a - b);

  return {
    id: cleanText(info.id),
    title: cleanText(info.title, 'Contenido sin título'),
    creator: cleanText(info.uploader || info.channel || info.creator),
    thumbnail: typeof info.thumbnail === 'string' && info.thumbnail.startsWith('https://') ? info.thumbnail : null,
    duration,
    platform,
    qualities: qualities.length ? qualities : [360, 480, 720, 1080],
    defaultQuality: qualities.filter((height) => height <= 1080).at(-1) ?? qualities.at(-1) ?? 720
  };
}

export async function analyzeMedia(inputUrl, config, signal) {
  const parsed = parseSupportedUrl(inputUrl);
  const { stdout } = await runProcess(
    config.ytDlpPath,
    buildAnalyzeArgs(parsed.url, config),
    { timeoutMs: config.analyzeTimeoutMs, signal }
  );
  let info;
  try {
    info = JSON.parse(stdout);
  } catch {
    throw new Error('La plataforma devolvió metadatos inesperados.');
  }
  return { ...normalizeMetadata(info, parsed.platform, config.maxDurationSeconds), sourceUrl: parsed.url };
}

export async function downloadMedia(request, directory, config, signal, onProgress) {
  const parsed = parseSupportedUrl(request.url);
  const outputTemplate = path.join(directory, 'media.%(ext)s');
  const parseProgress = (line) => {
    const match = /^download:\s*([\d.]+)%/.exec(line.trim());
    if (match) onProgress(Math.min(99, Math.max(0, Number.parseFloat(match[1]))));
  };

  await runProcess(config.ytDlpPath, buildDownloadArgs({ ...request, url: parsed.url }, outputTemplate, config), {
    cwd: directory,
    timeoutMs: config.downloadTimeoutMs,
    signal,
    maxOutputBytes: 2 * 1024 * 1024,
    onStdoutLine: parseProgress,
    onStderrLine: parseProgress
  });

  const entries = await fs.readdir(directory, { withFileTypes: true });
  const extension = request.type === 'audio' ? '.mp3' : '.mp4';
  const file = entries.find((entry) => entry.isFile() && entry.name.endsWith(extension));
  if (!file) throw new Error('La conversión terminó sin producir el archivo esperado.');
  return path.join(directory, file.name);
}
