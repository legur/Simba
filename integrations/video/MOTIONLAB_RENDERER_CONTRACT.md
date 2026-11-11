# Montage ↔ Motion Lab: реальный renderer contract / первый E2E (Issue #113)

> **Уточнение владельца Bon Tours от 11.11.2026, Issue #113:**
> творческий просмотр настоящих клипов, рекомендации и подготовка **трех
> монтажных концепций выполняются Motion Lab**, а не Montage.
> Предлагается новый `materials.launch/v2 → proposals/v2 → selection/v2`;
> в нем **не должно быть обязательных трех options от Montage**.
> Код `map_selection_to_spec` в этом PR пока является лишь **строгим
> адаптером для существующего legacy `launch/v1 → selection/v1`**;
> он не реализует и не подменяет мультимодальный анализ Motion Lab.
> Новую v2-схему требуется утвердить в Issue #113 до внедрения.


**11.11.2026.** Владелец: Montage / интеграция Киностудии.
Статус: `RENDERER_CODE_IN_DRAFT_PR_115 / ZERO_PAID_PREFLIGHT / END_TO_END_NOT_READY`.
Документ описывает только новый модуль `integrations/video/`, не меняет
существующий интерфейс Motion Lab из merged PR #114.

## Уточнение общей цепочки

Рафаэль (статичные утвержденные кадры) → Ф2У / A2E (готовые
короткие MP4, обычно 5–15 с) → приватный Drive-архив / actual
readback SHA-256 → утвержденные voice/music →
**Motion Lab / выбор 3 монтажных концепций** →
**Montage / video-spec.json / MP4 / технический QA** → Leo.
Готовый клип **уже является выходом Ф2У**, не отдельным источником.
Рендерер не создает заново Ф2У, голос или музыкальные исходники.

## 1. Transitional legacy v1: совместимое необязательное расширение

Текущий `bontours.motionlab.storyboard.launch/v1` сохраняется без
смены версии. Адаптер `motionlab_render_contract.with_capabilities`
добавляет к **backend-verified** launch **только**:

```json
{
  "renderer_capabilities": {
    "schema": "bontours.montage.renderer-capabilities/v1",
    "revision_sha256": "<SHA-256 фактических make_video.py, film.js, transitions.js и subtitle_styles.js>",
    "...": "см. renderer_capabilities() — реальный перечень ID, scoped constraints"
  },
  "scenes": [{
    "scene_id": "clip-01",
    "asset_id": "<real approved A2E asset id>",
    "media": {
      "kind": "video",
      "asset_sha256": "<real full MP4 SHA-256>",
      "duration_s": 5.0
    }
  }]
}
```

**Новый основной поток после смены ответственности:** Montage передает
только проверенные материалы, lock constraints и renderer capabilities.
Motion Lab анализирует реально полученные файлы/кадры и уже
в **своей среде** создает рекомендованный монтаж и две альтернативы.
Legacy-`options[3]` в `launch/v1` не является требованием для новой
`materials.launch/v2`. Новая схема будет согласована отдельно.

**Запрещено заполнять эти поля браузеру из демо-файлов.**
`asset_sha256` относится к оригинальному MP4 из приватного
Drive после фактической проверки, а не к snapshot, preview,
скриншоту или публичному Wix. `duration_s` берется из реального
`ffprobe` и проверенного архива, не из предположения «5 секунд».
Текущий интерфейс PR #114 уже умеет читать optional
`scenes[].media.kind/asset_sha256/duration_s` для **локального**
File API preview и не включает blob URL в возвращаемый JSON.
При отсутствии этих полей локальный preview лишь визуальный,
не источник разрешения рендера. Width/height/fps/has_audio можно
добавить позже как **необязательные проверенные метаданные**
после согласования, не подменяя `video-spec`.

`renderer_capabilities.revision_sha256` рассчитывается из реальных
файлов production renderer. Изменения renderer вызывают новый SHA;
сессии со старым SHA отклоняются как stale до materialization.
Никаких приватных ссылок в capabilities нет.

## 2. Реальные возможности после этого PR

**Перечень после PR #115 — только когда PR будет интегрирован:**

- **Камера (пока три):** `cinematic-zoom`, `push-through`,
  `float`. Они теперь **прямо реализованы** в
  `film.js:drawScene` как bounded Canvas2D post-clip motion.
  В `video-spec.scenes[].cameraEffect` передается
  `{"id":"cinematic-zoom","intensity_percent":30}`.
  `move` остается `none` для A2E MP4; эффекты включаются
  **только по явному выбору**, нет скрытой подмены
  `cinematic-zoom→push` или дополнительной генерации.
  Остальные 9 camera ID Motion Lab остаются `preview_only` и
  server preflight их блокирует. В веб-редакторе до
  отдельной правки владельца все 12 могут оставаться помечены
  preview-only; это **не повод менять его файлы из Montage**.
- **Титры:** `fade-rise` = намеренно существующий `drawTitle`
  с появлением снизу; `none` допускается только при пустом
  утвержденном `title_text`. Остальные эффекты титров
  `preview_only`, включая `light-sweep` и `punch-zoom`.
  Новое строгое поле `scenes[].titleEffect` поддерживает только
  `fade-rise/none` и не меняет legacy-сцены.
- **Переходы:** прежние 30 ID из
  `make_video.TRANSITIONS/template/transitions.js`, строго
  `scenes[i].transition`, начиная со **второй** сцены,
  400–2400 ms. `transition.id=none` из Motion Lab
  **не поддерживается** в production: его нельзя заменить
  отсутствующим transition (это включило бы legacy
  crossfade).
