const $ = (selector) => document.querySelector(selector);
const analyzeForm = $('#analyze-form');
const downloadForm = $('#download-form');
const mediaCard = $('#media-card');
const message = $('#message');
const progressWrap = $('#progress-wrap');
const apiInput = $('#api-url');

let media = null;
let currentJob = null;
let pollTimer = null;

const normalizeApiUrl = (value) => value.trim().replace(/\/$/, '');
const defaultApi = window.BEETALES_API_URL || 'http://localhost:8787';
apiInput.value = localStorage.getItem('beetalesApiUrl') || defaultApi;

const apiUrl = (path) => `${normalizeApiUrl(apiInput.value) || defaultApi}${path}`;
const setMessage = (text = '', type = '') => {
  message.textContent = text;
  message.className = `message ${type}`.trim();
};

const request = async (path, options = {}) => {
  const response = await fetch(apiUrl(path), {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options.headers }
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || `Error ${response.status}`);
  return body;
};

const formatDuration = (seconds) => {
  if (!seconds) return 'Duración desconocida';
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `${minutes}:${String(remainder).padStart(2, '0')}`;
};

analyzeForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  setMessage('Analizando el enlace…');
  $('#analyze-button').disabled = true;
  downloadForm.hidden = true;
  mediaCard.hidden = true;
  try {
    media = await request('/api/v1/analyze', {
      method: 'POST',
      body: JSON.stringify({ url: $('#media-url').value })
    });
    $('#media-title').textContent = media.title;
    $('#platform').textContent = media.platform.label;
    $('#media-meta').textContent = [media.creator, formatDuration(media.duration)].filter(Boolean).join(' · ');
    const thumbnail = $('#thumbnail');
    thumbnail.hidden = !media.thumbnail;
    thumbnail.src = media.thumbnail || '';
    thumbnail.alt = media.thumbnail ? `Miniatura de ${media.title}` : '';
    const quality = $('#quality');
    quality.replaceChildren(...media.qualities.map((height) => {
      const option = document.createElement('option');
      option.value = height;
      option.textContent = `${height}p`;
      option.selected = height === media.defaultQuality;
      return option;
    }));
    mediaCard.hidden = false;
    downloadForm.hidden = false;
    setMessage('Enlace listo.', 'success');
  } catch (error) {
    setMessage(error.message, 'error');
  } finally {
    $('#analyze-button').disabled = false;
  }
});

downloadForm.addEventListener('change', () => {
  const audio = new FormData(downloadForm).get('type') === 'audio';
  $('#quality-field').hidden = audio;
  $('#bitrate-field').hidden = !audio;
});

const stopPolling = () => {
  if (pollTimer) clearTimeout(pollTimer);
  pollTimer = null;
};

const pollJob = async () => {
  if (!currentJob) return;
  try {
    const job = await request(`/api/v1/downloads/${currentJob}`);
    $('#progress').value = job.progress;
    $('#progress-label').textContent = `${job.progress}%`;
    if (job.status === 'ready') {
      stopPolling();
      progressWrap.hidden = true;
      downloadForm.hidden = false;
      setMessage('Tu archivo está listo. La descarga comenzará ahora.', 'success');
      window.location.assign(apiUrl(job.fileUrl));
      currentJob = null;
      return;
    }
    if (['failed', 'cancelled', 'expired'].includes(job.status)) {
      throw new Error(job.error || 'La descarga no pudo completarse.');
    }
    pollTimer = setTimeout(pollJob, 900);
  } catch (error) {
    stopPolling();
    currentJob = null;
    progressWrap.hidden = true;
    downloadForm.hidden = false;
    setMessage(error.message, 'error');
  }
};

downloadForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!media) return;
  const data = new FormData(downloadForm);
  setMessage('Creando el trabajo de descarga…');
  $('#download-button').disabled = true;
  try {
    const job = await request('/api/v1/downloads', {
      method: 'POST',
      body: JSON.stringify({
        url: media.sourceUrl,
        title: media.title,
        type: data.get('type'),
        quality: Number(data.get('quality')),
        audioBitrate: Number(data.get('audioBitrate'))
      })
    });
    currentJob = job.id;
    downloadForm.hidden = true;
    progressWrap.hidden = false;
    $('#progress').value = 0;
    $('#progress-label').textContent = '0%';
    void pollJob();
  } catch (error) {
    setMessage(error.message, 'error');
  } finally {
    $('#download-button').disabled = false;
  }
});

$('#cancel-button').addEventListener('click', async () => {
  if (!currentJob) return;
  const id = currentJob;
  currentJob = null;
  stopPolling();
  await request(`/api/v1/downloads/${id}`, { method: 'DELETE' }).catch(() => {});
  progressWrap.hidden = true;
  downloadForm.hidden = false;
  setMessage('Descarga cancelada.');
});

$('#save-api').addEventListener('click', () => {
  const value = normalizeApiUrl(apiInput.value);
  try {
    const parsed = new URL(value);
    if (!['http:', 'https:'].includes(parsed.protocol)) throw new Error();
    localStorage.setItem('beetalesApiUrl', value);
    setMessage('Servidor guardado.', 'success');
  } catch {
    setMessage('Escribe una URL válida para la API.', 'error');
  }
});
