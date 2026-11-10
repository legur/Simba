# Motion Lab / автоматическая Киностудия — протокол v1

**Задача:** пользователь выполняет `edit_choice` на сайте; исполнитель запускает интерфейс, а после выбора получает структуру сцен и выбранных приемов. **Не** запускает рендер, A2E, TTS или публикацию.

## Исходный код опубликованного Motion Lab

**Канонический исходный код сайта хранится в этой папке GitHub**.
Ровно 16 файлов страниц/стилей/скриптов соответствуют опубликованной Wix Headless
версии на 10.11.2026 (сверка после переноса):

| Экран | HTML | CSS | JS |
|---|---|---|---|
| Переходы (30) | `index.html` | `styles.css` | `app.js`, `transitions.js` |
| Титры (15) | `text.html` | `text.css` | `text.js` |
| Субтитры (5 + 24) | `subtitles.html` | `subtitles.css` | `subtitles.js` |
| Движение камеры (12) | `camera.html` | `camera.css` | `camera.js` |
| Раскадровка | `storyboard.html` | `storyboard.css` | `storyboard.js` |

**Wix:** https://headless-cvcdjldqjlx-leostraveltips-140e.wix-site-host.com/
— существующий siteId `795efbc2-50c4-435e-939e-537cb2df75c7`.

Для публикации берите **только** перечисленные 16 файлов, с их исходными
именами в корне ZIP либо файлового bundle; загружайте на **существующий**
Wix Headless site как static files. `README.md`, Python, тесты, `demo-launch.json`,
`motionlab_host_adapter.js` и workflow относятся к стороне Simba и не
публикуются веб-сервером. Не используйте `replaceAll` без проверки файлов.

**Важно:** push и merge в GitHub не обновляют Wix автоматически.
Нынешний Wix-сайт уже был опубликован до этой синхронизации. Двусторонняя
автосинхронизация, удаленный вызов агента и сохранение его решения в
защищенной среде **пока не настроены**. Для дальнейших изменений сначала
обновляйте канонический файл в этом каталоге, затем отдельно публикуйте
соответствующие полные файлы в Wix и сверяйте read-back.

Локальные фотографии пользователя и приватные исходные ассеты не
отправляются ни в GitHub, ни в Wix при обычном просмотре/выборе эффектов.
Не коммитьте в этот каталог секреты, клиентские данные, закрытые
`video-spec.json`, временные signed URLs или аудиофайлы.

## Вход

Сервер/агент передает объект `bontours.motionlab.storyboard.launch/v1` (см. `demo-launch.json`) с `request_id`, `project_id`, `stage="edit_choice"`, `expected_input_fingerprint` (SHA-256 предыдущего проверенного этапа), ровно тремя вариантами `options[]`, `scenes[]` с ID исходных ассетов и метаданными.

`preview_url` для каждой сцены необязателен и должен быть HTTPS. Он используется браузером только для показа. Приватные одноразовые ссылки и токены НЕ должны передаваться в публичный сайт; отдавайте только разрешенное preview или используйте демонстрационный фон.

## Браузерный вызов и возврат

Приложение открывает iframe/всплывающее окно `https://headless-cvcdjldqjlx-leostraveltips-140e.wix-site-host.com/storyboard.html?host_origin=<URL-encoded-origin>`. Параметр `host_origin` должен указывать HTTPS-origin приложения, которое инициирует выбор.

