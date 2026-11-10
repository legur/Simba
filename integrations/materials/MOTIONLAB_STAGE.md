# Simba Motion Lab PR №112 → Киностудия, этап 5G (edit_choice)

Версия 10.11.2026. Статус: **код принятия выбора готов; production host/ACK не подключен**.
PR №105 синхронизирован с объединенным в main PR №112.

## Сверка с чатом Studio — обязательное уточнение (10.11.2026)

**Общий контракт:** `SIMBA KNOWLEDGE BASE/06_AGENT_WORKFLOWS/STUDIO_MOTIONLAB_SYNC.md` в `main`.
Studio — **редактор подготовки монтажа**; вход: **уже готовые изображения
или ролики 5–15 с**, A2E — **необязательный** источник. Существующий
Монтажер Клод собирает и проверяет финальный MP4. Настройки выбирает
Leo, они должны вернуться в автоматическую среду; вторую систему
платной генерации/рендера делать нельзя.

**Важный статус реализации:** текущий `build_launch` и
`motionlab_stage_writeback` ниже работают **только** при
`voice_music` и `a2e_clips` с исходными `animated_clip` MP4.
Иными словами, реализован маршрут `A2E_MEDIA`. В
`README` студийного модуля и чате Studio уже согласован
`READY_MEDIA` (изображения и готовые видео 5–15 с), но
`handoff.py` пока принудительно проходит
`a2e_prompts → a2e_clips`: обходить это фиктивными approvals нельзя.
Нужны отдельный optional-source путь и совместимые тесты,
до их появления **не объявлять весь Studio-flow завершенным**.

**Открытые блокеры:** live authenticated browser host
`SELECTION → durable-save → ACK`, настоящий предпросмотр
разрешенных пользовательских исходников и Wix deploy 403.
Это ограничения исполнения, не повод создавать дубликаты
редактора, генератора или монтажера.

## Источники истины

