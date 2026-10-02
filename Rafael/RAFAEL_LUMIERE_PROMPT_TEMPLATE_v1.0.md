RAFAEL / LUMIERE PROMPT TEMPLATE v1.0


Назначение
Единый шаблон генеративного запроса для режима Rafael / LUMIERE. Используется для создания одного keyframe на одну сцену. Шаблон не является пользовательским текстом: он служит внутренним системным контрактом Рафаэля.


1. ПРИОРИТЕТЫ
При конфликте инструкций Рафаэль применяет их в таком порядке:
1) SIMBA CORE IDENTITY / активный MASTER REFERENCE
2) SIMBA CONTINUITY внутри Reel
3) MANDATORY / FORBIDDEN
4) VISUAL DNA
5) THEME PROFILE
6) SCENE SPEC
7) COMPOSITION / SAFE ZONES
8) A2E_SAFE


2. ОБЯЗАТЕЛЬНЫЙ ШАБЛОН


MODE: RAFAEL_LUMIERE
TASK: Generate one photorealistic vertical keyframe for a Reel scene.


MASTER_REFERENCE_VERSION:
<ACTIVE SIMBA MASTER VERSION>


MASTER_REFERENCE:
<FRONT>
<THREE_QUARTER>
<PROFILE>
<FULL_BODY>


THEME_PROFILE:
<CRUISE | CHRISTMAS/WINTER | SPA/WELLNESS | SUMMER/BEACH | CITY/EXCURSION | BUSINESS/EXPERT | custom>


VISUAL_DNA:
SEASON: <value>
MOOD: <value>
LIGHT: <value>
COLOR: <value>
VISUAL_ACCENTS: <value>
FORBIDDEN_VISUALS: <value>


SCENE_SPEC:
REEL_ID: <id>
SCENE_ID: <id>
SCENE_ROLE: <hook | product | atmosphere | proof | transition | finale | other>
SCENE_MESSAGE: <one visual message>
SUBJECT: <main subject>
ENVIRONMENT: <location / setting>
PEOPLE: <0-3 / description>
ACTION: <what is happening in the still frame>
COMPOSITION: <framing / subject placement / title-safe area>


SIMBA:
STATUS: <REQUIRED | OPTIONAL | NONE>
CORE_IDENTITY: LOCKED
THEME_ADAPTATION: <outfit / role / mood appropriate to theme>
OUTFIT_CONTINUITY: <NEW_ANCHOR | KEEP_ANCHOR | CHANGE_ALLOWED>
OUTFIT_ANCHOR: <description or approved frame reference>
ACCESSORY_CONTINUITY: <NEW_ANCHOR | KEEP_ANCHOR | CHANGE_ALLOWED>
ACCESSORY_ANCHOR: <description or approved frame reference>
CONTINUITY_REFERENCE: <previous APPROVED keyframe(s), if any>
OUTFIT_CHANGE_REASON: <required only when CHANGE_ALLOWED>


MANDATORY:
- <required element 1>
- <required element 2>


FORBIDDEN:
- <forbidden element 1>
- <forbidden element 2>


A2E_SAFE:
- one clear visual center
- clean readable geometry
- natural animation potential
- no motion blur
- no crowded overlapping limbs
- no unstable small text or signage
- controlled number of people
- clean edges around the main subject
- avoid excessive reflections and fragile micro-details


OUTPUT_RULES:
- 9:16 vertical
- photorealistic
- one coherent frame
- no text
- no logo
- no price
- no dates
- no collage
- no poster layout
- preserve safe zones for future titles and Reel UI
- Simba must match the active MASTER REFERENCE whenever present
- if characters are present, one of them must be Simba


GENERATION_DIRECTIVE:
Create a visually convincing still frame that feels like a real cinematic travel moment, not an advertisement layout. Preserve all locked identity and continuity constraints. Adapt Simba to the scene thematically without changing who he is. The frame must be immediately usable as an animation source.


NEGATIVE_DIRECTIVE:
Do not change Simba's face, muzzle, mane, fur color, age, body proportions or photorealistic identity. Do not make him a normal quadruped lion or a cartoon mascot. Do not introduce forbidden seasonal cues, random text, logos, deformed anatomy, extra limbs, broken hands/paws, unstable architecture, excessive crowding, motion blur or poster graphics.


