# Simba Studio — Voice & Music → Montage (шаг 5F)

**Контракт, 10.11.2026.** Дополняет \`VIDEO_PIPELINE.md\`,
\`Музыкальный редактор/MUSIC_EDITOR_v1.0.md\`,
\`integrations/video/simba_voice_issue.py\`,
\`integrations/video/music_input.py\`. **Нового синтезатора голоса или
музыкального загрузчика нет.**

## Когда вызывается

После подтвержденного \`stage_handoffs.a2e_clips=completed\`.
\`handoff.make_handoff\` обязан вернуть
\`READY_FOR_HANDOFF\`, \`recipient=VOICE_AND_MUSIC\`,
\`packet.next_stage=voice_music\` и неизменный
\`packet.receipt_sha256\`.

Музыкальный редактор показывает **три реальные музыкальные композиции**,
проверяет условия коммерческого размещения и online ads по
**конкретному** треку, записывает источники и лицензию. Сценарист
показывает **три полных варианта текста озвучки**; Лео выбирает
отдельно вариант текста и трек. Профиль Simba WarmBaritone уже
утвержден глобально; другие голоса нельзя выбирать молча. Если
голос вообще не нужен (у клипов есть свой звук), это отдельное
явное \`voice.profile=none\`.

**Выбор Лео одновременно означает согласование выбранных
текста/музыки.** Повторно спрашивать то же самое не требуется.
Но он не отменяет требование фактического MP3/WAV, проверку
права использовать музыку и запрет неопределенного платного
повтора Gemini. Текущий шаг **только принимает существующие
аудиофайлы**, не выполняет новый TTS-запрос.

## Приватный план выбора — JSON

После явного выбора сохраняется **не в публичном GitHub**, а в
закрытом Google Drive \`Simba Private AI Drafts\` JSON следующего
формата. Значения, заключенные в \`<...>\`, — обозначения реальных
значений, а не готовые approval/ссылки.

\`\`\`json
{
  "schema_version": 1,
  "project_id": "<approved-project-id>",
  "input_fingerprint": "<real a2e_clips handoff.receipt_sha256>",
  "selection": {
    "texts": [
      {"option": 1, "sha256": "<exact text1 UTF-8 SHA256>"},
      {"option": 2, "sha256": "<exact text2 UTF-8 SHA256>"},
      {"option": 3, "sha256": "<exact text3 UTF-8 SHA256>"}
    ],
    "music": [
      {"option": 1, "source": "mixkit", "track_url": "<actual track1 URL>"},
      {"option": 2, "source": "pixabay", "track_url": "<actual track2 URL>"},
      {"option": 3, "source": "mixkit", "track_url": "<actual track3 URL>"}
    ],
    "text_option": 2,
    "music_option": 3,
    "leo_approval_evidence": "<actual Leo's specific decision with date/context>"
  },
  "voice": {
    "profile": "simba_warmbaritone",
    "text_sha256": "<exact selected text UTF-8 SHA256>",
    "issue_number": "<real existing owner-voice Issue integer>",
    "file_id": "<existing exact voice WAV Drive file ID>",
    "folder_id": "<actual private narration folder ID>",
    "sha256": "<full actual WAV SHA256>"
  },
  "music": {
    "file_id": "<actual MP3/WAV Drive file ID>",
    "folder_id": "<actual private music folder ID>",
    "sha256": "<full music file SHA256>",
    "source": "mixkit",
    "title": "<actual track title>",
    "author": "<actual artist name>",
    "track_url": "<selected option3 actual track URL>",
    "license_url": "https://mixkit.co/license/modal/musicFree/",
    "verified_at": "<actual review date YYYY-MM-DD>",
    "commercial_use_verified": true,
    "online_ads_verified": true,
    "licensed_channels": ["facebook", "instagram"],
    "attribution_required": false,
    "license_evidence": "<actual Music Editor license review citation, date and restrictions>"
  },
  "channels": ["facebook", "instagram"]
}
\`\`\`

**Примечание:** В JSON выше поля \`text_option\`, \`music_option\`,
\`source\`, \`licensed_channels\` и \`verified=true\` — это
**иллюстрация структуры**, не решение Лео и не реальная лицензия.
Они заполняются *только* после фактического выбора и проверки;
никакое демонстрационное значение не должно передаваться
в production. Для \`voice.profile=none\` поле \`voice\` содержит
**только** \`profile=none\` и \`text_sha256\`; никаких
\`file_id\`, \`folder_id\`, \`sha256\` или \`issue_number\`.

## Live readback до записи

\`integrations/materials/voice_music_writeback.py\` требует:
- настоящий private Drive JSON по \`manifest_file_id\` и
  \`manifest_sha256\`, совпадение \`input_fingerprint\`;
- **три различных** SHA текста, три разных реальных URL трека,
  явно выбранные text/music 1–3 и свидетельство решения Лео;
- официальный source домен Mixkit/Pixabay, дату лицензионной
  проверки не старше 90 дней, подтвержденные коммерческое
  использование, online ads и планируемые каналы;
- реальные bytes MP3/WAV из Google Drive; проверка родительской
  папки, owner-only permissions, размера, MD5/SHA256 и
  \`ffprobe\` музыкальной дорожки. **Никаких скачиваний музыки
  с внешних сайтов**;
- если используется WarmBaritone: существующую owner-authored
  GitHub Issue с \`simba-approved-voice\`, sha точного выбранного
  текста из \`issue.body.text\`, тот же destination folder,
  исходный \`Simba_voice_issue_<number>.wav\` и
  \`appProperties.simba_render_marker_id\` от действующего
  TTS-runner, фактические WAV-байты и PCM-параметры
  через **существующий** \`simba_voice._validated_wav\`.
  Это доказательство происхождения WAV, **не** утверждение,
  что финальное распознавание Whisper уже выполнено.

Код не может юридически удостоверить лицензию по одному URL
или обнаружить изменившиеся условия автоматически.
\`commercial_use_verified\` — только
**человеческое подтверждение Музыкального редактора**.
Это не равно \`VIDEO_QA_PASS\` и не дает согласие на публикацию.

## Write-back и выход

После всех проверок этот модуль добавляет в **тот же**
\`campaigns/<project>/project.json\` реальные приватные
\`kind=music\`, а при голосе — \`kind=narration\` assets
(Drive ID, SHA-256, длительность, подтверждения). Затем
пишет \`stage_handoffs.voice_music=completed\`,
\`texts_presented/music_presented=3\`,
\`text_option/music_option\`, \`voice_profile\`,
\`music_license_evidence\`. Никаких медиа/текста/секретного
voice ID в репозиторий не копирует.

\`handoff.make_handoff\` должен отдать
\`READY_FOR_HANDOFF → MONTAGE / edit_choice\`.
Существующий \`dispatcher.py\` автоматически создаст
следующее задание **после** успешного \`push main\`.
Тогда Монтажер показывает три решения переходов,
субтитров и титров. Новые рендеры/TTS/публикация
этим переходом не запускаются.

Выполняется вручную \`.github/workflows/simba-voice-music-writeback.yml\`
на owner \`legur@main\` с ID и SHA уже утвержденного
частного JSON; workflow содержит только Drive OAuth
и GitHub Issue GET, **без** Gemini/A2E ключей.
\`--apply\` использует ранее созданную
\`a2e_writeback.apply_candidate\` для атомарной
CAS записи строго одной карточки. Без \`--apply\`
возвращает только \`VOICE_MUSIC_CANDIDATE_VERIFIED_NOT_WRITTEN\`.

## Статус

На 10.11.2026: **код готов / CI offline tests pass**.
Тесты читают настоящие синтетические PCM WAV-байты и
подменяют Drive/GitHub/ffprobe; реальных текстовых
вариантов и треков для нового утвержденного проекта
пока не предъявлено. Существующие ролики Праги и Баварии
не менять и повторно не озвучивать. Live voice/music
write-back и монтаж по этому новому маршруту еще
не выполнялись.
