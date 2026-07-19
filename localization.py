"""Centralized, testable interface localization for BeeTales."""

from __future__ import annotations

from typing import Final


DEFAULT_LANGUAGE: Final = "en"
LANGUAGE_NAMES: Final = {
    "en": "English",
    "es": "Español",
    "pl": "Polski",
    "pt": "Português",
}


TRANSLATIONS: Final[dict[str, dict[str, str]]] = {
    "en": {
        "app_title": "BeeTales Video Downloader",
        "sidebar_product": "VIDEO DOWNLOADER",
        "local_title": "Sora keeps everything local",
        "local_description": "No accounts, advertising, telemetry,\nor BeeTales servers.",
        "tools_ready": "● Tools ready",
        "tools_missing": "● FFmpeg not found",
        "sponsor": "♥  Sponsor on GitHub",
        "language": "Language",
        "appearance": "Appearance",
        "appearance_system": "System",
        "appearance_light": "Light",
        "appearance_dark": "Dark",
        "version": "Version {version}",
        "heading": "Download authorized media",
        "subheading": "YouTube, TikTok, Instagram and X · MP4 video or MP3 audio",
        "local_badge": "100% LOCAL",
        "private_badge": "Private · Ad-free",
        "step_link": "01  SOURCE LINK",
        "url_placeholder": "Paste a public video link",
        "paste": "Paste",
        "clear": "Clear",
        "analyze": "Analyze",
        "analyzing": "Analyzing…",
        "step_output": "02  OUTPUT",
        "format": "Format",
        "video_mp4": "Video MP4",
        "audio_mp3": "Audio MP3",
        "quality": "Quality",
        "video_quality": "Video quality",
        "audio_quality": "Audio quality",
        "save_to": "Save to · Ctrl+O",
        "choose": "Browse",
        "rights": "I confirm that I have permission to download this content.",
        "add_queue": "Add to queue · Ctrl+Enter",
        "step_queue": "DOWNLOAD QUEUE",
        "queue_empty_count": "No items",
        "queue_active_count": "{active} active · {finished} finished",
        "queue_finished_count": "{finished} finished",
        "keyboard_help": "Shortcuts (F1)",
        "clear_finished": "Clear finished",
        "queue_empty": "Downloads will appear here. Links are never saved to history.",
        "ready": "Ready. Paste a public link to begin.",
        "clipboard_empty": "No text was found on the clipboard.",
        "url_required": "Paste a public link first.",
        "duplicate": "This download is already active in the queue.",
        "checking_public": "Checking public media information…",
        "link_ready": "The link is ready to add to the queue.",
        "duration_unknown": "Unknown duration",
        "analyze_first": "Analyze a link first.",
        "confirm_permission": "Confirm that you have permission to download this content.",
        "choose_destination": "Choose a destination folder.",
        "destination_write_error": "The selected folder is not writable.",
        "destination_invalid": "The destination path is not a folder.",
        "destination_dialog": "Choose download folder",
        "queued": "Added to the download queue.",
        "download_complete": "Download completed.",
        "queue_state": "Queued",
        "preparing": "Preparing download…",
        "processing_video": "Merging and validating video…",
        "processing_audio": "Converting to MP3…",
        "processing_compatible": "Optimizing H.264/AAC compatibility…",
        "cancel": "Cancel",
        "cancelling": "Cancelling…",
        "cancelled": "Cancelled",
        "completed": "Completed",
        "open_folder": "Open folder",
        "error": "Error",
        "remaining": "{seconds}s remaining",
        "removed_finished": "Removed {count} finished item(s).",
        "close_title": "Exit BeeTales",
        "close_question": "Active operations are still running. Cancel them and exit?",
        "closing": "Safely closing local operations…",
        "open_error_title": "Could not open folder",
        "open_error_body": "Open this folder manually:\n{directory}",
        "help_title": "Accessibility and keyboard",
        "help_heading": "BeeTales keyboard shortcuts",
        "help_note": "Statuses are also described with text; color is never the only indicator.",
        "shortcut_focus": "Focus and select the public link",
        "shortcut_analyze": "Analyze the link from the URL field",
        "shortcut_clear": "Clear the link and analyzed preview",
        "shortcut_enqueue": "Add the prepared download to the queue",
        "shortcut_destination": "Choose the destination folder",
        "shortcut_help": "Show keyboard help",
        "link_cleared": "Link and preview cleared. Active queue items were not changed.",
        "unexpected_analysis": "An unexpected error occurred while analyzing the link.",
        "unexpected_download": "An unexpected download error occurred.",
        "error_private": "This content is private and cannot be downloaded without authorization.",
        "error_drm": "This content is DRM-protected and is not supported.",
        "error_unavailable": "This content is not publicly available.",
        "error_no_video": "This post does not contain a compatible public video.",
        "error_network": "Could not connect to the platform. Check your connection and try again.",
        "error_unsupported": "This link is not supported or no longer matches the platform format.",
        "error_ffmpeg": "FFmpeg could not complete local media processing.",
        "error_rate": "The platform is temporarily limiting requests. Try again later.",
        "error_session": "This content requires an account session and is not supported.",
        "error_generic": "The operation could not be completed with this public media.",
    },
    "es": {
        "app_title": "BeeTales Video Downloader", "sidebar_product": "DESCARGADOR DE VIDEO",
        "local_title": "Sora procesa todo localmente", "local_description": "Sin cuentas, publicidad, telemetría\nni servidores de BeeTales.",
        "tools_ready": "● Herramientas listas", "tools_missing": "● FFmpeg no encontrado", "sponsor": "♥  Patrocinar en GitHub",
        "language": "Idioma", "appearance": "Apariencia", "appearance_system": "Sistema", "appearance_light": "Claro", "appearance_dark": "Oscuro",
        "version": "Versión {version}", "heading": "Descarga contenido autorizado", "subheading": "YouTube, TikTok, Instagram y X · Video MP4 o Audio MP3",
        "local_badge": "100% LOCAL", "private_badge": "Privado · Sin anuncios", "step_link": "01  ENLACE DE ORIGEN",
        "url_placeholder": "Pega un enlace público de video", "paste": "Pegar", "clear": "Borrar", "analyze": "Analizar", "analyzing": "Analizando…",
        "step_output": "02  SALIDA", "format": "Formato", "video_mp4": "Video MP4", "audio_mp3": "Audio MP3", "quality": "Calidad",
        "video_quality": "Calidad de video", "audio_quality": "Calidad de audio", "save_to": "Guardar en · Ctrl+O", "choose": "Elegir",
        "rights": "Confirmo que tengo permiso para descargar este contenido.", "add_queue": "Agregar a la cola · Ctrl+Enter",
        "step_queue": "COLA DE DESCARGAS", "queue_empty_count": "Sin elementos", "queue_active_count": "{active} activa(s) · {finished} finalizada(s)",
        "queue_finished_count": "{finished} finalizada(s)", "keyboard_help": "Atajos (F1)", "clear_finished": "Limpiar finalizadas",
        "queue_empty": "Las descargas aparecerán aquí. Los enlaces no se guardan en el historial.", "ready": "Listo. Pega un enlace público para comenzar.",
        "clipboard_empty": "No se encontró texto en el portapapeles.", "url_required": "Pega primero un enlace público.",
        "duplicate": "Esta descarga ya está activa en la cola.", "checking_public": "Consultando información pública…",
        "link_ready": "El enlace está listo para agregar a la cola.", "duration_unknown": "Duración desconocida", "analyze_first": "Analiza primero un enlace.",
        "confirm_permission": "Confirma que tienes permiso para descargar este contenido.", "choose_destination": "Elige una carpeta de destino.",
        "destination_write_error": "No se puede escribir en la carpeta seleccionada.", "destination_invalid": "La ruta de destino no es una carpeta.",
        "destination_dialog": "Elegir carpeta de descargas", "queued": "Descarga agregada a la cola.", "download_complete": "Descarga completada.",
        "queue_state": "En cola", "preparing": "Preparando descarga…", "processing_video": "Uniendo y validando el video…",
        "processing_audio": "Convirtiendo a MP3…", "processing_compatible": "Optimizando compatibilidad H.264/AAC…",
        "cancel": "Cancelar", "cancelling": "Cancelando…", "cancelled": "Cancelado", "completed": "Completado",
        "open_folder": "Abrir carpeta", "error": "Error", "remaining": "{seconds}s restantes", "removed_finished": "Se retiraron {count} elemento(s) finalizado(s).",
        "close_title": "Salir de BeeTales", "close_question": "Hay operaciones activas. ¿Quieres cancelarlas y cerrar la aplicación?",
        "closing": "Cerrando operaciones locales de forma segura…", "open_error_title": "No se pudo abrir la carpeta",
        "open_error_body": "Abre manualmente esta carpeta:\n{directory}", "help_title": "Accesibilidad y teclado",
        "help_heading": "Atajos de teclado de BeeTales", "help_note": "Los estados también se describen con texto; el color nunca es el único indicador.",
        "shortcut_focus": "Enfocar y seleccionar el enlace público", "shortcut_analyze": "Analizar el enlace desde el campo de URL",
        "shortcut_clear": "Borrar el enlace y la vista analizada", "shortcut_enqueue": "Agregar la descarga preparada a la cola",
        "shortcut_destination": "Elegir la carpeta de destino", "shortcut_help": "Mostrar esta ayuda de teclado",
        "link_cleared": "Enlace y vista previa borrados. La cola activa no cambió.", "unexpected_analysis": "Ocurrió un error inesperado al analizar el enlace.",
        "unexpected_download": "Ocurrió un error inesperado en la descarga.", "error_private": "Este contenido es privado y no puede descargarse sin autorización.",
        "error_drm": "Este contenido está protegido con DRM y no es compatible.", "error_unavailable": "Este contenido no está disponible públicamente.",
        "error_no_video": "Esta publicación no contiene un video público compatible.", "error_network": "No fue posible conectar con la plataforma. Revisa tu conexión e inténtalo nuevamente.",
        "error_unsupported": "El enlace no es compatible o la plataforma cambió su formato.", "error_ffmpeg": "FFmpeg no pudo completar el procesamiento local.",
        "error_rate": "La plataforma está limitando solicitudes temporalmente. Inténtalo más tarde.", "error_session": "Este contenido requiere una sesión de cuenta y no es compatible.",
        "error_generic": "No se pudo completar la operación con este contenido público.",
    },
    "pl": {
        "app_title": "BeeTales Video Downloader", "sidebar_product": "POBIERANIE WIDEO", "local_title": "Sora przetwarza wszystko lokalnie",
        "local_description": "Bez kont, reklam, telemetrii\ni serwerów BeeTales.", "tools_ready": "● Narzędzia gotowe", "tools_missing": "● Nie znaleziono FFmpeg",
        "sponsor": "♥  Wesprzyj na GitHub", "language": "Język", "appearance": "Wygląd", "appearance_system": "Systemowy", "appearance_light": "Jasny", "appearance_dark": "Ciemny",
        "version": "Wersja {version}", "heading": "Pobierz autoryzowane multimedia", "subheading": "YouTube, TikTok, Instagram i X · Wideo MP4 lub audio MP3",
        "local_badge": "100% LOKALNIE", "private_badge": "Prywatnie · Bez reklam", "step_link": "01  LINK ŹRÓDŁOWY", "url_placeholder": "Wklej publiczny link do filmu",
        "paste": "Wklej", "clear": "Wyczyść", "analyze": "Analizuj", "analyzing": "Analizowanie…", "step_output": "02  FORMAT WYJŚCIOWY",
        "format": "Format", "video_mp4": "Wideo MP4", "audio_mp3": "Audio MP3", "quality": "Jakość", "video_quality": "Jakość wideo", "audio_quality": "Jakość audio",
        "save_to": "Zapisz w · Ctrl+O", "choose": "Wybierz", "rights": "Potwierdzam, że mam prawo pobrać tę zawartość.", "add_queue": "Dodaj do kolejki · Ctrl+Enter",
        "step_queue": "KOLEJKA POBIERANIA", "queue_empty_count": "Brak elementów", "queue_active_count": "Aktywne: {active} · Zakończone: {finished}",
        "queue_finished_count": "Zakończone: {finished}", "keyboard_help": "Skróty (F1)", "clear_finished": "Usuń zakończone",
        "queue_empty": "Pobrane elementy pojawią się tutaj. Linki nie są zapisywane w historii.", "ready": "Gotowe. Wklej publiczny link, aby rozpocząć.",
        "clipboard_empty": "W schowku nie znaleziono tekstu.", "url_required": "Najpierw wklej publiczny link.",
        "duplicate": "To pobieranie jest już aktywne w kolejce.", "checking_public": "Sprawdzanie publicznych informacji…", "link_ready": "Link jest gotowy do dodania do kolejki.",
        "duration_unknown": "Nieznany czas", "analyze_first": "Najpierw przeanalizuj link.", "confirm_permission": "Potwierdź, że masz prawo pobrać tę zawartość.",
        "choose_destination": "Wybierz folder docelowy.", "destination_write_error": "Nie można zapisywać w wybranym folderze.", "destination_invalid": "Ścieżka docelowa nie jest folderem.",
        "destination_dialog": "Wybierz folder pobierania", "queued": "Dodano do kolejki pobierania.", "download_complete": "Pobieranie zakończone.", "queue_state": "W kolejce",
        "preparing": "Przygotowywanie pobierania…", "processing_video": "Łączenie i sprawdzanie wideo…", "processing_audio": "Konwertowanie do MP3…",
        "processing_compatible": "Optymalizacja zgodności H.264/AAC…", "cancel": "Anuluj", "cancelling": "Anulowanie…", "cancelled": "Anulowano", "completed": "Zakończono", "open_folder": "Otwórz folder", "error": "Błąd",
        "remaining": "Pozostało {seconds}s", "removed_finished": "Usunięto zakończone elementy: {count}.", "close_title": "Zamknij BeeTales",
        "close_question": "Trwają aktywne operacje. Anulować je i zamknąć program?", "closing": "Bezpieczne zamykanie operacji lokalnych…",
        "open_error_title": "Nie można otworzyć folderu", "open_error_body": "Otwórz folder ręcznie:\n{directory}", "help_title": "Dostępność i klawiatura",
        "help_heading": "Skróty klawiaturowe BeeTales", "help_note": "Stany są również opisywane tekstem; kolor nigdy nie jest jedynym wskaźnikiem.",
        "shortcut_focus": "Ustaw fokus i zaznacz publiczny link", "shortcut_analyze": "Analizuj link z pola URL", "shortcut_clear": "Wyczyść link i podgląd",
        "shortcut_enqueue": "Dodaj przygotowane pobieranie do kolejki", "shortcut_destination": "Wybierz folder docelowy", "shortcut_help": "Pokaż pomoc skrótów",
        "link_cleared": "Link i podgląd wyczyszczono. Aktywna kolejka nie została zmieniona.", "unexpected_analysis": "Wystąpił nieoczekiwany błąd podczas analizy linku.",
        "unexpected_download": "Wystąpił nieoczekiwany błąd pobierania.", "error_private": "Ta zawartość jest prywatna i nie można jej pobrać bez autoryzacji.",
        "error_drm": "Ta zawartość jest chroniona DRM i nie jest obsługiwana.", "error_unavailable": "Ta zawartość nie jest dostępna publicznie.",
        "error_no_video": "Ten wpis nie zawiera zgodnego publicznego filmu.", "error_network": "Nie można połączyć się z platformą. Sprawdź połączenie i spróbuj ponownie.",
        "error_unsupported": "Ten link nie jest obsługiwany lub format platformy uległ zmianie.", "error_ffmpeg": "FFmpeg nie ukończył lokalnego przetwarzania.",
        "error_rate": "Platforma tymczasowo ogranicza żądania. Spróbuj ponownie później.", "error_session": "Ta zawartość wymaga sesji konta i nie jest obsługiwana.",
        "error_generic": "Nie można ukończyć operacji dla tej publicznej zawartości.",
    },
    "pt": {
        "app_title": "BeeTales Video Downloader", "sidebar_product": "BAIXADOR DE VÍDEO", "local_title": "Sora processa tudo localmente",
        "local_description": "Sem contas, anúncios, telemetria\nou servidores da BeeTales.", "tools_ready": "● Ferramentas prontas", "tools_missing": "● FFmpeg não encontrado",
        "sponsor": "♥  Patrocinar no GitHub", "language": "Idioma", "appearance": "Aparência", "appearance_system": "Sistema", "appearance_light": "Claro", "appearance_dark": "Escuro",
        "version": "Versão {version}", "heading": "Baixe mídia autorizada", "subheading": "YouTube, TikTok, Instagram e X · Vídeo MP4 ou áudio MP3",
        "local_badge": "100% LOCAL", "private_badge": "Privado · Sem anúncios", "step_link": "01  LINK DE ORIGEM", "url_placeholder": "Cole um link público de vídeo",
        "paste": "Colar", "clear": "Limpar", "analyze": "Analisar", "analyzing": "Analisando…", "step_output": "02  SAÍDA", "format": "Formato",
        "video_mp4": "Vídeo MP4", "audio_mp3": "Áudio MP3", "quality": "Qualidade", "video_quality": "Qualidade do vídeo", "audio_quality": "Qualidade do áudio",
        "save_to": "Salvar em · Ctrl+O", "choose": "Escolher", "rights": "Confirmo que tenho permissão para baixar este conteúdo.", "add_queue": "Adicionar à fila · Ctrl+Enter",
        "step_queue": "FILA DE DOWNLOADS", "queue_empty_count": "Sem itens", "queue_active_count": "{active} ativa(s) · {finished} concluída(s)",
        "queue_finished_count": "{finished} concluída(s)", "keyboard_help": "Atalhos (F1)", "clear_finished": "Limpar concluídos",
        "queue_empty": "Os downloads aparecerão aqui. Os links nunca são salvos no histórico.", "ready": "Pronto. Cole um link público para começar.",
        "clipboard_empty": "Nenhum texto foi encontrado na área de transferência.", "url_required": "Cole primeiro um link público.",
        "duplicate": "Este download já está ativo na fila.", "checking_public": "Consultando informações públicas…", "link_ready": "O link está pronto para ser adicionado à fila.",
        "duration_unknown": "Duração desconhecida", "analyze_first": "Analise um link primeiro.", "confirm_permission": "Confirme que você tem permissão para baixar este conteúdo.",
        "choose_destination": "Escolha uma pasta de destino.", "destination_write_error": "Não é possível gravar na pasta selecionada.", "destination_invalid": "O caminho de destino não é uma pasta.",
        "destination_dialog": "Escolher pasta de downloads", "queued": "Download adicionado à fila.", "download_complete": "Download concluído.", "queue_state": "Na fila",
        "preparing": "Preparando download…", "processing_video": "Unindo e validando o vídeo…", "processing_audio": "Convertendo para MP3…",
        "processing_compatible": "Otimizando compatibilidade H.264/AAC…", "cancel": "Cancelar", "cancelling": "Cancelando…", "cancelled": "Cancelado", "completed": "Concluído", "open_folder": "Abrir pasta", "error": "Erro",
        "remaining": "{seconds}s restantes", "removed_finished": "Foram removidos {count} item(ns) concluído(s).", "close_title": "Sair do BeeTales",
        "close_question": "Há operações ativas. Deseja cancelá-las e fechar o aplicativo?", "closing": "Fechando operações locais com segurança…",
        "open_error_title": "Não foi possível abrir a pasta", "open_error_body": "Abra esta pasta manualmente:\n{directory}", "help_title": "Acessibilidade e teclado",
        "help_heading": "Atalhos de teclado do BeeTales", "help_note": "Os estados também são descritos em texto; a cor nunca é o único indicador.",
        "shortcut_focus": "Focar e selecionar o link público", "shortcut_analyze": "Analisar o link pelo campo de URL", "shortcut_clear": "Limpar o link e a prévia",
        "shortcut_enqueue": "Adicionar o download preparado à fila", "shortcut_destination": "Escolher a pasta de destino", "shortcut_help": "Mostrar ajuda de teclado",
        "link_cleared": "Link e prévia limpos. A fila ativa não foi alterada.", "unexpected_analysis": "Ocorreu um erro inesperado ao analisar o link.",
        "unexpected_download": "Ocorreu um erro inesperado no download.", "error_private": "Este conteúdo é privado e não pode ser baixado sem autorização.",
        "error_drm": "Este conteúdo é protegido por DRM e não é compatível.", "error_unavailable": "Este conteúdo não está disponível publicamente.",
        "error_no_video": "Esta publicação não contém um vídeo público compatível.", "error_network": "Não foi possível conectar à plataforma. Verifique sua conexão e tente novamente.",
        "error_unsupported": "Este link não é compatível ou o formato da plataforma mudou.", "error_ffmpeg": "O FFmpeg não concluiu o processamento local.",
        "error_rate": "A plataforma está limitando solicitações temporariamente. Tente novamente mais tarde.", "error_session": "Este conteúdo exige uma sessão de conta e não é compatível.",
        "error_generic": "Não foi possível concluir a operação com este conteúdo público.",
    },
}


