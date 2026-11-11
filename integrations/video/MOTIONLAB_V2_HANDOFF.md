# Motion Lab v2: материалы, рекомендации, выбор, безопасная передача

**11 ноября 2026, Issue #113.** Это **предложение контракта** со стороны
Монтажера, предназначенное для утверждения разработчиком Motion Lab.
Статус: `DRAFT_PROTOCOL_CODE_TESTED / OWNER_REVIEW_REQUIRED`.

Исходный принцип: **творческий просмотр и три предложения делает
Motion Lab**, а не Montage. Montage отвечает только за проверенные
материалы Ф2У/A2E, сохранение источников, ограничения настоящего
рендерера, dry-run, конечный MP4, QA. Статический Wix-интерфейс сам
не выполняет мультимодальный анализ — агент Motion Lab должен получить
реальный приватный исходник. Отдельный чат не получает его
автоматически через GitHub.

## 1. Стадии и три версии документа

```text
verified F2U MP4 + approved audio/text
  -> Montage: materials.launch/v2 WITHOUT creative options
  -> private ORIGINAL MP4 + contact sheets delivered to Motion Lab agent
  -> agent REALLY inspects clips; if not accessible => ANALYSIS_INPUT_MISSING
  -> Motion Lab: proposals/v2 (1 recommended + 2 alternatives)
  -> Motion Lab UI: see timeline / edit only renderer knobs
  -> explicit Leo approval -> selection/v2
  -> trusted Montage validator + zero-paid mapper
  -> durable receipt ACK; later project CAS APPLIED;
  -> SPEC_READY only after verified WAV/music/full-timeline job
  -> Montage renderer MP4, actual VIDEO_QA, Leo approval, publish separately
```

**Нельзя** выдать `ACK` за `APPLIED`, а `APPLIED` за
готовое видео. Ни один шаг v2 не разрешает платный TTS/A2E,
авторендер или публикацию. В черновой ветке PR #105 теперь реализованы `selection/v2` и подключенный браузерный мост; в production Wix/owner HTTPS host они еще не развернуты.

### A. `bontours.motionlab.materials.launch/v2` — только Montage

Создается `integrations/video/motionlab_v2_contract.py:make_materials_v2`.
Это функция **без записи и сети**, она сначала проверяет
конкретные локальные MP4 полным SHA-256 и фактическим `ffprobe`.
Параметры исходника, которых нет, не придумываются.

```json
{
  "schema":"bontours.motionlab.materials.launch/v2",
  "project_id":"example-project",
  "request_id":"v2-request-example",
  "stage":"edit_choice",
  "expected_input_fingerprint":"<64 lowercase hex from current handoff>",
  "renderer_capabilities":{"schema":"bontours.montage.renderer-capabilities/v1",
      "revision_sha256":"<real source revision>", "...":"see renderer_capabilities()"},
  "scenes":[{
    "scene_id":"clip-01",
    "asset_id":"<verified F2U asset ID>",
    "name":"Сцена 1",
    "media":{
      "kind":"video","asset_sha256":"<full real MP4 sha256>",
      "duration_s":5.0,"width":1080,"height":1920,"has_audio":false
    },
    "locked":{
      "title_text":"<actual approved title, only if permitted to show>",
      "title_sha256":"<sha256 of exact title>",
      "subtitle_preview":"<actual approved public-facing phrase>",
      "subtitle_sha256":"<sha256 of exact phrase>",
      "read_only":true
    }
  }],
  "approved_audio_sha256":"<sha256 of canonical approved voice + music spec>",
  "constraints":{
    "format":"9:16","max_total_seconds":60,
    "source_ids_immutable":true,
    "approved_text_immutable":true,
    "approved_voice_music_immutable":true,
    "trim_requires_v2_extension":true,
    "allow_paid_operations":false,"allow_publish":false
  },
  "analysis":{
    "status":"PENDING_REAL_MEDIA_ACCESS",
    "required_kind":"full_original_mp4"
  }
}
```

