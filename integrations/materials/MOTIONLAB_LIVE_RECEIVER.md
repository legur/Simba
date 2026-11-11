# Motion Lab — живой прием выбранного монтажа (5G Host Relay)

10.11.2026 · \`CODE_TESTED / DEPLOY_NOT_CONFIGURED\` · относится к PR №105.

## Что добавлено

**Выполняется без ручной передачи JSON после развертывания сервиса.**
Это защищенный companion backend для существующего Wix Headless
Motion Lab из PR №112. Ни Wix сайт, ни его эффекты/субтитры/переходы
не дублируются. Готовые клипы поступают из Ф2У/A2E, после реального
Drive MP4 readback и утверждения voice/music.

- \`integrations/materials/motionlab_live_receiver.py\` —
  HTTP-сервис, короткоживущие сессии, SQLite receipt, отдельная очередь
  обработки; приватное Drive GET/POST и безопасный GitHub CAS PUT.
- \`integrations/materials/motionlab/motionlab_host.html\`, \`.css\`,
  \`motionlab_host_page.js\` — собственная оболочка ведущего,
  открывающая **существующий** редактор Motion Lab в iframe.
- \`motionlab_live_host.js\` переиспользует **старый**
  \`motionlab_host_adapter.js\`; после отправки \`SELECTION\` отвечает
  браузеру \`ACK\` только при подтвержденном durable SQLite receipt.
- \`test_motionlab_live_receiver.py\` и
  \`motionlab/repo-tests/test_motionlab_live_host.mjs\` —
  нефиктивные SQLite-операции, имитация закрытого Drive и GitHub CAS,
  имитация postMessage, проверка отказа при отсутствии receipt.

## Две стадии подтверждения

1. **Получено**: \`SELECTION\` проверено существующим
   \`motionlab_selection.validate\`, текущим
   \`handoff.make_handoff\` и исходными MP4 ID; записано в
   защищенную SQLite WAL с \`synchronous=FULL\`.
   Только после COMMIT сервер возвращает \`receipt_id\`, после
   чего браузер получает \`SIMBA_MOTIONLAB_ACK:accepted=true\`.
   Это **не** утверждение, что \`project.json\` уже обновлен.
2. **Передано монтажеру**: отдельный durable worker заново
   проверяет источники, записывает два JSON в закрытую папку
   Drive с детерминированными именами и readback SHA-256/MD5,
   вызывает **существующий** \`motionlab_stage_writeback.build_candidate\`,
   затем выполняет CAS-обновление только
   \`campaigns/<project_id>/project.json\` через GitHub.
   После успеха статус \`APPLIED\`; обычный
   \`simba-video-stage-dispatch.yml\` создает задачу
   \`MONTAGE_RENDERER\`, **не** сам MP4.
   При неясной ошибке \`BLOCKED\`, автоматического повтора
   PUT или платных вызовов нет.

Браузерная оболочка различает «сохранено» и «передано».
Она может опрашивать статус по кнопке или до 60 секунд
после выбора, не дублируя запросы на платный монтаж.

## Как открывается защищенная сессия

**Только доверенный backend/оркестратор** отправляет запрос на
\`POST /api/motionlab/session\` с
\`Authorization: Bearer <SIMBA_MOTIONLAB_OWNER_TOKEN>\` и JSON:

\`\`\`json
{"project_id":"<real-approved-project-id>","options":[
  {"name":"<option1>","description":"<actual complete montage proposal>","settings":{
   "camera":"cinematic-zoom","transition":"crossfade","titleFx":"fade-rise",
   "subtitleStyle":"clean","wordMotion":"karaoke","intensity":25}},
  {"name":"<option2>","description":"<actual different proposal>","settings":{
   "camera":"push-through","transition":"whip","titleFx":"punch-zoom",
   "subtitleStyle":"outline","wordMotion":"active-pop","intensity":70}},
  {"name":"<option3>","description":"<actual different proposal>","settings":{
   "camera":"float","transition":"postcard","titleFx":"light-sweep",
   "subtitleStyle":"luxury","wordMotion":"highlight-strip","intensity":40}}
]}
\`\`\`

Значения здесь **демонстрационные**, не настоящее решение Лео.
Production применяет только действительно предъявленные варианты.
Сервер проверяет текущий \`voice_music\` handoff, реальные
\`a2e_clips\` MP4, receipts и варианты.

Ответ содержит \`studio_url\` с **временным токеном в URL-фрагменте**:
\`https://<trusted-host>/studio#<session_id>.<capability>\`.
Фрагмент не уходит на HTTP-сервер как часть GET.
Оболочка сразу удаляет его из адресной строки и извлекает
подтвержденный \`launch\` по
\`GET /api/motionlab/session/<session_id>\` с заголовком
\`X-Simba-Capability\`. Ссылка действует 20 минут и
предназначена **только одному согласующему пользователю**.
Ее нельзя публиковать в Issues, логах, сообщениях или на сайте.

При загрузке существующий \`motionlab_host_adapter.js\` передает
\`START\`, получает \`SELECTION\`, проверяет \`origin\` и
\`event.source\`, затем вызывает защищенный
\`POST /api/motionlab/selection\` на **том же origin**.
\`ACK\` отправляется только при подтвержденном \`persisted=true\`.
\`GET /api/motionlab/status/<session_id>\` не раскрывает приватные
поля и сообщает \`QUEUED/PROCESSING/APPLIED/BLOCKED\`.

## Что нужно для реального запуска

1. Постоянный сервер с Python 3.12+ и доступом по HTTPS через
   отдельный reverse proxy/сервер. Процесс Python **привязывается
   только к 127.0.0.1**, не должен быть открыт напрямую по HTTP.
   Открывать наружу только ровно используемые API/страницу Studio,
   с rate limit, TLS и корректными proxy/security headers.
2. Отдельный чистый checkout **\`main\`** репозитория \`legur/Simba\`
   (не PR-ветка, не каталог с изменяемыми исходными файлами).
   Он нужен, потому что \`handoff.make_handoff\` проверяет реальные
   \`sources[]\`, \`project.json\` и SHA. После каждого GitHub
   writeback этот checkout требуется обновлять, иначе следующая
   сессия того же проекта безопасно блокируется как устаревшая.
   **Не выполнять \`git reset --hard\` в рабочем каталоге пользователя.**
3. Постоянный **приватный** диск для SQLite/WAL, вне GitHub checkout.
   База и \`.db-wal\` должны быть доступны только Unix-пользователю
   сервиса; запуск с \`umask 077\`. Создание базы внутри GitHub
   checkout прямо запрещено скриптом.
4. Переменные окружения сервера, полученные **только по защищенным
   каналам**, не в GitHub файлах/Issues/браузере:
   \`SIMBA_MOTIONLAB_HOST_ORIGIN=https://<trusted-host>\`,
   \`SIMBA_MOTIONLAB_OWNER_TOKEN\` (случайный секрет ≥32 символов),
   \`SIMBA_GITHUB_WRITE_TOKEN\` (минимально необходимые
   Contents read/write права \`legur/Simba\`),
   и уже действующие \`GDRIVE_OAUTH_CLIENT_ID\`,
   \`GDRIVE_OAUTH_CLIENT_SECRET\`, \`GDRIVE_OAUTH_REFRESH_TOKEN\`.
   Веб-страница **никогда не получает** эти переменные.
   Токен для GitHub должен иметь тип, при котором push
   запускает \`simba-video-stage-dispatch.yml\`.
5. Библиотеки из существующих модулей: \`google-api-python-client\`,
   \`google-auth\`, \`google-auth-httplib2\`, \`requests\`.
   Установка пакетов сама по себе не развертывает внешний сервис.

Пример локального запуска **на отдельной серверной машине**:

\`\`\`sh
python3 -m pip install google-api-python-client google-auth google-auth-httplib2 requests
python3 integrations/materials/motionlab_live_receiver.py \
  --repo-root /srv/simba/main-checkout \
  --sqlite /var/lib/simba-studio/private/receiver.sqlite --port 8765
\`\`\`

HTTPS proxy направляет \`/studio\`, \`/assets/motionlab_*.\`,
\`/api/motionlab/*\` к \`127.0.0.1:8765\`.
Внешний host origin задается в конфигурации, сервер не позволяет
постороннему \`Origin\` отправлять решения.
Статическое приложение Wix **не содержит** ключей.
\`motionlab_host.html\` является страницей на **новом защищенном
origin** backend, а не двадцатым публичным файлом Wix PR №112.

## Реально проверено и что не заявляем

**CI**: Python offline настоящий SQLite и SHA-256,
mock Google Drive/GitHub, JS browser postMessage ACK, блокировки
неавторизованных/expired/чужих/stale/draft решений.
**НЕ** выполнялись: внешний HTTPS deployment, настоящий выбор в
Wix браузере, успешное обновление production \`main\`, реальный
запуск Монтажера, новые платные вызовы или публикация.

**Отдельная известная проблема:** автоматическая публикация
статического Wix Headless Motion Lab через GitHub Actions ранее
заблокирована \`403 VELO.APP_PROJECT_READ\`. Этот companion host
не меняет/не обходит права и не устраняет Wix deploy issue.

## V2: новая рабочая цепочка Motion Lab → защищенный приемник (11.11.2026)

**Код объединен в черновой PR #105 вместе с renderer v2 из PR #115.
Проверен офлайн, НО НЕ РАЗВЕРНУТ НА ВНЕШНЕМ HTTPS HOST.** Внутренние
файлы `storyboard.html/css/js`, `visual_editor.js`, `scene_pages.js`
Motion Lab не изменялись.

В v2 **три рекомендации пишет только Motion Lab** после доступа к
оригинальным MP4 Ф2У. Монтажер не передает фиктивные варианты. В ветке PR #105 теперь есть новый подключенный браузерный v2 мост,
но публичный Wix по-прежнему использует старую версию до успешного
развертывания. Сервер никогда не переводит отдельный локальный
`visual-layout-draft/v2` в подтвержденное решение без явного
`selection/v2` и долговечного ACK.

### Приватные источники на owner HTTPS host

На сервере требуется переменная окружения:

`SIMBA_MOTIONLAB_PRIVATE_JOBS_ROOT=/srv/simba/private/jobs`

Это отдельная приватная папка **вне** публичного Git checkout.
Для проекта `<project_id>` в ней должны находиться:

```text
/srv/simba/private/jobs/<project_id>/
    approved-video-spec.json
    verified-media.json
    scene-01.mp4
    scene-02.mp4
    ...