- Сайт/редактор: \`integrations/materials/motionlab/storyboard.js\`, редактор
  на существующем Wix Headless \`siteId=795efbc2-50c4-435e-939e-537cb2df75c7\`.
- Контракт без побочных эффектов:
  \`integrations/materials/motionlab/motionlab_selection.py:validate\`.
- Уже работающий протокол браузера:
  \`SIMBA_MOTIONLAB_READY → START → SELECTION → ACK\` и
  \`motionlab_host_adapter.js\`. **Нельзя отправлять ACK, пока долговечная
  запись не завершилась.** Этот репозиторий **не** является запущенным
  сервером приема браузерного \`postMessage\`.
- Новый серверный этап:
  \`integrations/materials/motionlab_stage_writeback.py\` для двух
  зафиксированных SHA-256 приватных JSON и текущего
  \`stage_handoffs.voice_music=completed\`.
- Owner-only ручной workflow:
  \`.github/workflows/simba-motionlab-stage-writeback.yml\` — проверяет
  файлы в частном Google Drive и коммитит единственный
  \`campaigns/<project>/project.json\`. **Адаптер не рендерит, не
  генерирует речь и не публикует.**

## Старт задания

\`build_launch(root, project_id, options, request_id)\` строит
\`bontours.motionlab.storyboard.launch/v1\` исключительно из текущих
канонических \`animated_clip\` assets, подтвержденных этапом \`a2e_clips\`
и еще действующего receipt после \`voice_music\`.

\`options\` — **ровно три действительно подготовленных аген­том варианта**
(нельзя заменять пустыми шаблонами/автовыбором), каждый со
\`name\`, \`description\` и \`settings\`:
\`camera\`, \`transition\`, \`titleFx\`,
\`subtitleStyle\`, \`wordMotion\`, \`intensity\`.
ID значений соответствуют **существующим** Motion Lab и
\`motionlab_selection.py\`; заготовки из PR №112 могут служить исходными
предложениями после проверки настоящих кадров.

Результат содержит:
- \`request_id\`, \`project_id\`,
  \`expected_input_fingerprint\` из текущего
  \`handoff.make_handoff(...).packet.receipt_sha256\`;
- три разных \`options\`;
- \`scenes[]\`, где \`scene_id\` стабилен, а \`asset_id\` обязательно
  указывает на **конкретный** оригинальный подтвержденный A2E MP4;
- длительность каждого клипа соответствует фактически проверенной
  продолжительности в проекте (не выдумывать запас кадров).

**В публичный Motion Lab не передаются приватные ссылки Google Drive.**
Пока не готова авторизованная раздача превью, редактор покажет
демонстрационный фон. Это не замена оригинального MP4 в задании.
Хосту запрещено выставлять ненастоящий URL из непубличного Drive.

## Что делает браузер, а что не делает

При настоящем подключении приложения-хоста \`motionlab_host_adapter.js\`
передает \`SIMBA_MOTIONLAB_START\`; редактор предлагает три варианта и
собирает решения по сценам. После выбора отправляет
\`SIMBA_MOTIONLAB_SELECTION\`, содержащий
\`decision.state=USER_SELECTED_IN_CONNECTED_SESSION\`,
\`provenance.mode=embedded-bridge\` и защитные флаги
\`run_render/run_tts/run_a2e/run_paid_operations/auto_publish=false\`.

Проверка \`motionlab_selection.validate(launch, selection)\` необходима,
но недостаточна: backend должен привязать оба сообщения к **текущему**
проекту, выбранным A2E активам, свежему receipt, фактическому
пользовательскому выбору и owner-authenticated write-back.
\`DRAFT_NOT_DELIVERED\` из автономного JSON-экспорта
**не может** быть повышен до утверждения подменой поля.

**ACK:** только после фактического безопасного сохранения
исходного launch, selected JSON и источника разрешения в
защищенном серверном хранилище. Для утверждения
\`stage_handoffs.edit_choice\` нужен затем успешный stage
write-back в GitHub. Пока постоянный хост-приемник не подключен,
браузерного ACK и полностью автоматического save/route нет.
Это блокер, а не фиктивно завершенный шаг.

## Реальный приватный этап write-back

Два фактических JSON загружаются под owner-only доступом в
\`Simba Private AI Drafts\`. Имя не критично; важны точные
\`file_id\`, \`sha256\` полных байтов. Owner \`legur\` может запустить
после существования выбранного материала
\`simba-motionlab-stage-writeback.yml\` на \`main\`, параметры:
\`project_id\`, \`launch_file_id\`, \`launch_sha256\`,
\`selection_file_id\`, \`selection_sha256\`.

Write-back **до изменения GitHub** проверяет:
1. \`handoff.make_handoff\` = \`READY_FOR_HANDOFF → MONTAGE/edit_choice\`,
   полный прежний \`voice_music\` и исходный SHA receipt;
2. приватные Google Drive parent/permissions, размер, MD5/SHA-256
   реальных байтов двух разных JSON;
3. существующий выбор из 3 реально различных вариантов;
4. действительные ID и SHA каждого \`animated_clip\`, сцены
   без подмены/дублирования/удаления, длительность ≤ исходного
   MP4, общая длительность ≤ 60 сек.;
5. **старый** \`motionlab_selection.validate\` и дополнительные
   provenance guards, выбор 1–3, дату и отсутствие разрешения
   на платные вызовы или автоматическую публикацию;
6. отсутствие предыдущего \`edit_choice\` и сохранение ранее
   утвержденных голоса, музыки, текста, \`approvals\` и
   \`approved_asset_id\`.

Только затем добавляет **один** \`kind=edit_plan\` asset
(приватный URL Google Drive, точный SHA-256 и source launch SHA)
и \`stage_handoffs.edit_choice=approved\` с
\`options_presented=3\`, \`selected_option\`,
\`options_evidence\`, \`approval_evidence\` и
\`motionlab_receipt_id\`.
Делает повторный \`handoff.make_handoff\`: строго
\`READY_FOR_HANDOFF → MONTAGE_RENDERER/render\`.
На owner-only \`--apply\` CAS-обновляет только
\`project.json\`. Git push запускает **существующий**
\`simba-video-stage-dispatch.yml\`, который создаст
задачу для \`MONTAGE_RENDERER\`, **не выполнит** сам рендер.

Этот выбор — режиссерская подготовка; исполнение требует
фактически существующих MP4, утвержденных аудио,
технического монтажа и последующего полного VIDEO_QA.
До final Leo approval никакой публикации нет.

## Проверка

\`\`\`bash
python -m unittest discover -s integrations/materials/motionlab/repo-tests -p test_motionlab_selection.py -v
python -m unittest discover -s integrations/materials -p test_motionlab_stage_writeback.py -v
\`\`\`

Тесты используют fake Drive и настоящий бинарный JSON с MD5/SHA-256,
но не реальные клипы, live-host или отправленный из браузера выбор.
Контроль: отказ от draft, неверного source, чужого media,
измененного выбора, превышения длительности, shared folder,
повтора и неразрешенной записи. CI: безопасный
\`simba-motionlab-stage-writeback.yml\` на PR.

**Текущие практические ограничения:** Wix Headless deploy из CI
временно приостановлен из-за \`403 VELO.APP_PROJECT_READ\`,
поэтому обновление статических веб-файлов в main не означает
публикацию сайта. В PR №105 веб-файлы не изменяются и не
пытаются обходить ограничения Wix.