`scenes[].media.fps` добавляется **только** если ffprobe реально
выдал FPS; оно необязательно. Для визуализации разрешен сам
оригинал из защищенного канала или локальный File API внутри
клиентского браузера, но эти два пути нельзя смешивать.
Пакет с actual MP4 / frames не содержит ключи, Drive URLs,
signed URLs или ссылку на публичное Wix.

**В этом документе нет `options[3]`: Montage их не создает.**

### B. `bontours.motionlab.proposals/v2` — автор Motion Lab

Отдельный агент Motion Lab получает реальные файлы, анализирует
композицию, движение, естественные точки склейки и размещение
надписей, согласует только renderable IDs.

```json
{
  "schema":"bontours.motionlab.proposals/v2",
  "project_id":"example-project",
  "request_id":"v2-request-example",
  "expected_input_fingerprint":"<same>",
  "materials_sha256":"<sha256 of exact canonical materials launch>",
  "renderer_revision_sha256":"<same real renderer revision>",
  "analysis":{
    "status":"REAL_VIDEO_REVIEWED",
    "access_mode":"owner_private_material_bundle",
    "review_notes":"<concrete real observations, >=20 characters>",
    "inspected_assets":[{
       "scene_id":"clip-01","asset_sha256":"<actual video hash>",
       "evidence_kind":"full_original_mp4",
       "scene_notes":"<concrete actual observation, >=20 chars>"
    }]
  },
  "proposals":[
    {
      "option":1,"title":"<name>","recommended":true,
      "rationale":"<why this is recommended, >=20 chars>",
      "scenes":[{
        "scene_id":"clip-01",
        "camera":{"id":"cinematic-zoom","intensity_percent":30},
        "transition":null,
        "title_fx":"fade-rise",
        "subtitle":{"style_id":"clean","word_motion_id":"karaoke"}
      }]
    },
    {"option":2,"title":"<different name>","recommended":false,
      "rationale":"<different actual visual reasoning>","scenes":"<same structure>"},
    {"option":3,"title":"<third name>","recommended":false,
      "rationale":"<third actual visual reasoning>","scenes":"<same structure>"}
  ]
}
```

Иллюстрация **не** является готовыми тремя предложениями:
`scenes` у вариантов 2 и 3 здесь сокращено, в настоящем
JSON обязателен полный массив всех сцен.

Только допустимые для PR #115 эффекты:
camera `cinematic-zoom`, `push-through`, `float`;
title `fade-rise`, `none` (если нет утвержденного титра);
30 переходов, кроме `none`; единый subtitle style/motion
для всего ролика. Остальные preview-only. Фактическая
реализация есть только в draft PR #115 до мержа.
**Итоговый интерфейс Motion Lab должен явно показывать это
различие, его код я не меняю.**

`analysis.status=REAL_VIDEO_REVIEWED` и notes являются
**свидетельством/заявлением агента**. Код сверяет SHA, scene IDs,
полноту и смысловую длину, но **не может доказать**, что
мультимодальная модель действительно просмотрела каждый MP4.
Проверка доступности реальных файлов — отдельная обязательная
процедура в доверенной среде. Только contact sheet не доказывает
просмотр движения: при отсутствии полного видео не использовать
`REAL_VIDEO_REVIEWED`.

### C. `bontours.motionlab.selection/v2` — Leo после просмотра

