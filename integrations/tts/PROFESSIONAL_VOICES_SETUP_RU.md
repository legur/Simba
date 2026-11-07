# Simba — тест профессиональных систем озвучки (аудио, без видео)

Актуально: 07.11.2026. Основной голос Simba **WarmBaritone** не изменять без прямого подтверждения.

## Системы

| Сервис | API-модель | Русский мужской голос | Статус |
|---|---|---|---|
| ElevenLabs | `eleven_multilingual_v2` | Выбрать из Voice Library (язык ru, male, взрослый) или создать авторский Voice Design | Нужен API-ключ и voice_id |
| MiniMax | `speech-2.8-hd` | Выбрать и подтвердить русский мужской voice_id | Нужен API-ключ и voice_id |
| Azure Speech | `ru-RU-Lev:MAI-Voice-2` | Lev HD, стиль reflective; резерв ru-RU-DmitryNeural | Нужен Speech-ресурс, ключ и регион |

Документация: https://elevenlabs.io/docs/api-reference/text-to-speech/convert ; https://elevenlabs.io/docs/api-reference/voices/search ; https://platform.minimax.io/docs/api-reference/speech-t2a-http ; https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=tts

## Настройка секретов в GitHub (никогда не присылайте ключи в чат)

Открыть `legur/Simba` → **Settings → Secrets and variables → Actions**.

**Repository secrets**:
- `ELEVENLABS_API_KEY`
- `MINIMAX_API_KEY`
- `AZURE_SPEECH_KEY`
- `AZURE_SPEECH_REGION` (например, только регион действующего ресурса, без URL)

Секреты для приватного Google Drive уже используются в Simba и должны остаться без изменений.

**Repository variables** (не ключи):
- `SIMBA_ELEVENLABS_VOICE_ID` = фактический ID выбранного русского мужского голоса.
- `SIMBA_MINIMAX_VOICE_ID` = подтвержденный ID выбранного русского мужского голоса.
- `SIMBA_PRO_TTS_ONE_REQUEST` = `YES_ONCE` только для разового теста после согласования затрат. После тестов убрать эту переменную или изменить значение, чтобы блокировать повторные вызовы.

## Запуск

Скрипт: `integrations/tts/professional_voice_pilot.py`.
Workflow: `.github/workflows/simba-professional-tts-pilot.yml`.

По умолчанию `python integrations/tts/professional_voice_pilot.py --provider azure --voice-id 'ru-RU-Lev:MAI-Voice-2'` запускает **только dry-run** и не обращается в API. Offline dry-run также выполняется GitHub Actions для проверки скрипта.

После настройки ключа, голоса, явного подтверждения лимита **ОДИН запрос на голос**, можно открыть ровно один GitHub issue от владельца `legur` с соответствующим точным заголовком:
- `Simba pro TTS ElevenLabs test ONE SHOT`
- `Simba pro TTS MiniMax test ONE SHOT`
- `Simba pro TTS Azure test ONE SHOT`

Только при `SIMBA_PRO_TTS_ONE_REQUEST=YES_ONCE` соответствующий issue запустит платный тест. После того как запрос был отправлен, его не надо повторять, даже если GitHub Action завершился ошибкой: состояние списания может быть неясно.

## Ограничения и сохранение

- Один фрагмент: проверенный русский рекламный текст из `prague_male_voices.json`, около 200 символов.
- Один запрос синтеза на один запуск; нет скрытых повторных запросов.
- До платного вызова проверяется приватный Google Drive, затем записывается одноразовая отметка в issue.
- Формат WAV, сохранение в приватной папке `Simba Private TTS Prague 2026-11-07` с проверкой после загрузки.
- Не монтировать видео и не публиковать результаты автоматически.
- Не переносить токены и идентификатор Gemini WarmBaritone в публичный репозиторий.
- Проверять условия коммерческого использования выбранной голосовой модели и лицензии Voice Library отдельно.