def normalize_language(value: object) -> str:
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in TRANSLATIONS:
            return lowered
        for code, label in LANGUAGE_NAMES.items():
            if lowered == label.lower():
                return code
    return DEFAULT_LANGUAGE


def language_from_label(label: str) -> str:
    return next(
        (code for code, name in LANGUAGE_NAMES.items() if name == label),
        DEFAULT_LANGUAGE,
    )


def tr(key: str, language: str = DEFAULT_LANGUAGE, **values: object) -> str:
    selected = TRANSLATIONS.get(normalize_language(language), TRANSLATIONS[DEFAULT_LANGUAGE])
    template = selected.get(key, TRANSLATIONS[DEFAULT_LANGUAGE].get(key, key))
    return template.format(**values)


def appearance_labels(language: str) -> dict[str, str]:
    return {
        "system": tr("appearance_system", language),
        "light": tr("appearance_light", language),
        "dark": tr("appearance_dark", language),
    }


def localize_engine_error(message: str, language: str) -> str:
    """Convert safe canonical engine messages to the selected interface language."""

    lowered = message.casefold()
    categories = (
        (("privad", "private"), "error_private"),
        (("drm",), "error_drm"),
        (("no está disponible", "not available", "eliminad", "removed"), "error_unavailable"),
        (("no contiene", "does not contain"), "error_no_video"),
        (("conectar", "conexión", "connection", "network", "timed out"), "error_network"),
        (("no es compatible", "unsupported", "enlace"), "error_unsupported"),
        (("ffmpeg", "ffprobe"), "error_ffmpeg"),
        (("limitando", "429", "too many requests"), "error_rate"),
        (("sesión", "session", "age"), "error_session"),
    )
    for needles, key in categories:
        if any(needle in lowered for needle in needles):
            return tr(key, language)
    return tr("error_generic", language)