1. После загрузки редактор посылает в родительское/открывающее окно `SIMBA_MOTIONLAB_READY` (protocol `bontours.motionlab.bridge/v1`).
2. Родитель отправляет `SIMBA_MOTIONLAB_START` с `payload` из схемы запуска.
3. Редактор валидирует структуру (три варианта, 1–24 сцены, SHA-256 fingerprint) и отвечает `SIMBA_MOTIONLAB_STARTED` с тем же `request_id`.
4. Пользователь меняет настройки, выбирает концепцию и нажимает **«Передать выбор агенту»**.
5. Редактор отправляет `SIMBA_MOTIONLAB_SELECTION` с `payload` схемы `bontours.motionlab.storyboard.selection/v1` строго исходному `Window` и `origin`.
6. **Принимающая сторона** валидирует `request_id`, `project_id`, `expected_input_fingerprint`, реестры ID эффектов, уникальность сцен и правила прав доступа. Только после безопасного сохранения результата отвечает `SIMBA_MOTIONLAB_ACK` с `request_id`, `accepted:true`, `receipt_id`.
7. UI показывает «Принято агентом» **только при реальном ACK**, иначе через 9 секунд предлагает JSON-экспорт.

Пример браузерных сообщений:

```js
// Origin должен совпадать с origin контейнера, где размещена Киностудия.
iframe.contentWindow.postMessage({
  type:'SIMBA_MOTIONLAB_START', protocol:'bontours.motionlab.bridge/v1',
  payload: launch // launch from verified session state
}, 'https://headless-cvcdjldqjlx-leostraveltips-140e.wix-site-host.com');

// После получения и проверки SIMBA_MOTIONLAB_SELECTION:
iframe.contentWindow.postMessage({
  type:'SIMBA_MOTIONLAB_ACK', protocol:'bontours.motionlab.bridge/v1',
  request_id: selection.request_id, accepted:true, receipt_id:'validated-receipt-id'
}, 'https://headless-cvcdjldqjlx-leostraveltips-140e.wix-site-host.com');
```

Обработчик родителя обязан проверять `event.origin` (точный HTTPS-origin Motion Lab) и `event.source` (его iframe), а не принимать сообщения от других окон. Не подтверждать прием до проверки и сохранения. Не включать приватные данные в URL query, логи и GitHub Issues. Задание передается только в `postMessage` или импортируется локально.

## Результат

Содержит `selected_option` 1–3 и per-scene `camera`, `transition`, `title`, `subtitles`, `asset_id`, `duration_seconds`; `user_selected_at`, source fingerprint и ограничения. Он предназначен **для подготовки**, а не для прямого рендера. Прежние утвержденные голос, сценарий и музыку сохраняет принимающий агент.

Если модуль открыт отдельно, он может импортировать JSON задания и экспортировать JSON выбора. Такой экспорт **не** является подтверждением, что автоматический агент его получил.

## Связь с Simba

`integrations/materials/handoff.py`: `stage_handoffs.edit_choice` требует ровно 3 предъявленных варианта, выбранный №1–3, корректный входной fingerprint, непустой `approval_evidence`, реальный ID готового edit_plan asset. UI результат **не** заменяет эти проверки, и самостоятельный выбор на сайте не записывает `project.json`. Агент должен независимо проверить и сохранить результат и evidence в закрытом контуре; только после этого существующий handoff/dispatcher пропускает следующую стадию.

## Готовый браузерный адаптер вызывающей среды

Файл `motionlab_host_adapter.js` предоставляет `storyboardUrl()` и
`connectStoryboard({targetWindow, launch, acceptSelection, onStatus})`.
Вызывающая среда показывает iframe либо открывает popup с `storyboardUrl()`,
а `targetWindow` указывает на `iframe.contentWindow` или popup.
После получения `SIMBA_MOTIONLAB_READY` адаптер передает `launch`.
Callback `acceptSelection` обязан независимо валидировать результат
через `motionlab_selection.validate(launch, choice)`, сохранить решение в
разрешенном приватном хранилище и вернуть `{receipt_id: "..."}`.
**Только тогда** адаптер посылает положительный ACK. Если сохранение не
состоялось, UI не показывает ложную доставку.

Важное ограничение: веб-адаптер сам по себе **не** подключает ChatGPT
агентов и не создает запись `stage_handoffs.edit_choice`.
Эту операцию должен выполнить доверенный исполнитель автоматической
Киностудии после корректного выбора и фактического write-back.
