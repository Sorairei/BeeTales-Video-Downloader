# BeeTales Video Downloader

Herramienta libre para preparar descargas de contenido **público y autorizado** de YouTube, TikTok, Instagram y X como video MP4 o audio MP3. Spotify, contenido privado y contenido con DRM están fuera del alcance.

## Arquitectura

- `apps/web`: página HTML/CSS/JS desplegable en GitHub Pages.
- `apps/api`: API Node.js que valida URLs y coordina `yt-dlp` con FFmpeg.
- `test`: pruebas de validación y construcción segura de argumentos.
- `Dockerfile`: backend autoalojable con sus herramientas multimedia.

GitHub Pages solo aloja el frontend. Para analizar y preparar archivos se necesita desplegar el contenedor de la API y configurar su URL en la página.

La API publicada debe usar HTTPS. Una página de GitHub Pages no puede llamar a un backend HTTP por las protecciones de contenido mixto del navegador. Para desarrollo local, usa juntos los servidores HTTP descritos abajo.

## Desarrollo local

Requisitos para descargas reales:

- Node.js 20 o superior.
- `yt-dlp` actualizado y disponible en `PATH`.
- FFmpeg y FFprobe disponibles en `PATH`.

Inicia la API:

```sh
npm start
```

En otra terminal inicia la web:

```sh
npm run dev:web
```

Abre `http://127.0.0.1:4173`. La API usa `http://localhost:8787` por defecto.

## Docker

```sh
docker compose up --build
```

Para publicar la API, establece `PUBLIC_ORIGINS` con el origen exacto de GitHub Pages, por ejemplo:

```env
PUBLIC_ORIGINS=https://sorairei.github.io
```

Después establece la URL HTTPS del backend en `apps/web/config.js`:

```js
window.BEETALES_API_URL = 'https://api.tu-dominio.example';
```

La misma URL se puede cambiar desde la sección «Configuración del servidor» de la interfaz y queda guardada únicamente en ese navegador.

El volumen temporal debe ser mayor que `MAX_FILE_SIZE_MB` multiplicado por la concurrencia, porque durante la unión pueden coexistir varias pistas y el archivo final.

## API

- `POST /api/v1/analyze` con `{ "url": "https://..." }`.
- `POST /api/v1/downloads` con `url`, `type`, `quality` o `audioBitrate`.
- `GET /api/v1/downloads/:id` para consultar progreso.
- `GET /api/v1/downloads/:id/file` para recibir el archivo terminado.
- `DELETE /api/v1/downloads/:id` para cancelar.
- `GET /health` para comprobar el servicio.

Los archivos expiran y se eliminan automáticamente. La cola y el rate limiting son locales a cada instancia; un despliegue con varias réplicas necesitará un almacén y cola compartidos.

## Uso responsable

Que un enlace sea público no significa que su contenido sea de libre distribución. Usa la herramienta solo con contenido propio, de dominio público, con licencia compatible o cuando tengas autorización del titular. El proyecto no evade inicios de sesión, controles de acceso ni DRM.

## Licencia

[MIT](LICENSE)
