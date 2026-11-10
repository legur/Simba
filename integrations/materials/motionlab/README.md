# Motion Lab / автоматическая Киностудия — протокол v1

**Задача:** пользователь выполняет `edit_choice` на сайте; исполнитель запускает интерфейс, а после выбора получает структуру сцен и выбранных приемов. **Не** запускает рендер, A2E, TTS или публикацию.

## Исходный код опубликованного Motion Lab

**Канонический исходный код сайта хранится в этой папке GitHub**.
В репозитории теперь 19 статических файлов. Пять старых модулей и новая библиотека графики/ритма размещаются на прежнем Wix Headless сайте. После изменения канонические файлы публикуются отдельным шагом:

| Экран | HTML | CSS | JS |
|---|---|---|---|
| Переходы (30) | `index.html` | `styles.css` | `app.js`, `transitions.js` |
| Титры (15) | `text.html` | `text.css` | `text.js` |
| Субтитры (5 + 24) | `subtitles.html` | `subtitles.css` | `subtitles.js` |
| Движение камеры (12) | `camera.html` | `camera.css` | `camera.js` |
| Раскадровка | `storyboard.html` | `storyboard.css` | `storyboard.js` |
| Объекты (15), маршруты (10), музыкальные схемы (8), шаблоны (5) | `creative.html` | `creative.css` | `creative.js` |

**Wix:** https://headless-cvcdjldqjlx-leostraveltips-140e.wix-site-host.com/
— существующий siteId `795efbc2-50c4-435e-939e-537cb2df75c7`.

Для публикации берите **только** перечисленные 19 файлов, с их исходными
именами в корне ZIP либо файлового bundle; загружайте на **существующий**
Wix Headless site как static files. `README.md`, Python, тесты, `demo-launch.json`,
`motionlab_host_adapter.js` и workflow относятся к стороне Simba и не
публикуются веб-сервером. Не используйте `replaceAll` без проверки файлов.

### Автоматическая публикация GitHub → Wix

Workflow: `.github/workflows/motionlab-wix-deploy.yml`. После **push/merge
в `main`**, затрагивающего файлы Motion Lab HTML/CSS/JS или сам workflow,
он проверяет все 19 публичных файлов; публикационный шаг временно приостановлен (см. ниже) и не публикует их на **существующий Wix
siteId** `795efbc2-50c4-435e-939e-537cb2df75c7`. PR запускает
только проверку, без доступа к секрету и без публикации. В ручном
`workflow_dispatch` по умолчанию выполняется только проверка; для
публикации нужно отдельно выбрать `publish=true`.

**Одноразовая активация (действия владельца):**

1. Создать отдельный Wix API key в
   https://manage.wix.com/account/api-keys с правами на управление
   соответствующим Wix Headless сайтом. Ограничить ключ сайтом Motion Lab,
   а не всеми сайтами Bon Tours. Не вставлять ключ в чат, PR, Issues или
   статические HTML/JS.
2. Открыть https://github.com/legur/Simba/settings/secrets/actions,
   создать **Repository secret** с точным именем
   `MOTIONLAB_WIX_API_KEY` и вставить его значение туда.
3. В GitHub Actions выбрать **Motion Lab — automatic Wix deployment** →
   **Run workflow**, `main`, `publish=true` для первичной публикации.
   После успешного запуска каждое изменение опубликованных файлов,
   объединенное с `main`, вызывает публикацию автоматически.

**Без ключа автоматическая публикация НЕ активирована:** она
останавливается с понятной ошибкой. Код и workflow могут быть слиты в
`main` без фиктивного заявления об успехе публикации.

Технические ограничения и защиты:

- Из `integrations/materials/motionlab/` в Wix отправляются **строго**
  19 публичных файлов: HTML/CSS/JS шести экранов. `README.md`, GitHub
  workflow, `demo-launch.json`, `motionlab_host_adapter.js`, Python,
  тесты и приватные ассеты не попадают в статический сайт.
- Wix **static drop заменяет весь набор** файлов. Перед передачей
  workflow запрашивает Wix inventory и прекращает работу при
  отсутствующих либо дополнительных файлах, чтобы не стереть чужие
  изменения. Один workflow запускается за раз; ручные изменения в Wix
  между проверкой и публикацией все равно создают риск конфликта.
