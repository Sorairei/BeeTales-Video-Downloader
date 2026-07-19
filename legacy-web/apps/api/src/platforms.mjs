const PLATFORM_RULES = [
  {
    id: 'youtube',
    label: 'YouTube',
    hosts: ['youtube.com', 'youtu.be', 'youtube-nocookie.com']
  },
  {
    id: 'tiktok',
    label: 'TikTok',
    hosts: ['tiktok.com']
  },
  {
    id: 'instagram',
    label: 'Instagram',
    hosts: ['instagram.com']
  },
  {
    id: 'x',
    label: 'X',
    hosts: ['x.com', 'twitter.com']
  }
];

const matchesHost = (hostname, allowed) =>
  hostname === allowed || hostname.endsWith(`.${allowed}`);

export function parseSupportedUrl(input) {
  if (typeof input !== 'string' || input.length === 0 || input.length > 2048) {
    throw new TypeError('La URL es obligatoria y no puede superar 2048 caracteres.');
  }

  let url;
  try {
    url = new URL(input.trim());
  } catch {
    throw new TypeError('La URL no es válida.');
  }

  if (url.protocol !== 'https:' || url.username || url.password || (url.port && url.port !== '443')) {
    throw new TypeError('Solo se aceptan enlaces HTTPS públicos sin credenciales ni puertos personalizados.');
  }

  const hostname = url.hostname.toLowerCase().replace(/\.$/, '');
  const platform = PLATFORM_RULES.find((candidate) =>
    candidate.hosts.some((host) => matchesHost(hostname, host))
  );

  if (!platform) {
    throw new TypeError('Plataforma no compatible. Usa YouTube, TikTok, Instagram o X.');
  }

  url.hash = '';
  return {
    url: url.toString(),
    platform: { id: platform.id, label: platform.label }
  };
}

export const supportedPlatforms = PLATFORM_RULES.map(({ id, label }) => ({ id, label }));