```

`approved-video-spec.json` — фактический ранее утвержденный
`video-spec.json` с неизменными voice/music, sourcePost,
lines/say/asr, title, offer/end. Файл должен иметь
`packageId=<project_id>`; пока аудиомедиа и полный таймлайн
не проверены, он является лишь **источником для zero-paid mapper**,
не прямым разрешением запускать renderer.

`verified-media.json` — приватный доверенный массив по каждой
сцене **в том же порядке**, что в `a2e_clips.assets[]`:

```json
[{
  "scene_id":"clip-01","asset_id":"<actual approved asset id>",
  "file":"scene-01.mp4",
  "sha256":"<actual full SHA256>",
  "duration_s":5.0
}]
```

Это не ввод от браузера. Сервер повторно сверяет имена,
`asset_id`, реальные bytes MP4 и ffprobe, длительность,
`recorded_sha256` в canonical `project.json`, финальный
`voice_music` handoff и текущий stage fingerprint. Нет файлов,
разрешений или серверной переменной — **v2 session не создается**.

### Две owner-фазы, затем клиентское подтверждение

**Фаза A.** Доверенный процесс (не UI) вызывает
`POST /api/motionlab/v2/session` с
`Authorization: Bearer <SIMBA_MOTIONLAB_OWNER_TOKEN>`:

```json
{"project_id":"<approved-project>"}
```

Ответ включает `launch` схемы
`bontours.motionlab.materials.launch/v2`, `session_id`,
`studio_url` с токеном в URL fragment, `capability` (только
короткоживущая личная сессия), статус
`AWAITING_REAL_MOTIONLAB_PROPOSALS`. На этом этапе
`options[3]` НЕТ. Срок действия 20 минут; аналитика реальных
видео и подготовка предложений должны проходить в пределах этой
сессии или должна быть создана новая сессия и документы.

**Фаза B.** Владелец/доверенная среда **после фактического
просмотра видео** передает три рекомендации Motion Lab через
`POST /api/motionlab/v2/proposals` с тем же owner bearer:

```json
{"session_id":"<session id>","proposals":{
  "schema":"bontours.motionlab.proposals/v2",
  "...":"полная реальная схема из MOTIONLAB_V2_HANDOFF.md"
}}
```

Нельзя сначала создать предложения, а затем переименовать
`request_id`: SHA материалов и `request_id` должны
совпасть с **конкретной** фазой A. Сервер проверяет три
**различных** варианта, одну рекомендацию, правильные
возможности рендерера и анализ-аттестации, затем надежно
фиксирует набор в SQLite. Заменить уже сохраненные
предложения другим набором нельзя.

**Фаза C.** В подготовленном коде UI v2 редактор получает
`SIMBA_MOTIONLAB_V2_START` с материалами/предложениями,
наглядно показывает их, принимает поправки Лео (в том числе
`scene_layout[]`) и **только после нового явного подтверждения**
отправляет `SIMBA_MOTIONLAB_V2_SELECTION`, protocol
`bontours.motionlab.bridge/v2`.

Owner-host-адаптер `motionlab_v2_live_host.js` принимает
сообщения только от проверенного Wix `origin` и
`iframe.contentWindow`; отбрасывает старые v1 сообщения,
черновики и выбор без `explicit_approval`, `guards=false`
или без всех измененных `scene_layout[]`. Затем вызывает
`POST /api/motionlab/v2/selection` с **только одноразовой
session capability** (никаких owner/GitHub/Drive ключей).
Backend повторно проверяет source, proposals SHA, WYSIWYG
и mapped `video-spec.json` и записывает в SQLite
`selection_json`, `spec_json`, `receipt_id`
одной транзакцией c `synchronous=FULL`. Только после
ее COMMIT отправляется `SIMBA_MOTIONLAB_V2_ACK accepted=true`.

### После ACK: worker + GitHub CAS

Существующий v1 Relay/SQLite/Drive/GitHub CAS расширен
для v2, **второго исполнителя/очереди нет**. Worker:
1. Еще раз сверяет `project.json`, approved private MP4
   и spec; проверяет, что bytes mapped spec не изменились.
2. Сохраняет **четыре приватных JSON** в уже существующую
   закрытую папку Drive, с точной проверкой SHA256/MD5
   после чтения:
   `materials`, `proposals`, `selection-v2`,
   `video-spec`. Никакие MP4 не переносятся в GitHub.
3. `motionlab_v2_stage_writeback.build_candidate_v2`
   записывает лишь asset `edit_plan` и
   `stage_handoffs.edit_choice=approved`, включая SHA
   четырех приватных источников; проверяет действительный
   `handoff.make_handoff → MONTAGE_RENDERER`.
4. Только фактически успешный GitHub CAS `project.json`
   отмечает статус `APPLIED`. Любая неясная ошибка —
   `BLOCKED`, без повторной отправки TTS/A2E/публикации.

**`ACK ≠ APPLIED ≠ SPEC_READY ≠ MP4_QA_PASS`.**
При успешной записи spec в приватный Drive пользователь
утвердил монтаж, но **полный фильм еще НЕ создавался**;
проверка повторного использования утвержденного WAV, реальных
offer/end таймингов и QA по-прежнему отдельная стадия.

### Текущее ограничение интерфейса и типографики

На Wix уже работают отдельные страницы сцены/стыка,
ручное размещение текста и экспорт черновика v2. В нем
появились также `global_theme` и per-scene font/color
исключения. **v2 receiver принимает только строго определенные** `global_theme.typography`,
`scene_typography` и `scene_layout`, с неизменными asset/scene ID.
Неизвестные поля price/end-layout блокируются. Без заранее установленных
шрифтов Unbounded/Manrope v2 UI блокирует утверждение; доступные системные
Georgia/Arial используются как начальные настройки. Это не доказывает
попиксельного соответствия браузерного preview и итогового MP4.

В новом файле `motionlab_v2_ui.js` теперь реализованы
`SIMBA_MOTIONLAB_V2_READY` и `SIMBA_MOTIONLAB_V2_SELECTION`.
Подтверждение разрешено лишь после проверки локально загруженных MP4
по SHA-256 и длительности, а `ACK` ставится только после серверного
SQLite COMMIT. Модуль добавлен в 22-файловый allowlist статического
пакета. **Ветку не развертывали в Wix и не выполняли настоящий E2E**;
состояние production остается неизменным.

### Статус по проверкам

- `test_motionlab_v2_live_receiver.py`:
  authenticated owner-only двухфазная сессия, настоящий
  SQLite receipt, private spec snapshot, SHA MP4 source,
  WYSIWYG, отказ при stale/draft/подмене, mock Drive
  четыре файла и GitHub CAS; никаких реальных клиентских
  секретов.
- `repo-tests/test_motionlab_v2_live_host.mjs`:
  origin+source v2 postMessage, отсутствие v1 fallback,
  отрицательный ACK при сбоях, проверка persisted
  до ответа.
- CI бесплатно; TTS/A2E/публикация не вызываются.
- Реальный внешний HTTPS deployment, автоматическая
  передача реальных MP4 в соседний ChatGPT, live Wix
  v2 connected integration, **реальный client video render**
  пока не выполнены.