```json
{
  "schema":"bontours.motionlab.selection/v2",
  "project_id":"example-project","request_id":"v2-request-example",
  "expected_input_fingerprint":"<same>",
  "materials_sha256":"<exact materials SHA>",
  "proposals_sha256":"<exact proposals SHA>",
  "format":"9:16",
  "decision":{
    "selected_option":1,
    "options_presented":3,
    "state":"USER_SELECTED_IN_CONNECTED_SESSION",
    "explicit_approval":true,
    "user_selected_at":"<actual UTC ISO 8601>"
  },
  "guards":{
    "run_render":false,"run_tts":false,"run_a2e":false,
    "run_paid_operations":false,"auto_publish":false,
    "preserve_approved_voice":true,
    "preserve_approved_music":true,
    "preserve_approved_narration":true
  },
  "scenes":[{
    "scene_id":"clip-01",
    "camera":{"id":"cinematic-zoom","intensity_percent":30},
    "transition":null,"title_fx":"fade-rise",
    "subtitle":{"style_id":"clean","word_motion_id":"karaoke"}
  }],
  "next_stage":"MONTAGE_PLANNING_REVIEW"
}
```

`scenes[]` содержит **только редактируемые монтажные настройки**.
Никаких `asset_id`, URLs, title strings, subtitles/voice,
trim/in/out, цен и новых медиа. Контракт сохраняет неизменными
исходные media/title/phrase из materials.launch/v2.
Пользовательские правки к выбранному предложению допустимы,
если они проходят настоящий renderer capabilities preflight.

## 2. Проверяющий и pure mapper

`motionlab_v2_contract.py`:
- `validate_materials`, `validate_proposals_v2`,
  `validate_selection_v2`: три различные предложения,
  одно рекомендованное, source SHA, renderer revision, полный
  список сцен, отсутствие изменения текста/media и paid guards;
  explicit user approval, сохраненный только после реального
  подтверждения.
- `map_selection_v2_to_spec`: уже выбранные и проверенные
  эффекты → **копия** approved video-spec.json только после
  actual MP4 SHA-256, ffprobe, current approved audio and
  immutable title/voice/lines/copy. Никаких выдуманных
  `options[3]` от Montage или автоматической подмены camera.
- Возвращает `V2_VIDEO_SPEC_MAPPED_NOT_RENDERED` с
  `render_authorized=false`,
  `preapproved_wav_reuse_verified=false`,
  `total_timeline_verified=false`, `paid_calls=0`.
  До прохождения последних двух gates запуск renderer
  остается **запрещенным**.

## 3. Закрытый пакет для реального анализа в соседнем чате

`integrations/video/motionlab_analysis_bundle.py`
позволяет владельцу создать **в приватной папке вне checkout**
ZIP, включающий:
- `materials.launch.v2.json`;
- **полные проверенные MP4 из Ф2У**, имена
  `originals/scene-01.mp4`… и SHA-256 исходных байтов;
- **контакт-листы по четыре кадра** с настоящими таймкодами
  `contact-sheets/scene-01.png`…;
- `analysis-evidence.json` с SHA оригинала/листов,
  метаданными и честным
  `analysis_status=NOT_YET_REVIEWED_BY_MOTIONLAB`.

ZIP ограничен по размеру, не содержит bearer/OAuth/Drive URL,
пишется в новую owner-private папку с mode `0600`;
проверяется чтением после записи. Никогда не отправляется
в публичные GitHub Issues/Actions/веб-сайт. **Сама сборка ZIP
не передает файлы в соседний чат ChatGPT.**
Владелец или доверенный механизм с реальным доступом к
ChatGPT-файлам должен **отдельно** предоставить его агенту
Motion Lab. Только после фактического просмотра агент вправе
создавать proposals/v2.

Пример на машине с **уже имеющимся** локальным приватным
job-folder и проверенными metadata, без оплаченных операций:

```bash
python integrations/video/motionlab_analysis_bundle.py \
  --materials /srv/simba/private/materials.launch.v2.json \
  --verified-media /srv/simba/private/verified-media.json \
  --job /srv/simba/private/jobs/travel-video \
  --output /srv/simba/private/handoffs/MotionLab-private.zip
```

Команда специально не принимает исходники напрямую из браузера;
входной JSON должен быть создан доверенным интеграционным
компонентом после проверки архивных исходников. Пакеты вне
репозитория, **не делать upload-artifact в публичных Actions**.