- Workflow использует документированный Wix REST API Key: заголовок
  `Authorization` с исходным ключом и `wix-account-id` для account-level
  Headless static-drop API. Ключ хранится только в GitHub Actions Secret.
  Никаких короткоживущих CLI-токенов или прав пользователя из ChatGPT в CI нет.
- После публикации workflow повторно проверяет список файлов. Он
  **не** проводит полный браузерный и видео-QA, не запускает A2E/TTS/MP4
  и не публикует рилсы.
- Это **односторонний** GitHub → Wix deploy, не двусторонняя синхронизация.
  Если править сайт напрямую в Wix, такие правки могут быть перезаписаны
  следующим GitHub deploy. Все новые правки сначала делать в `main`.

Удаленный вызов агента и сохранение выбора в защищенной автоматической
среде остаются отдельной задачей и не подразумеваются этим deploy.

Локальные фотографии пользователя и приватные исходные ассеты не
отправляются ни в GitHub, ни в Wix при обычном просмотре/выборе эффектов.
Не коммитьте в этот каталог секреты, клиентские данные, закрытые
`video-spec.json`, временные signed URLs или аудиофайлы.


## Подготовительные библиотеки 06–09

Единый интерфейс `creative.html` содержит:

- **Объекты:** 15 самостоятельных CSS-демонстраций появления/акцента для цен, карточек, значков и логотипа.
- **Маршруты:** 10 анимаций SVG-линии, остановок и условного движения самолета/корабля. Координаты **условны**, это не географическая карта; реальную трассу и порядок остановок утверждает агент/оператор тура.
- **Музыкальные акценты:** 8 схем, основанных на BPM, введенном или отбитом вручную. Опциональный аудиофайл открывается локально, **алгоритма автоматического распознавания ударов нет**. Музыкальная разметка — предложение к монтажу, не гарантированный музыкальный анализ.
- **Режиссерские шаблоны:** 5 сочетаний камеры, переходов, титров, оформления субтитров и новых приемов. Ссылки в `storyboard.html?creativePreset=<id>` заполняют **только демонстрационную** раскадровку. После получения задания агента источник истины — его три предложенных варианта.

Общая подборка сохраняется в `localStorage` браузера и экспортируется как `bontours.motionlab.creative-plan/v1`. Всегда содержит `status=DRAFT_NOT_DELIVERED` и явные запреты на рендер, платные сервисы и публикацию. Это **не** `stage_handoffs.edit_choice` и не подтвержденная доставка в автоматическую среду. Структуры нового черновика и проверенного канала `SIMBA_MOTIONLAB_SELECTION` нельзя механически объединять: для автоматической передачи нужен отдельный контракт, приемник и подтвержденный серверный receipt.

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

### Временная блокировка публикации (10.11.2026)

Несмотря на `Specific sites: Anime Transition Lab`, `Manage Sites` и
`Wix CLI - Git Integration`, Wix CLI для **Headless** проекта
`795efbc2-50c4-435e-939e-537cb2df75c7` с внутренним приватным
`appId=78ffbc67-367d-40e6-8f21-b2d2b1a760af` возвращает
`403 PERMISSION_DENIED: VELO.APP_PROJECT_READ` на
`POST /_api/wix-code-app-deployments/v1/app-projects/{appId}/app-deployments`.
Повторено после обновления разрешений ключа, в том числе в
GitHub run `42879839810` (attempt 4).

GitHub **PR/push validation продолжает работать**, но автоматический
публикационный шаг временно **выключен** для `push`, чтобы не плодить
падающие сборки и уведомления. Для диагностического Wix CLI **preview**
(без публикации) разрешен только ручной `workflow_dispatch` с
`publish=true`. До устранения права для Headless private app **не
считать автоматическую публикацию настроенной**. Не включать
`All permissions` ради обхода отказа.

Следующий шаг: передать Wix Support сайт, `appId`, точный код отказа и
уточнить, какое право/тип идентичности требуется **именно Wix-managed
Headless** проекту для неинтерактивного `wix preview/release`.
После официального ответа проверить preview, затем отдельно вернуть
автодеплой `main` и заменить preview на release в CI.
