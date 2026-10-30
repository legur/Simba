# Zernio: утверждённый пакет → проверенный черновик

Версия 2.0 · 30.10.2026. Требуется Python 3.10+ и существующий авторизованный
`@zernio/cli`. Новые платные сервисы, подписки и зависимости не подключаются.
Используется существующий аккаунт; лимиты и тарификация загрузок определяются им.

## GROK_ADS_MODE — 30.10.2026
Режим существующего Simba по прямому решению Leo. Полный канонический контракт: `Симба (Писатель)/Simba-v5.0.md`, раздел с идентификатором GROK_ADS_MODE. Только рекламные задания от Грока, принятые явно от Leo или через отдельно настроенный им канал. Один пост вместо трех; после обычного KB/TIA/факт-контроля, Internal Critic и Humanizer — POLICY_AUTHORIZED_FOR_PUBLICATION и публикация только в Facebook Simba World Travel. PROCESS_OWNER выполняет lookup страницы, журнал/dedupe, публикацию, readback и write-back. Нерекламное задание — BLOCKED_SCOPE без публикации через другой модуль.
В этом режиме прямое разрешение Leo заменяет выбор текста и отдельную команду «публикуй» для каждого ID; текстовый пост по умолчанию без обязательного Rafael-trigger. Новый визуал при явном запросе сохраняет процесс Rafael. Эти исключения имеют приоритет над общими approval/draft-only/default-page формулировками данного файла только в названном scope. Ограничения инструментов/среды не отменяются: требование подтверждения exact text конкретного publisher означает BLOCKED_PUBLISH_APPROVAL_REQUIRED до его выполнения. zernio.py остается draft-only. Режим не создает канал приема Grok, расписание или работающую интеграцию; их готовность и remote smoke не подтверждены. Обычный AUTOMATION_CONTINUOUS_MODE не получает права публикации.

## Место в процессе

PROCESS_OWNER проверяет реальные согласования в истории: APPROVED_TEXT,
отдельный финальный render Rafael с QA, FINAL_VISUAL_READY и PUBLICATION_PACKAGE_READY.
Поля JSON — утверждения вызывающего процесса, не электронная подпись Leo.
Preview и POLICY_APPROVED_FOR_VISUAL не подходят. Утверждение текста/картинки
не разрешает публикацию. Сохранять content дословно, без служебного текста архива.

Перед отправкой явно выбрать `Leo's Travel Tips` или `Simba World Travel`.
Если Leo страницу не назвал, спросить: «На какую страницу сохранить черновик:
Leo's Travel Tips или Simba World Travel?» Не выбирать по типу автора или прошлому
посту. Выбор разрешает работу только с названной страницей.

## Команды

Из корня Simba, проверка существующей авторизации (только чтение):

```powershell
python integrations/ai_plugins/zernio.py doctor
```

CLI автоматически находится в PATH или установленном npm-cache Windows, без npx
и скачивания обновлений. При необходимости `SIMBA_ZERNIO_CLI_JS` указывает путь
к установленному `@zernio/cli/dist/index.js` (это путь, не ключ). На Windows
запуск через node без cmd.exe сохраняет кавычки и спецсимволы текста.
Конфигурацию и ключи читает только сам CLI. Адаптер не копирует их и не выводит
сырой stderr/ответы авторизации. `doctor` выводит только ID, имя, платформу и активность.

Подготовить UTF-8 JSON рядом с финальной картинкой, например `approved-package.json`:

```json
{
  "packageId": "content-library-record-unique-revision",
  "content": "Дословный утверждённый текст",
  "image": "final.png",
  "textStatus": "APPROVED_TEXT",
  "visualStatus": "FINAL_VISUAL_READY",
  "status": "PUBLICATION_PACKAGE_READY"
}
```

Проверить локально; без `--send` внешних запросов и загрузок нет:

```powershell
python integrations/ai_plugins/zernio.py draft approved-package.json --page "Leo's Travel Tips"
```

По команде сохранить черновик добавить `--send`:

```powershell
python integrations/ai_plugins/zernio.py draft approved-package.json --page "Leo's Travel Tips" --send
```

Выполняется accounts:list → точное уникальное имя активной Facebook-страницы →
поиск существующего поста во всех страницах списка и статусах → media:upload →
posts:create **с обязательным --draft** → posts:get. Успех только после сверки
ID, accountId/страницы, точного content, единственного image URL и статуса draft.
Вывод: `DRAFT_VERIFIED`, `id`, `page`, `accountId`, `content`, `mediaItems`, `remoteStatus`.
При mismatch — BLOCKED; не переписывать удалённый пост автоматически.

