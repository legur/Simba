# Video: утверждённый пост → вертикальный ролик до 60 секунд

Рендерер фото-историй Simba. Берёт **утверждённый пост** из Content Library, **кадры Рафаэля** и **реплики Сценариста**
и собирает ролик 1080×1920 (Reels / Shorts / TikTok / Facebook): движение камеры по кадрам, голос (edge-tts),
субтитры с подсветкой произносимого слова, карточка оффера, финальная карточка с постером и контактом, музыка и звуки.

Процесс, роли и gates описаны в `SIMBA KNOWLEDGE BASE/06_AGENT_WORKFLOWS/VIDEO_PIPELINE.md`. Этот файл — только про инструмент.

## Установка (один раз, на машине Leo)

Нужны Node 20+, Python 3.11–3.13 и ffmpeg (`winget install Gyan.FFmpeg`; путь WinGet инструмент находит сам).

```powershell
cd integrations\video
npm install
node node_modules\playwright-core\cli.js install chromium-headless-shell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

Голос (edge-tts) и первая загрузка модели Whisper `small` (~480 MB, Hugging Face) требуют интернета.

## Задание: папка с `video-spec.json` и картинками

Папка задания живёт вне Git (по умолчанию `integrations/video/jobs/<packageId>/`, каталог в `.gitignore`).
В ней лежат кадры Рафаэля (9:16, без текста), финальный постер 1:1 и `video-spec.json`:

| Поле | Что это |
|---|---|
| `packageId` | id ролика (латиница, цифры, `.-_`), из него имя файла |
| `sourcePost` | путь к `*__APPROVED.md` от корня репозитория; файл обязан иметь `STATUS: APPROVED` и раздел `## APPROVED_TEXT` |
| `voice` | `{"name": "ru-RU-DmitryNeural", "rate": "-4%"}` (по умолчанию) |
| `scenes[]` | 1–8 сцен: `image`, `move` (`push` / `pull` / `pan-left` / `pan-right` / `rise`), необязательный `title`, `focus` `[x, y]` 0–1, `lines[]` |
| `offer` | карточка оффера: `title`, `rows[]`, `price`, `note`, `lines[]`, необязательный `bg` (картинка фона) |
| `end` | финал: `poster`, `cta`, `contact`, `brand`, `lines[]` |
| `lines[]` | `{"text": ...}` — субтитр и то, что сверяется; `say` — что произносит голос (числа словами, латиница кириллицей); `asr` — как Whisper должен это услышать, если отличается от `text` |

Пример: [`examples/costa-diadema-fjords.video-spec.json`](examples/costa-diadema-fjords.video-spec.json).

### Сцены из готовых видеоклипов (Grok и др.)

Вместо `image` сцена может взять `clip` (`.mp4` / `.mov` / `.m4v` / `.webm`) из папки задания:

```json
{ "clip": "c1.mp4", "lines": [{ "text": "Корабль красивый." }, { "text": "А гулять-то когда?" }] }
```

- Клип кадрируется под размер ролика (cover), длина сцены = длина клипа; `in` / `out` (секунды) обрезают его.
  Камера по умолчанию неподвижна (`move: "none"`): клип уже анимирован.
- **Голос берётся из самого клипа** (`"voice": "clip"`, по умолчанию): губы совпадают с речью. Whisper проверяет, что клип
  произносит строки сцены (сходство ≥ 0.90 — обрезанная фраза не пройдёт), и даёт тайминги для субтитров.
  `"voice": "tts"` — клип без звука, строки озвучивает edge-tts, как у картинок.
- Если у клип-сцены нет `lines`, субтитры берутся из распознанной речи и помечаются в `qa-report.md` для проверки Leo;
  fact gate проверяет и их.
- Музыка — одна общая дорожка на весь ролик (`"music": {"style": "lounge", "bpm": 100}` или спокойная по умолчанию),
  уходит под голос клипов. Своя музыка клипа остаётся в их звуке, поэтому в Grok её лучше просить тихой или без неё.
- `end.bg` / `offer.bg` можно указать именем клипа — фоном станет его последний кадр.

Тест без Grok: `examples/make_test_clips.py` делает «клипы» из картинок с голосом и пометкой «ТЕСТОВЫЙ КЛИП».

### Нарисованные сцены (`"insert"`)

Сцена без картинки и клипа, нарисованная кодом (`template/inserts.js`, `template/cartoon.js`):

