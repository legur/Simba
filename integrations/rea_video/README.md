# Кадр / rea-video

Самостоятельный специалист: `Кадр/KADR_v1.0.md`. Накопительная база для монтажёра: `Кадр/База/INDEX.md`; карточки создаёт Кадр после просмотра по `CARD_TEMPLATE.md`. Аналогия с TIA относится к хранению/поиску приёмов; библиотеки раздельные. Скрипт выполняет анализ, а запись проверенных карточек/индекса — агент по профилю Кадра.
Upstream: https://github.com/JuneYaooo/rea-video, Apache-2.0.
Установленный commit: `b32fbbdb074adbd72f54505114ed8600366cdaa5`.

Локальное расположение относительно родителя репозитория Simba:
- `video-lab/tools/rea-video` — оригинальные исходники и технический skill;
- `video-lab/.venv-rea` — изолированный Python 3.12, rea-video, OCR и yt-dlp;
- `video-lab/tools/ffmpeg*/bin` — существующие FFmpeg/ffprobe;
- `video-lab/.cache/kadr` — отдельные настройки инструмента.

Из корня репозитория:
```
python integrations/rea_video/kadr.py doctor
python integrations/rea_video/kadr.py analyze "C:/path/reference.mp4" --output "../video-lab/kadr/my-reference"
python integrations/rea_video/kadr.py analyze "https://www.instagram.com/reel/EXAMPLE/" --output "../video-lab/kadr/my-reel"
```
Папка output должна быть новой. При ошибке анализ сохраняет диагностические материалы; повтор — с новым output. Не обходить отказ Instagram логином или автоматическим извлечением cookies. MP4 — запасной вход. URL-загрузка ещё требует проверки на реальном рилсе.

`--quick` пропускает OCR/разделение звука для быстрой технической проверки. Обычный запуск включает эти этапы; разделение может скачать ~67 MB модели. VLM принудительно выключен, платные ключи адаптеру не нужны. Английский машинный отчёт дополняется русским `editor-advice.md` исполнителя после просмотра. Скрипт не генерирует советы автоматически и не запускает монтаж.

Восстановление окружения: Python 3.12 `-m venv ../video-lab/.venv-rea`, затем его Python `-m pip install -e ../video-lab/tools/rea-video yt-dlp rapidocr-onnxruntime`. После установки OCR удалить `opencv-python` и переустановить `opencv-python-headless>=4.8,<5` с `--force-reinstall --no-deps` (пакеты занимают один cv2). Проверить doctor. Снимок проверенных версий — `requirements-local.lock`; исходники и окружение не коммитятся. Это локальная установка, не развёртывание на удалённом исполнителе.