## Повторы и сбои

Метка `simbaDraftKey` связывает packageId и страницу; `simbaFingerprint` — точный
текст и SHA-256 картинки. Remote metadata также содержит имя страницы. Повтор
пакета перечитывает прежний ID. То же содержимое под другим packageId ищется по
fingerprint и странице. Изменение пакета требует нового approval и нового packageId.
Уже scheduled/published пост не пересоздаётся. Удалённый пост с известным ID не
пересоздаётся. Несколько remote matches блокируют запись.

Локальный `.zernio-state/` исключён из Git: блокировки package и fingerprint/page,
атомарный журнал намерения
пишутся до загрузки. После неизвестного результата сначала remote reconciliation.
Если совпадения нет, повторная запись блокируется (`OUTCOME_UNKNOWN`); не удалять
журнал/lock автоматически, сверить кабинет и историю завершения процесса.
Сбой загрузки может оставить медиа без поста; автоматическая повторная загрузка запрещена.
Однозначные структурированные HTTP-отказы 400/401/403/404/413/415/422/429
показывают только безопасный числовой status. Они не создают пост: журнал попытки
снимается, после исправления причины допустим новый запуск с повторным lookup.
409, 5xx, timeout и неструктурированные ошибки остаются UNKNOWN.

CLI 0.4.1 не предоставляет флаг Idempotency-Key. Поэтому защита рассчитана на один
последовательно работающий Simba checkout. Одновременная отправка из разных машин
не имеет серверной атомарной гарантии; использовать один исполнитель/общий журнал.
Не объявлять remote exactly-once. Изменённая/удалённая вручную metadata требует сверки.
Перед загрузкой используется временная копия картинки с проверенным hash, чтобы
замена файла во время передачи не подменила утверждённый визуал. В readback также
блокируются platform customContent/customMedia/scheduledFor/platformSpecificData
и уже опубликованные platform targets: сверяется фактический payload Facebook.

## Публикация и расписание — отдельная явная команда

Адаптер намеренно не содержит publish/schedule и не вызывает posts:update.
Для команды Leo «опубликуй черновик ID» или «запланируй черновик ID на время»:
сначала posts:get ID, сверка страницы/текста/медиа и актуального разрешения именно
для этого ID. Для расписания обязательны дата, время и часовой пояс; при пробеле уточнить.
Только затем через существующий CLI выполнить posts:update того же ID. Обязательно
передать `--draft=false`: без isDraft=false обновление сохраняет прежний draft-статус.
Аргументы отдельного разрешённого действия (не команды адаптера и не разрешение
выполнить их во время проверки интеграции):

```text
posts:update ID --publishNow --draft=false
posts:update ID --scheduledAt ISO-8601 --timezone IANA_ZONE --draft=false
```

Для запуска использовать тот же существующий CLI, который находит `cli_command()`
в `zernio.py`. На этой Windows-машине команда zernio отсутствует в PATH, поэтому
это префикс `node.exe` + найденный `@zernio/cli/dist/index.js`, без npx/установки/login.
Исполнитель передаёт аргументы массивом через subprocess с shell=False и
capture_output=True; сырой stdout/stderr не показывать. Для pre-read и post-read
применим разрешённый `posts:get ID`, выводить только ID, страницу, текст, медиа и статус.
Новый posts:create запрещён. После операции снова posts:get:
scheduled не равен published; промежуточный/ошибочный статус не считать публикацией.
Никакое поле пакета, approval или команда сохранить draft не заменяет эту команду Leo.

Уточнение 1.1: явный выход из draft и запуск найденного CLI описаны по фактическому
контракту posts:update; публикация и расписание в этой проверке не выполнялись.

## Проверки

```powershell
python -m unittest discover -s integrations/ai_plugins -p 'test_*.py' -v
```

Offline-подмены проверяют запись/повторы/readback/сбои, но не доказывают remote
создание. Реальный smoke выполняется только с готовым пакетом и выбранной страницей.
Официальные контракты: [CLI](https://docs.zernio.com/cli),
[posting](https://docs.zernio.com/cli/posting),
[исходник CLI](https://github.com/zernio-dev/zernio-cli).

### 2.0 — 30.10.2026
Структурное изменение по прямой команде Leo: синхронизирован GROK_ADS_MODE Simba 8.0, один рекламный пост и scoped разрешение публикации в Simba World Travel. Факты/KB/TIA/Internal Critic/Humanizer и требования инструментов сохранены; прием Grok и live publisher не объявлены подключенными. Обычный режим не изменен.