## 4. Осталось до production

- Разработчик Motion Lab должен **согласовать схему v2**
  и собственный путь мультимодального анализа; UI PR #116
  уже умеет визуальный последовательный preview и кнопку
  подтверждения, но не автоматически анализирует MP4.
- Черновой PR #105 живого receiver/writeback пока принимает
  **только v1**. Для v2 нужен отдельный owner-authenticated
  server endpoint, protobuf/JSON validator, receipt и
  durable-save. Нельзя послать v2 JSON старому обработчику
  и выдать ложное ACK.
- Приватные MP4 должны быть реально доступны агенту Motion Lab;
  File API в браузере НЕ дает автоматически такой доступ.
- Верификация реального voice/music WAV reuse и полного
  60-секундного таймлайна, затем тест E2E с фактическим
  пользователем/публикацией отдельно. Проверка renderer
  `make_video.py --plan-only` **не** является нулевой по
  расходам: он может повторно вызвать TTS. Наши v2 модули
  его не используют.
- `main` и внутренние файлы Motion Lab не изменяются
  до отдельного согласования. Все правки только в draft
  [PR #115](https://github.com/legur/Simba/pull/115).

**Смежный источник решений:** Issue #113, в частности
комментарии 6789167439 (изменение ответственности) и
6789524105 (UI PR #116 уже merged).

## 5. WYSIWYG-правки после PR #117: согласование renderer-side

**Статус: РЕАЛИЗОВАНО В DRAFT PR #115 / ОЖИДАЕТ ПОДТВЕРЖДЕНИЯ
РАЗРАБОТЧИКА MOTION LAB / НЕ СОЕДИНЕНО С LIVE UI.**

После публикации PR #117 внутренний Motion Lab сохраняет положения
титров и субтитров в отдельном черновике
`bontours.motionlab.visual-layout-draft/v2`. В этом проекте
хранится `scene_layout[]` с привязкой к `scene_id`/`asset_id`.
Для исполнения предложен совместимый в точности формат
`selection/v2.scene_layout[]`:

```json
{
  "decision": {
    "visual_layout_edited": true,
    "explicit_approval": true
  },
  "scene_layout": [
    {
      "scene_id": "scene-1",
      "asset_id": "verified-a2e-1",
      "layout": {
        "title": {"x": 55, "y": 42, "scale": 110},
        "subtitle": {"x": 45, "y": 80, "scale": 90}
      }
    }
  ]
}
```

В полноценном `selection/v2` этот фрагмент дополняет существующие
поля `schema/project_id/request_id/fingerprint/proposals_sha256`,
`scenes[]` и строгие `guards`; он **не** является отдельным
полноценным JSON. **Черновой `DRAFT_NOT_DELIVERED` нельзя
превратить в утверждение** путем изменения только поля status.
Проверяется связанный с текущим проектом `selection/v2`,
выбранный вариант и `explicit_approval=true`; любая правка
сбрасывает прежнее подтверждение.

`proposals/v2.proposals[i].scene_layout[]` может быть подготовлен
агентом Motion Lab, если он предлагает конкретные положения текста.
Если предложенный layout существует, `selection/v2` **обязан**
передать его явно. При `decision.visual_layout_edited=false`
layout должен совпадать с выбранной концепцией (либо с дефолтом,
если предложения его не содержали). При `true` требуется
полный `scene_layout[]` после ручных изменений Лео.
**Потеря хотя бы одного layout при передаче блокируется.**

### Координаты и реальный Canvas2D

- **Область:** весь вертикальный кадр 9:16, а не центральная область
  превью; `x/y` в процентах, **anchor=center**.
- **Границы редактора:** x=36..64%, y=13..87%; `scale`=70..140%
  с шагом 5. Только строгие числа integer, без тихого clamp.
- **Перенос текста:** 72% ширины кадра как **максимальная**
  ширина. При смещении к краю реальный Canvas2D может
  уменьшить ширину переноса ради внутренних безопасных
  отступов 6%; не изменяет выбранные x/y/scale.
- **Титр:** `video-spec.scenes[i].visualLayout.title`,
  реальная координата/размер; не меняет утвержденную строку.
- **Субтитры:** `visualLayout.subtitle` на каждую сцену
  меняет **только геометрию**, не общий `subtitleStyle.style/motion`,
  Whisper word timing и утвержденные реплики.
- **Коллизии:** source-side preflight блокирует опасное сближение
  title/subtitle по Y при одновременном присутствии обоих
  текстов; Canvas2D дополнительно проверяет реальные границы
  блока и останавливает рендер при невозможности вписаться.
  Это fail-closed, не «подвинуть титр как-нибудь».
- **Не реализованы:** отдельно редактируемые шрифты для
  каждой сцены, per-scene subtitle style/motion, позиции текста
  `offer`/price card и `end`/CTA. Эти поля не передавать
  без отдельного согласованного расширения; интерфейс обязан
  обозначать `offer_card/end_card=not_renderable`.
- **Шрифты:** используем действующие глобальные гарнитуры
  рендерера. При желании пользователя действие «применить ко
  всем сценам» выполняется на стороне UI копированием
  `scene_layout[]`; сами сцены в renderer независимы.
  Это не изменение глобального шрифта и не второй движок.

Реальные файлы: `motionlab_layout_contract.py` +
`make_video.py:load_spec/timeline` + `film.js:drawTitle/drawSub`
+ `subtitle_styles.js:drawStyledSubtitle`. Mapper
`motionlab_v2_contract.map_selection_v2_to_spec` помещает
подтвержденное `scene_layout[i].layout` в
`video-spec.scenes[i].visualLayout`. Изменения не применяются
к source asset, озвучке и правам на музыку.

**Тесты:** `test_motionlab_visual_layout.py` проверяет asset-lock,
редактирование/потерю согласования, x/y/scale, коллизии и
отказ от неподдерживаемых `offer_layout/end_layout`. Node
`test_motionlab_subtitle_geometry.mjs` проверяет реальное
рисование Canvas2D через существующую JS-функцию и то, что
изменение X/Y сдвигает настоящие `fillText` координаты.
Технический предел: полный браузерный render 1080x1920
с реальным клиентским видео еще не проведен; требуется
QA-preview после live подключенного v2.


## Integration checkpoint — 11.11.2026 (not production live)

- Motion Lab v2 UI is implemented in `integrations/materials/motionlab/motionlab_v2_ui.js` and linked into the static Wix build. Existing scene/cut editors and visual layout/theme controls remain the only editing UI.
- The private owner host sends trusted materials/proposal SHA hashes in the v2 START payload. Selection includes the current rendered values for every scene, global typography and per-scene exceptions, never raw private videos.
- Each browser submission carries a non-secret `delivery_id` (monotonic per page). An ACK must echo the same ID; an ACK for an edited, timed-out, or superseded choice is ignored. The main editor locks on submit and stays immutable after a server receipt. A new edit requires a newly authenticated session.
- The real renderer refuses to interpret `voice.source=existing_approved_wav` as a new Simba/Edge TTS request. **Direct WAV reuse is still unimplemented and render authorization remains false.** This is an intentional zero-paid fail-closed gate rather than a claimed audio integration.
- The current PR #105 is draft and not mergeable against latest `main` until branch conflicts are reconciled. No real owner HTTPS deployment, Wix publication, MP4 client render, voice reuse or final QA has been completed. Do not conflate an offline JS smoke result with full GitHub CI.


## Existing narration WAV — verified source preflight (zero paid)

New `motionlab_approved_audio.py` performs a **read-only** SHA-256, file size,
24 kHz/16-bit PCM and duration check of an *actual existing* WAV staged
privately from Google Drive, against the canonical `project.json`
`voice_music` handoff (exactly one narration asset). Neither the approved
audio bytes nor private paths are written to GitHub or returned in the result.

Example on an **owner-controlled environment**, with actual files already
staged (no dummy files or automated Drive downloading):

```sh
python integrations/video/motionlab_approved_audio.py \
  --project-json /srv/simba/main-checkout/campaigns/PROJECT/project.json \
  --private-job /srv/simba/private/jobs/PROJECT \
  --wav-name approved.wav
```

A successful report is
`EXISTING_APPROVED_WAV_SOURCE_VERIFIED_NOT_RENDER_READY`, with a canonical
`asset_id`, SHA-256 and duration; `render_authorized=false`.
Mismatches, missing canonical voice approval, symlink traversal or absent
file stop the preflight. This does **not** split the approved narration
into lines, provide voice word timestamps, validate the licensed music,
synchronize offer/end screens, or certify the full 60-second MP4 timeline.

The renderer separately rejects any
`voice.source=existing_approved_wav` until a **direct WAV mixer** with
verified transcript/time alignment is implemented. Never bypass this by
allowing default new TTS.


## 11.11.2026 — Locked Studio audio → trusted v2 session gate (Montage PR #105)

**Status:** implemented in draft branch, **not production ready**. Requires Studio PR #127 `studio_audio_lock.py` to be present in the deployment checkout (it is intentionally *not copied* into Montage files). At `stage_v2.source_context()`, before generating `materials.launch/v2`, Montage checks canonical `voice_music.audio_lock` via `inspect_v2_audio`, then reads real private files through `motionlab_v2_audio_gate.verify_private_audio_manifest()`. Without the Studio module, lock, private files or matching hashes, the session is rejected as `V2_APPROVED_AUDIO_SOURCE_NOT_VERIFIED`. No fallback to legacy v1 approval.

The trusted job folder `<private-root>/<project-id>/` (outside repository checkout) must contain the already-required `approved-video-spec.json`, `verified-media.json` and a local **server-only** `approved-audio-files.json`. Example of the latter, with *illustrative* values only:

```json
{
  "audio_revision_sha256": "<actual Studio canonical audio_lock.audio_revision_sha256>",
  "narration_file": "approved.wav",
  "music_file": "approved-music.mp3"
}
```

The names are local filenames inside the private job, not URLs or absolute paths. `no_narration` requires `narration_file: null`. `approved_clip_audio` is **blocked pending a distinct clip-source gate**; don't mislabel an extracted clip as an approved WAV. No media bytes, local filenames or bearer credentials go to Wix/GitHub via the public `materials.launch/v2`.

Byte receipt `APPROVED_AUDIO_BYTES_VERIFIED_NOT_ALIGNED` proves the WAV/music hashes correspond to Studio-approved metadata; it is **not** proof of ASR alignment, decoded music integrity, audio-mix approval or render-readiness. The launch carries only `audio_revision_sha256`, this byte receipt status and `audio_alignment_status: TIMINGS_NOT_VERIFIED`.

**New fail-closed final review guard:** `check_current_v2(..., selection=...)` blocks `TIMINGS_NOT_VERIFIED`. Phase A trusted session and Phase B Motion Lab proposals can be prepared once actual files exist, but Phase C final visual approval cannot succeed until Montage supplies independently verified `audio_alignment/v1`. Merely attaching a user SRT or supplying syntactically plausible timestamps must not flip the status. No automatic TTS, paid calls, MP4 render, approval or publication was authorized.

Added regression tests: `test_motionlab_v2_audio_gate.py` (actual test WAV + mock canonical Studio metadata, tampered audio, manifest revisions and traversal); these **do not establish** true cross-PR integration. Next integration requires combining Studio PR #127 with Montage PR #105, production word aligner + independent audio QA, verified review-timing handoff and complete E2E tests. Do not merge conflicting draft #105 into `main` until reconciled with current Motion Lab + Studio.
