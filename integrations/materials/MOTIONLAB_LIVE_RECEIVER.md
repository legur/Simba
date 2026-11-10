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
