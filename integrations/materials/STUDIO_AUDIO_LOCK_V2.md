# Studio v2 — каноническая фиксация утвержденной озвучки и музыки

**11.11.2026 · ownership: Studio / Dispatcher · refs #113, #126.**  
**Статус:** `VALIDATED_METADATA_ONLY`, **не live-получение private WAV, не Audio Engine, не production render**.

## Зачем

В прежнем `handoff.py` проверяются выбор трех вариантов текста и музыки, `voice_profile`, лицензия и наличие ассета `narration`. Однако старый `source_fingerprint(project)` включает только `project.sources[]`, поэтому смена WAV/music байтов без обновления источников могла остаться неотраженной в явной аудиоревизии. Исправление — каноническая вложенная запись `voice_music.audio_lock` с криптографической привязкой к выбранным медиа и upstream source.

## Где хранится

В **том же** `campaigns/<id>/project.json` внутри `stage_handoffs.voice_music`; отдельная коллекция, второй диспетчер и новый агент запрещены.

Для **новых v2** стадий `voice_music` необходимо явно указать:

```json
{
  "schema": "bontours.studio.voice-music/v2",
  "state": "completed",
  "input_fingerprint": "<SHA-256 настоящего upstream stage receipt>",
  "assets": ["approved-wav-asset-id", "approved-music-asset-id"],
  "approval_evidence": "<подтвержденный выбор пользователя>",
  "voice_profile": "simba_warmbaritone",
  "texts_presented": 3,
  "music_presented": 3,
  "text_option": 1,
  "music_option": 2,
  "music_license_evidence": "<доказательство проверенной лицензии>",
  "audio_lock": {
    "schema": "bontours.studio.approved-audio-lock/v1",
    "source_revision_sha256": "<handoff.source_fingerprint(project)>",
    "stage_input_fingerprint": "<то же input_fingerprint, что и выше>",
    "approved_text_source_path": "<путь реально существующего элемента project.sources[]>",
    "approved_text_sha256": "<SHA-256 именно этого source элемента>",
    "voice_profile": "simba_warmbaritone",
    "mode": "approved_wav",
    "narration": {"asset_id": "approved-wav-asset-id", "sha256": "<SHA-256 действительных WAV-байтов>"},
    "music": {"asset_id": "approved-music-asset-id", "sha256": "<SHA-256 действительных music-байтов>"},
    "music_license_sha256": "<SHA-256 UTF-8 music_license_evidence>",
    "audio_revision_sha256": "<канонический SHA-256 всех полей audio_lock, кроме самого audio_revision_sha256>"
  }
}
```

Это **образец формы, а не готовые данные**. Нельзя заменить placeholder фиктивной строкой и считать файл согласованным. На каждом используемом ассете `project.assets[]` должны существовать совпадающие `id`, `kind`, `state=available` и `sha256` действительных байтов. Допустимые значения `mode`: `approved_wav` (`narration` kind), `approved_clip_audio` (`animated_clip` kind при `voice_profile=none`, без новой TTS) и `no_narration` (явно `narration=null`, `voice_profile=none`). Музыка с лицензией обязательна в текущем v2 contract.

## Детерминированный revision и инвалидация

`studio_audio_lock.revision_for(lock)` вычисляет SHA-256 канонического JSON всех ключей `audio_lock` **кроме** `audio_revision_sha256`. Канонизация: Unicode UTF-8, sort_keys, compact separators, без NaN. `audio_lock.source_revision_sha256` должен совпадать с актуальным `handoff.source_fingerprint(project)`, `stage_input_fingerprint` — с полем upstream stage. Текстовый source обязан существовать в `project.sources[]` с тем же SHA. Привязка аудио проверяется к `project.assets[]` и к `stage_handoffs.voice_music.assets`, музыка — к SHA evidence лицензии.

- `handoff._validate_stage(voice_music)` теперь **строго проверяет** v2 lock, если объявлена схема v2 или присутствует `audio_lock`. Любая подмена SHA, голоса, музыки, лицензии, текста/источника или input fingerprint → `BLOCKED`.
- Проверенная `voice_music` stage receipt включает весь lock, поэтому изменения audio revision меняют цепочку upstream receipt и делают старые `edit_choice` / последующие записи устаревшими. CAS writeback через доверенный backend обязан повторно проверить актуальную ревизию на каждом gate.
- Старые записи **без схемы v2** остаются доступными для legacy v1; их нельзя автоматически пометить approved v2 или дописать вымышленные SHA. Для нового v2 обязательна отдельная проверка `studio_audio_lock.inspect_v2_audio(project, current_source_fingerprint)`. Результат `VALID_METADATA` — только проверка внутренних метаданных; `external_media_verified=false`, `audio_alignment_verified=false`, `render_authorized=false` **всегда**.
- `catalog.project_issues()` по-прежнему проверяет файлы `project.sources[]` на диске. Только **Montage** в доверенном контексте делает проверку байтов WAV/music из закрытого архива, `audio_alignment/v1` и audio QA, дает таймкоды **до** финального утверждения пользователя в Motion Lab. Отсутствие подтвержденных реальных аудиобайтов/таймингов → `TIMINGS_NOT_VERIFIED` и запрет `SPEC_READY/render`.

## Зоны изменений

**Studio:** `studio_audio_lock.py`, schema `voice_music`, read-only handoff и тесты. Не запускает TTS/A2E, не создает второй Audio Engine, не записывает fake approvals и не меняет реальные проекты автоматически.

**Montage:** `integrations/video/`, approved WAV/music byte read-back, реально выровненные слова, renderer/direct mixing, v2 receiver, per-gate revision checking и доказательство `SPEC_READY`.

**Motion Lab:** графика субтитров и `proposals/v2`, verified-alignment preview и `selection/v2`; визуальный `SRT` пользователя и локальные CLIP-метки не меняют audio lock.

## Запуск тестов

```sh
python3 -m unittest discover -s integrations/materials -p test_handoff.py -v
python3 -m unittest discover -s integrations/materials -p test_studio_audio_lock.py -v
```

Проверяются строгое SHA-подтверждение на уровне **метаданных**, отсутствие новых платных действий, backwards-compatibility, смена WAV/music/source/лицензии, клиповая озвучка, stale upstream stage, неизменность `project.json` от проверяющих функций. Контрактные проверки на реальном доверенном WAV и настоящее end-to-end принадлежат Montage и **пока не выполнены**.
