# GameAssets/Chapter2 — «Горы» (из env_ch2/v7.1)

Источник арта: `/workspace/walking-sim/env_ch2/v7/` (v7.1: горы +30%, без cloud_thin).

## Структура (как Chapter1)
- `places/bg_far_ridges_tile.png`, `bg_mid_fields_tile.png` — тайлы Н/С (размер как у гл.1, чтобы global `layers.pixelSize` в world.json совпадал)
- `places/place_*_main.png` — Седло / Хомут / Репка / Горловина
- `places/el_*` — дерево-письма, столб, рупор-цветы, столик
- `underground/ug_*` — модули разреза с согласованными краями + `ug_neutral_tile` из ground_master v7 (НЕ нейтраль гл.1)
- `_preview/` — phone/strip для глаз, в рантайме не читается кодом

## world.json
Глава 2 = `chapters[1]` (startStep 20000, lengthSteps 25000). Все главы — сегменты одной `WorldScene`: глобальные координаты `startStep + localStep`, общая камера/герой, без замены сцены на границе. Сюжетный движок и HUD получают локальные шаги активной главы. Правило применяется к любому числу `world.chapters`, не только 1+2.


## Исправление форса и окружения

- DEBUG-форс записывает `forceChapterBaseSteps = totalSteps`, но не добавляет шаги.
  Локальный прогресс = `clamp(totalSteps - base, 0...lengthSteps)`.
- Сброс форса убирает обе настройки. «Сбросить историю» также очищает состояния всех
  глав и явно возвращает активную главу/камеру в начало Долины.
- `places/bg_far_ridges_tile.png` и `bg_mid_fields_tile.png` заново собраны из
  `/workspace/walking-sim/env_ch2/v7/layer_far.png` / `layer_mid.png`.
  Прозрачная верхняя пустота убрана из расположения гор; пропорции силуэтов сохранены.
  Итог 2636×1236 / 2636×1040 совпадает с глобальными `pixelSize`: `world.json`,
  far/mid height/top и все ассеты Chapter1 не менялись.
- В разрезе всегда есть нейтральная подложка под асинхронно загружаемыми модулями.
  Все края модулей совпадают с новым нейтральным грунтом. `underground.top = 1700`
  уже на 20 px выше roadLineY=1720: геометрической щели не было, его не двигали.
- При сильном отзуме ниже разреза остаётся однотонная глубокая земля, не текстурный
  слой. Это арт-долг, а не отсутствие/застывший параллакс верхнего разреза.

Воспроизведение арта:

```sh
python3 tools/rebuild_ch2_environment.py --source /workspace/walking-sim/env_ch2/v7
# Для повторной обработки краёв: --module-source <папка ОРИГИНАЛЬНЫХ модулей>
# На box оригиналы сохранены в:
# /workspace/postman_ios_ch2_fix_backup/Postman/GameAssets/Chapter2/underground
```

Проверка на box (арифметика из Swift + контракты исходников + PNG; не iOS runtime):

```sh
python3 tools/check_chapter_progress.py
```
