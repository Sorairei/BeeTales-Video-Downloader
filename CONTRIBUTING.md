# Contribuir

Las mejoras, correcciones y propuestas son bienvenidas mediante GitHub Issues y pull requests.

## Reglas básicas

1. Crea una rama para cada cambio.
2. Ejecuta `python -m unittest -v test_downloader.py`.
3. Ejecuta `python -m py_compile app.py downloader.py queue_manager.py settings.py release_smoke.py theme.py`.
4. No incluyas cookies, tokens, archivos descargados ni URLs personales en pruebas o reportes.
5. Conserva la separación entre interfaz y motor multimedia.
6. No añadas DRM, evasión de autenticación, descargas privadas, Spotify ni eliminación artificial de marcas.
7. Mantén la interfaz sin publicidad, telemetría ni funciones premium.

Los extractores específicos pertenecen a yt-dlp. Evita duplicarlos dentro de BeeTales salvo que exista una razón técnica documentada.
