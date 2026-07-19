import test from 'node:test';
import assert from 'node:assert/strict';
import { buildAnalyzeArgs, buildDownloadArgs } from '../apps/api/src/media-service.mjs';

const config = { maxFileSizeMb: 500, ffmpegLocation: undefined };

test('análisis evita playlists y separa la URL como argumento', () => {
  const args = buildAnalyzeArgs('https://youtu.be/example', config);
  assert.ok(args.includes('--no-playlist'));
  assert.deepEqual(args.slice(-2), ['--', 'https://youtu.be/example']);
});

test('video selecciona calidad y salida MP4', () => {
  const args = buildDownloadArgs({ type: 'video', quality: 720, url: 'https://youtu.be/example' }, 'media.%(ext)s', config);
  assert.ok(args.includes('bestvideo*[height<=?720]+bestaudio/best[height<=?720]'));
  assert.ok(args.includes('mp4'));
});

test('audio usa extracción MP3 con bitrate permitido', () => {
  const args = buildDownloadArgs({ type: 'audio', audioBitrate: 320, url: 'https://youtu.be/example' }, 'media.%(ext)s', config);
  assert.ok(args.includes('--extract-audio'));
  assert.ok(args.includes('mp3'));
  assert.ok(args.includes('320K'));
});

test('valores fuera de catálogo usan opciones seguras', () => {
  const video = buildDownloadArgs({ type: 'video', quality: 9999, url: 'https://youtu.be/example' }, 'media.%(ext)s', config);
  const audio = buildDownloadArgs({ type: 'audio', audioBitrate: 9999, url: 'https://youtu.be/example' }, 'media.%(ext)s', config);
  assert.ok(video.includes('bestvideo*[height<=?1080]+bestaudio/best[height<=?1080]'));
  assert.ok(audio.includes('192K'));
});