- **Субтитры:** 24 стиля + 5 word motions реально поддержаны,
  но строго в **одном** root `video-spec.subtitleStyle` на
  **весь ролик**. Различные настройки по сценам →
  `UNSUPPORTED_PER_SCENE_SUBTITLE`. `style_id=none` не
  означает «отключить субтитры» для production.
  `position` top/middle/bottom, `color`
  lime/gold/sky/white, `scale_percent` 80–135 передаются из
  неизменяемого утвержденного spec, если заданы.
- **Графика/маршруты/BPM/шаблоны `creative-plan/v1`:**
  остаются отдельным demo/preview, автоматического
  production map нет.
- **in/out/crop/overlays/новые word timing:** **v2**, на v1
  любые обрезки и несовпадение полной длительности
  отклоняются; Whisper word timing нельзя придумывать.

## 3. Серверный mapper в video-spec.json

`motionlab_render_contract.map_selection_to_spec(launch, selection,
approved_spec, job_dir, verified_media)` — **чистая функция**
проверки и построения результата, возвращает **копию** готового
`video-spec.json` и отдельную диагностику. Ничего не
записывает и не вызывает TTS/А2E/рендерер.

`verified_media` — **доверенная** таблица `asset_id→{file,
sha256,duration_s}` от приватного архивного adapter. `file`
— **простое локальное имя MP4** внутри gitignored
`integrations/video/jobs/<packageId>/`, ни Drive URL, ни
токенизированный адрес. Перед mapping проверяются:
- актуальный `launch/v1`/connected `selection/v1` через
  прежний `motionlab_selection.validate`, 3 разные
  реально предложенные концепции и неизменный
  `expected_input_fingerprint`;
- `renderer_capabilities` и ревизия кода, 1–8 scenes,
  `9:16`, source asset ID/filename;
- фактические байты локального MP4 и **полный SHA-256**,
  реальный `ffprobe` (длительность, размеры, audio stream),
  полное совпадение `scenes[].media` и trusted asset;
- запрет на дополнительную обрезку и отличающуюся
  `duration_seconds` в v1 (порог проверки 0.15 с),
  отсутствие подмены `title_text`,
  `subtitle_preview`, числа/фактов, voice/music/offer/end;
- только конкретные `renderable` эффекты, согласованная
  глобальная subtitle style/motion.

На выходе модифицируются **только рендерные поля:**
`scenes[].cameraEffect`, `titleEffect`, `transition`,
`scenes[].move="none"`, `title`, глобальный
`subtitleStyle`. Все `lines[].text/say/asr`,
`sourcePost`, `voice`, `music`, `offer`,
`end`, `packageId` остаются из утвержденного upstream
`video-spec.json`.

**Отчет честно пишет:**
`VIDEO_SPEC_MAPPED_NOT_RENDERED`,
`render_authorized=false`,
`preapproved_wav_reuse_verified=false`,
`total_timeline_verified=false`, `paid_calls=0`.
Никакого фактического видео или утверждения из этих
полей не следует.

## 4. Обязательная следующая интеграция — PR #105

PR #105 (draft) содержит приватный live-host и
`motionlab_stage_writeback.py`; он не находится в `main`
и не был объединен с этим новым модулем. На момент написания
PR #105 конфликтует с обновленным `main` после PR #114.

**До `stage_handoffs.edit_choice=approved` надо:**
1. Адаптировать production `build_launch` из PR #105 на
   **истинные** длительности клипов Ф2У (в нем сейчас
   `min(5,actual)` и лимит 3–10 с), прикрепить
   `renderer_capabilities` и `scenes[].media` из
   подтвержденного архива. Все источники и sha менять нельзя.
2. Получить selected JSON и выполнить
   `map_selection_to_spec` в приватном монтажном job; при
   `ContractError` не создавать `edit_choice=approved`,
   выдать безопасный код диагностики пользователю.
3. Разрешить **только** согласованные renderable ID;
   остальное preview-only, без silent fallback.
4. Сохранить receipt + SHA неизменного selected plan и
   v1 spec в защищенное хранилище; CAS writeback в
   `project.json`, push → существующий dispatcher.
5. Доработать повторное использование **уже одобренных WAV**
   при сборке. Важно: существующий `make_video.py --plan-only`
   вызывает `tts()` **до** проверки `plan_only`, поэтому
   это **не бесплатный preflight**. Этот новый mapper
   сам TTS не вызывает и не утверждает readiness.
6. После фактического audio reuse проверить полный таймлайн
   до 60 с **включая** речь, оффер, end card, технический
   QA/Whisper и отдельное решение Leo.

**Не запускать платную генерацию или публикацию на основании одного
выбора оформления в Motion Lab.** Недоступное расширение
не следует заменять «похожим» эффектом.

## 5. Тесты и владельцы

```bash
python -m unittest discover -s integrations/video/tests -p test_motionlab_render_contract.py -v
```

Тесты: synthetic local MP4-like bytes **только для SHA**,
stub `ffprobe` (не реальный media decode в unit-тесте),
строгие v1/renderer revision/title/clip locks,
противоподменные проверки, 30/24/5 ID и ошибочные
preview-only выборы. Реальный MP4 E2E остается отдельным.
В CI `montage-motionlab-renderer-contract.yml` проходят
также предыдущие проверки реального рендерера.

**Motion Lab owner** сам решает, когда обновлять
`rendererIssues` и визуально маркировать новые три camera ID
и `fade-rise` как renderable **после** проверки и согласования
этого PR. Этим PR **не изменяются**
`integrations/materials/motionlab/{storyboard.html,
storyboard.css,storyboard.js,motionlab_selection.py,...}`.
