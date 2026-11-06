# App Privacy labels — «Тишина. Последний почтальон»
App Store Connect → App → App Privacy → Get Started / Edit.

API не умеет (404 на appDataUsages) — только вручную в веб-UI. Review не отправлять.

## Ответы (по коду игры)

**Data Collection: Yes** (на устройстве читаются Health + Location; даже если не уходит на сервер, Apple часто требует указать типы, которые приложение запрашивает).

Если мастер спросит «Does this app collect data?» — ставим **Yes**, затем:

### 1) Health & Fitness → Fitness / Health (Steps)
- Type: **Health** / **Fitness** (шаги / step count)
- Linked to user: **No** (нет аккаунта)
- Used for tracking: **No**
- Purpose: **App Functionality** (почтальон идёт по шагам)
- Collected from: on device / HealthKit read-only
- Not used for advertising, not sold

### 2) Location → Coarse Location
- Type: **Coarse Location**
- Linked to user: **No**
- Used for tracking: **No**
- Purpose: **App Functionality** (погода в Долине)
- Optional; reduced accuracy; not stored/sent to developer servers

### Не добавлять
- Contact Info, Identifiers, Usage Data, Diagnostics, Purchases, Sensitive Info — игра этого не собирает.
- Precise Location — нет (только coarse / reduced).
- Health write — нет.

### Product Page URL
После включения GitHub Pages:
- Privacy: `https://pomazkoff.github.io/POSTAL/privacy.html`
- Support: `https://pomazkoff.github.io/POSTAL/support.html`

### Включить Pages (один раз)
GitHub → `pomazkoff/POSTAL` → Settings → Pages → Build from branch: **main**, folder: **/docs** → Save.