- `{"type": "route", "title", "path": [[lon, lat, "Порт"?], …], "ports": {…}, "rows": […]}` — карта маршрута:
  золотой пунктир по точкам, порты загораются, ниже дни и часы стоянок (данные — из поста, их видит fact gate);
- `{"type": "cartoon", "set": "deck|deck2|pool|map|cafe|promenade|halong|halong2|angkor|street|rice|airport", "act"?}` —
  мультяшный Симба с движением пасти в такт голосу; `airport` принимает `"stops": [{"name", "date"?}]` для табло.
  **Только по явной команде Leo** (VISUAL_RULES не допускает мультяшного маскота по умолчанию).

Вставка может иметь `lines` — тогда её длительность считается по голосу, как у картинки.
Финальная карточка принимает `end.table`: `{"title", "sub", "rows": [["Каюта", "1492$"], …], "note"}`.

### Флаги

- `--plan-only` — таймлайн и проверка чтения без рендера; кадры смотреть через `node engine/render/still.mjs <job> <t> … --size 1080x1920`.
- `--draft` — источник ещё не утверждён (по команде Leo): ролик получает статус `VIDEO_DRAFT_SOURCE_NOT_APPROVED`, не для публикации.
- `--workers N` — параллельные браузеры (по умолчанию 2: на встроенной графике больше зависает).

## Запуск

```powershell
integrations\video\.venv\Scripts\python integrations\video\make_video.py integrations\video\jobs\<packageId>
```

Порядок и gates (любой провал останавливает сборку с причиной):

1. `STATUS: APPROVED` у исходного поста.
2. **Fact gate:** каждое число на экране и в субтитрах (цены, даты, телефоны, ночи) должно стоять в `APPROVED_TEXT` буквально.
3. Голос: edge-tts по каждой реплике (кэш в `voice/.cache`).
4. **Speech check:** Whisper слышит каждую реплику обратно (сходство символов ≥ 0.90); заодно даёт тайминги слов для субтитров.
5. Таймлайн из длительности реплик; ролик длиннее 60 с не собирается.
6. **Reading check:** каждая надпись держится на экране не меньше «символы ÷ 15 + 1,5 с».
7. Рендер кадров (headless Chromium), микс (музыка уходит под голос), мастеринг −14 LUFS, `.srt`, обложка.
8. Финальная проверка: длительность, громкость, чёрные кадры, Whisper по готовому миксу → `qa-report.md`.

Результат в папке задания: `<packageId>.mp4`, `<packageId>.srt`, `cover.jpg`, `qa-report.md`.
Статус `VIDEO_READY_FOR_LEO` не разрешает публикацию — она остаётся отдельной командой Leo.

Тестовый прогон без Рафаэля: `python examples/make_test_frames.py jobs/<packageId>` рисует кадры-заглушки с красной
пометкой «ТЕСТОВЫЙ КАДР». Такие ролики не публикуются.

## Происхождение и лицензии

- `engine/render/*.mjs`, `engine/lib.js`, `engine/sfx.py` — из [lemo-opuscar](https://github.com/lemomo-ai/lemo-opuscar), MIT (`engine/LICENSE-lemo-opuscar`).
- Шрифты Montserrat и Playfair Display — SIL OFL 1.1 (`fonts/OFL-*.txt`).
- Музыка и звуки синтезируются кодом (`audio.py`), сэмплов нет.
- Голос — нейронные голоса Microsoft через edge-tts (неофициальный клиент онлайн-сервиса). Для коммерческого использования
  условия Microsoft проверяет Leo; официальная замена с теми же голосами — Azure Speech.


## A2E (Wix-backed) — 02.11.2026

Отдельный внешний генератор клипов (не заменяет Монтажера Клода):
`integrations/video/a2e_adapter.py`. Полный setup, CLI, условия оплаты,
передача clips в video-spec.json и статус Wix-deploy:
[A2E.md](A2E.md).

A2E_Key остается только в Wix Secrets Manager. Старт генерации оплачиваемый
и требует сначала бесплатный quote, затем явные `--send` + `--max-credits`.
Результат A2E — внешний MP4-клип для существующего `scenes[].clip`.
Статус интеграции: CODE_READY, REMOTE_DEPLOY_PENDING. Не считать удаленные
smoke-тесты или публикацию сайта выполненными до фактического подтверждения.