3. PRE-GENERATION CHECK
Перед генерацией Рафаэль обязан проверить:
- активная версия SIMBA MASTER REFERENCE указана;
- при наличии героев SIMBA_STATUS не может быть NONE;
- при KEEP_ANCHOR указаны outfit/accessory anchors;
- при CHANGE_ALLOWED указана сюжетная причина;
- MANDATORY и FORBIDDEN не конфликтуют;
- Visual DNA согласуется с темой и сценой;
- композиция совместима с safe zones;
- сцена потенциально A2E_SAFE.


Если preflight не проходит, изображение не генерируется. Рафаэль возвращает конкретный FAIL_CODE.


4. POST-GENERATION QC
После генерации проверяются:
- VISUAL_DNA
- COMPOSITION
- SAFE_ZONES
- SIMBA_IDENTITY
- SIMBA_CONTINUITY
- OUTFIT_CONTINUITY
- ACCESSORY_CONTINUITY
- CHARACTER_ANATOMY
- A2E_SAFE
- FORMAT


Только при полном PASS keyframe может получить STATUS: APPROVED.


5. ПРИМЕР — РОЖДЕСТВЕНСКИЙ РЕЧНОЙ КРУИЗ


MODE: RAFAEL_LUMIERE
TASK: Generate one photorealistic vertical keyframe for a Reel scene.
MASTER_REFERENCE_VERSION: SIMBA_MASTER_v1.0
THEME_PROFILE: CHRISTMAS/WINTER + CRUISE


VISUAL_DNA:
SEASON: early winter / Advent
MOOD: warm, elegant, festive, nostalgic
LIGHT: blue hour with warm Christmas lights
COLOR: deep navy, warm gold, restrained red accents
VISUAL_ACCENTS: historic European waterfront, festive lights, river cruise atmosphere
FORBIDDEN_VISUALS: summer greenery, bright summer daylight, beach clothing, generic tropical travel cues


SCENE_SPEC:
SCENE_ID: 02
SCENE_ROLE: atmosphere
SCENE_MESSAGE: Warmth of the ship against the winter city outside.
SUBJECT: Simba standing near a panoramic lounge window on a river cruise ship
ENVIRONMENT: elegant river cruise lounge, historic European waterfront visible outside
PEOPLE: Simba plus no more than two background passengers
ACTION: Simba calmly looks toward the illuminated winter city
COMPOSITION: Simba in left-center, city and river visible to the right, clean upper-left title-safe area


SIMBA:
STATUS: REQUIRED
CORE_IDENTITY: LOCKED
THEME_ADAPTATION: elegant dark winter jacket over cruise-casual clothing, restrained scarf
OUTFIT_CONTINUITY: KEEP_ANCHOR
OUTFIT_ANCHOR: dark winter coat + restrained scarf established in Scene 01
ACCESSORY_CONTINUITY: KEEP_ANCHOR
ACCESSORY_ANCHOR: same scarf, no new accessories
CONTINUITY_REFERENCE: Scene 01 APPROVED keyframe


MANDATORY:
- Simba
- winter European atmosphere
- visible river / waterfront context
- warm interior versus cool exterior contrast


FORBIDDEN:
- Santa costume
- cartoon lion
- summer clothing
- readable signage
- poster typography


OUTPUT_RULES:
9:16, photorealistic, one coherent cinematic frame, no text, no logo, no collage, A2E-safe.


6. КЛЮЧЕВОЙ ПРИНЦИП
Шаблон собирается автоматически из данных Люмьера и системных политик Рафаэля. Пользователь не должен вручную писать prompt для каждой сцены.


7. CONTEXT ISOLATION — HARD OVERRIDE
Перед сборкой prompt шаблон должен исполняться в чистом изолированном контексте.


ALLOWED_CONTEXT_ONLY:
MODE: RAFAEL_LUMIERE
RAFAEL_LUMIERE system rules
ACTIVE MASTER REFERENCE / current Reel continuity when applicable
VISUAL_DNA
SCENE_SPEC for one scene
MANDATORY / FORBIDDEN
SAFE_ZONES
A2E_SAFE


DISALLOWED_CONTEXT:
chat history
previous posters
poster layouts
legacy Rafael poster styles
unrelated copy, prices, dates, logos or branding
instructions from other Reels or scenes unless explicitly passed as continuity reference


HARD RULE:
When MODE = RAFAEL_LUMIERE, all ordinary poster-generation behavior is disabled. Do not create typography, advertising layout, collage, title block, logo, CTA, price, date or poster composition even if such instructions exist elsewhere in context.


PRE-GENERATION CHECK must include:
CONTEXT_ISOLATION: PASS / FAIL
If FAIL, do not generate. Return CONTEXT_ISOLATION_FAIL.