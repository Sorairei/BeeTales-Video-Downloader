import test from 'node:test';
import assert from 'node:assert/strict';
import { parseSupportedUrl } from '../apps/api/src/platforms.mjs';

const supported = [
  ['https://youtu.be/abc', 'youtube'],
  ['https://www.youtube.com/shorts/abc', 'youtube'],
  ['https://vm.tiktok.com/abc/', 'tiktok'],
  ['https://www.instagram.com/reel/abc/', 'instagram'],
  ['https://x.com/user/status/123', 'x'],
  ['https://mobile.twitter.com/user/status/123', 'x']
];

for (const [url, id] of supported) {
  test(`acepta ${url}`, () => assert.equal(parseSupportedUrl(url).platform.id, id));
}

for (const url of [
  'http://youtube.com/watch?v=x',
  'https://youtube.com.example.org/watch?v=x',
  'https://spotify.com/track/x',
  'https://user:pass@x.com/status/1',
  'https://127.0.0.1/video'
]) {
  test(`rechaza ${url}`, () => assert.throws(() => parseSupportedUrl(url), TypeError));
}
