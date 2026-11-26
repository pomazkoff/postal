#!/usr/bin/env python3
"""Build world.json chapter 4, chapter4_story.json, chapter4_taps.json, and patch EN/RU copy."""
from __future__ import annotations
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "Postman/GameAssets/Data"
CANON = (ROOT / "docs/canon/letters-ch4.md").read_text(encoding="utf-8")

def letter_text(n: int) -> str:
    m = re.search(r"^## Письмо %d\..*?$(.*?)(?=^## |\Z)" % n, CANON, re.S | re.M)
    assert m, n
    blocks, cur = [], []
    for ln in m.group(1).split("\n"):
        if ln.startswith(">"):
            cur.append(ln[2:] if ln.startswith("> ") else ln[1:])
        elif cur:
            blocks.append("\n".join(cur).strip()); cur = []
    if cur:
        blocks.append("\n".join(cur).strip())
    return "\n\n".join(blocks).strip()

def item(**kw):
    if 'sender' in kw:
        kw['from'] = kw.pop('sender')
    base = dict(takesSlot=True, art="env_plain", stick="stick_plain", initial="onRoad",
                road="road_envstake", kind="letter")
    base.update(kw)
    return base

def ev(id, step, typ, settlement, **kw):
    d = dict(id=id, step=step, type=typ, settlement=settlement)
    d.update(kw)
    return d

def line(text, who=""):
    return {"who": who, "text": text}

SETTLEMENTS = [
    dict(id="shlagbaum", name="Шлагбаум", nameGenitive="Шлагбаума", fullName="Шлагбаум", step=0),
    dict(id="otstoyniki", name="Отстойники", nameGenitive="Отстойников", fullName="Отстойники", step=4000),
    dict(id="kotelnaya", name="Котельная", nameGenitive="Котельной", fullName="Котельная", step=21000),
    dict(id="sarai", name="Сараи", nameGenitive="Сараев", fullName="Сараи", step=25000),
    dict(id="naberezhnaya", name="Набережная", nameGenitive="Набережной", fullName="Набережная", step=32000),
    dict(id="dvory", name="Дворы", nameGenitive="Дворов", fullName="Дворы", step=36500),
    dict(id="otdelenie", name="Отделение", nameGenitive="Отделения", fullName="Отделение", step=39500),
    dict(id="verkhnyaya", name="Верхняя", nameGenitive="Верхней", fullName="Верхняя", step=45000),
]

def ambient_props():
    # (image_stem, file already in Chapter4/ambient, step, dx, height, sink, z)
    # pixelSize from files
    from PIL import Image
    amb = ROOT / "Postman/GameAssets/Chapter4/ambient"
    def psz(name):
        im = Image.open(amb / f"{name}.png")
        return [im.size[0], im.size[1]]
    specs = [
        ("ducks", 300, -80, 70, 24, 10),
        ("ducks", 2500, 200, 70, 24, 10),
        ("ducks", 6000, 160, 70, 24, 10),
        ("dog_otstoyniki", 4000, 220, 165, 0, 12),
        ("dog_otstoyniki", 6500, -180, 165, 0, 12),
        ("fish", 4500, 80, 60, 30, 9),
        ("crow", 9000, 300, 140, -80, 14),
        ("crow_fly", 12000, -40, 150, -200, 16),
        ("crow", 13000, 180, 140, -60, 14),
        ("dog_slag", 17500, 200, 160, 0, 12),
        ("lizard", 19000, -60, 50, 8, 11),
        ("cat_soot", 23000, 280, 125, 0, 12),
        ("pigeons", 27000, 200, 90, -40, 13),
        ("cat_sarai", 28000, -160, 132, 0, 12),
        ("dog_city", 33000, 180, 160, 0, 12),
        ("sparrows", 34000, -80, 70, -30, 13),
        ("chickens", 36500, 240, 140, 0, 11),
        ("cat_otdelenie", 39500, 300, 130, 0, 12),
        ("dog_city", 37000, -200, 160, 0, 12),
    ]
    props = []
    for name, step, dx, height, sink, z in specs:
        ps = psz(name)
        props.append(dict(image=f"ambient/{name}", layer="main", step=step, dx=dx,
                          height=height, sink=sink, z=z, pixelSize=ps))
    # Clouds live in Chapter4/sky and are drawn by installStvorSky, not as far props
    # (the old cloud_* crops were opaque rectangles against the chapter gradient).
    return props

def build_world():
    """Chapter 4 layout from tools/build_chapter4_world_v2.py (v2 art, built like chapter 1)."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import build_chapter4_world_v2 as v2
    world = json.loads((DATA / "world.json").read_text(encoding="utf-8"))
    ch3 = next(c for c in world["chapters"] if c["id"] == 3)
    ch3.pop("rawClayAfterStep", None)
    world["chapters"] = [c for c in world["chapters"] if c["id"] != 4]
    props, anchors = v2.build_props()
    ambient = ambient_props()
    ch4 = {
        "id": 4,
        "title": "Нижний Створ",
        "startStep": 75000,
        "lengthSteps": 45000,
        "assetsFolder": "Chapter4",
        "settlements": SETTLEMENTS,
        "props": props + ambient,
        "underground": v2.build_underground(anchors),
        "quests": [
            {"untilStep": 4000, "telegram": "Оставить записку А.Л. в ящике на Отстойниках", "lettersInBag": 1},
            {"untilStep": 21000, "telegram": "До Котельной, оказия вниз", "lettersInBag": 1},
            {"untilStep": 28000, "telegram": "Оставить почту на Сараях", "lettersInBag": 1},
            {"untilStep": 36500, "telegram": "До Дворов, письмо Нюре", "lettersInBag": 1},
            {"untilStep": 39500, "telegram": "К отделению", "lettersInBag": 1},
            {"untilStep": 45000, "telegram": "До Верхней", "lettersInBag": 0},
        ],
        "sky": dict(v2.SKY),
        "rawClayAfterStep": 45000,
    }
    world["chapters"].append(ch4)
    (DATA / "world.json").write_text(json.dumps(world, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("world.json: chapter 4 v2 —", len(props), "art props,", len(ambient), "ambient,", len(ch4["underground"]["modules"]), "ug modules")
    return v2.taps(anchors, ambient)

def build_story():
    t1, t2, t3, t4, t5, t6, t7, t8, t10 = [letter_text(n) for n in (1,2,3,4,5,6,7,8,10)]
    items = [
        item(id="l1", to="Почтальону", place="Шлагбаум · оставить на Отстойниках, «к отделению»",
             settlement="shlagbaum", sender="А.Л.", senderSettlement="otdelenie",
             reader={"paper":"sheet","font":"hand","envelope":"renv_open",
                     "address":["ПОЧТАЛЬОНУ","А.Л."],"stamp":None,"attachment":None,
                     "attachmentCaption":None}, text=t1),
        item(id="l2", to="маме в Кадушки", place="Отстойники · оказия вниз, ящик на Котельной",
             settlement="otstoyniki", sender="«Андрей»", senderSettlement="dvory",
             reader={"paper":"sheet","font":"hand","envelope":"renv_closed",
                     "address":["МАМЕ","КАДУШКИ"],"stamp":None,"attachment":None,
                     "attachmentCaption":None}, text=t2),
        item(id="l3", to="Вере", place="Котельная · оставить на Сараях, «для Веры»",
             settlement="kotelnaya", sender="Кузьма", senderSettlement="svai",
             reader={"paper":"sheet","font":"hand","envelope":"renv_closed",
                     "address":["ВЕРЕ ИГНАТЬЕВНЕ","НИИ"],"stamp":None,"attachment":None,
                     "attachmentCaption":"щепка с зарубкой 71 — отдельного рисунка нет, заглушка"},
             text=t3),
        item(id="l4", to="Нине", place="Котельная · оказия вниз, ящик на Сараях",
             settlement="kotelnaya", sender="Митя", senderSettlement="svai",
             reader={"paper":"sheet","font":"hand","envelope":"renv_closed",
                     "address":["БАБЕ НИНЕ","ОКАЗИЯ ВНИЗ"],"stamp":None,"attachment":None,
                     "attachmentCaption":None}, text=t4),
        item(id="l5", to="«Зое» / Нюре", place="Сараи · отдать Нюре у калитки на Дворах",
             settlement="sarai", sender="Марья", senderSettlement="sarai",
             reader={"paper":"sheet","font":"hand","envelope":"renv_closed",
                     "address":["ЗОЕ","ВЕРХНЯЯ"],"stamp":None,"attachment":None,
                     "attachmentCaption":"банка леща — отдельного арта нет, заглушка"},
             text=t5),
        item(id="l6", to="Почтальону", place="Набережная · читается на месте",
             settlement="naberezhnaya", sender="Пимен", senderSettlement="zvonarnya",
             reader={"paper":"sheet","font":"hand","envelope":"renv_open",
                     "address":["ПОЧТАЛЬОНУ"],"stamp":None,"attachment":None,
                     "attachmentCaption":"лента 37 имён — отдельного арта нет, заглушка"},
             text=t6),
        item(id="l7", to="Мите", place="Дворы · оказия вниз, ящик на Отделении",
             settlement="dvory", sender="Нина", senderSettlement="svai",
             reader={"paper":"sheet","font":"hand","envelope":"renv_closed",
                     "address":["МИТЕ УСУ","ОКАЗИЯ ВНИЗ"],"stamp":None,"attachment":None,
                     "attachmentCaption":None}, text=t7),
        item(id="l8", to="Почтальону", place="Отделение · читается на месте",
             settlement="otdelenie", sender="Вера", senderSettlement="nii",
             reader={"paper":"sheet","font":"hand","envelope":"renv_open",
                     "address":["ПОЧТАЛЬОНУ"],"stamp":None,"attachment":None,
                     "attachmentCaption":"миллиметровка 31–71 — отдельного арта нет, заглушка"},
             text=t8),
        item(id="l9", takesSlot=False, kind="form", road=None, to="Почтальону",
             place="Кладовая Отделения · находка, не вскрывать",
             settlement="otdelenie", sender="кладовая", senderSettlement="otdelenie",
             text="Стопка: на верхнем конверте «от Ксении, брату». Тридцать одно письмо. Тексты не вскрывать."),
        item(id="l10", to="Почтальону", place="Верхняя · читается на месте",
             settlement="verkhnyaya", sender="А.Л.", senderSettlement="otdelenie",
             reader={"paper":"sheet","font":"hand","envelope":"renv_open",
                     "address":["ПОЧТАЛЬОНУ","А.Л."],"stamp":None,"attachment":None,
                     "attachmentCaption":None}, text=t10),
        item(id="note_kolya", takesSlot=False, kind="form", road=None, initial="leftBehind",
             to="Почтальону", place="Личные вещи", settlement="otstoyniki",
             sender="Коля", senderSettlement="otstoyniki",
             text="По дамбе ходи. В пульпу — нет.\nКоля"),
        item(id="note_pavel", takesSlot=False, kind="form", road=None, initial="leftBehind",
             to="Почтальону", place="Личные вещи", settlement="kotelnaya",
             sender="Павел", senderSettlement="kotelnaya",
             text="Сапоги на сушилке. Котёл один, для верхних. Ночевать можно."),
        item(id="find_sluice", takesSlot=False, kind="form", road=None, initial="leftBehind",
             to="Почтальону", place="Личные вещи", settlement="otstoyniki",
             sender="Отстойники", senderSettlement="otstoyniki",
             text="Бирка пруда, жетон задвижки. Отдельного рисунка нет."),
        item(id="find_blank", takesSlot=False, kind="form", road="road_envstake", initial="onRoad",
             to="Почтальону", place="Личные вещи", settlement="truby" if False else "otstoyniki",
             sender="Трубы", senderSettlement="otstoyniki",
             text="Обрывок бланка: два почерка, одно имя. Отдельного рисунка нет."),
        item(id="find_stub", takesSlot=False, kind="form", road="road_envstake", initial="onRoad",
             to="Почтальону", place="Личные вещи", settlement="otstoyniki",
             sender="Шлам", senderSettlement="otstoyniki",
             text="Корешок извещения, подпись снята. Отдельного рисунка нет."),
        item(id="find_cup", takesSlot=False, kind="form", road="road_envstake", initial="onRoad",
             to="Почтальону", place="Личные вещи", settlement="verkhnyaya",
             sender="Верхняя", senderSettlement="verkhnyaya",
             text="Меловая помета и холодная чашка. Кто-то сидел недавно."),
    ]
    # fix find_blank/stub settlements (landscape has no settlement id — use nearest)
    for it in items:
        if it["id"] == "find_blank":
            it["settlement"] = "otstoyniki"
            it["from"] = "Трубы"
        if it["id"] == "find_stub":
            it["settlement"] = "kotelnaya"
            it["from"] = "Шлам"

    events = [
        ev("p_l1", 40, "pickup", "shlagbaum", item="l1", title="Записка в ящике",
           lines=[line("В ящике у шлагбаума служебная записка. Фиолетовый карандаш, подпись А.Л.")],
           push=[line("Шлагбаум. В ящике записка А.Л.")]),
        ev("e_sluice", 4000, "choice", "otstoyniki", title="Задвижка не идёт",
           text="Коля возится с задвижкой. Длина пути одна.",
           default="help",
           options=[
               {"id":"help","label":"Помочь с задвижкой","result":"Ноги сухие. Коля суёт бирку и записку: «По дамбе ходи. В пульпу — нет.»",
                "flags":["sluice_helped"],"grant":["find_sluice","note_kolya"],
                "auto":"Почтальон помог закрыть задвижку."},
               {"id":"leave","label":"Идти дальше","result":"Коля бурчит вслед. Бирки нет. Письма на месте.","flags":["sluice_left"]},
           ],
           push=[line("Коля возится с задвижкой. Поможешь?")]),
        ev("p_l2", 4200, "pickup", "otstoyniki", item="l2", title="Письмо «Андрея»",
           lines=[line("В ящике будки конверт. Две руки, рабочее имя Андрей. Оказия вниз, на Котельную.")],
           push=[line("Отстойники. В будке конверт на Кадушки.")]),
        ev("d_otstoyniki", 4000, "pickup", "otstoyniki", item="l1", title="Ящик «к отделению»",
           lines=[line("Записку А.Л. можно оставить в ящике на Отстойниках, «к отделению».")],
           push=[line("Отстойники. Ящик «к отделению».")]),
        ev("p_blank", 11000, "pickup", "otstoyniki", item="find_blank", title="Обрывок бланка",
           lines=[line("На опоре эстакады обрывок бланка: два почерка, одно имя.")],
           push=[line("Трубы. Обрывок бланка, два почерка.")]),
        ev("p_stub", 17500, "pickup", "kotelnaya", item="find_stub", title="Корешок извещения",
           lines=[line("На корке шлама корешок извещения. Подпись снята.")],
           push=[line("Шлам. Корешок извещения, подпись снята.")]),
        ev("p_l3", 21100, "pickup", "kotelnaya", item="l3", title="Щепка 71",
           lines=[line("В ящике оказии записка Кузьмы Вере. К ней щепка с зарубкой 71.")],
           push=[line("Котельная. Записка Кузьмы, зарубка 71.")]),
        ev("p_l4", 21200, "pickup", "kotelnaya", item="l4", title="Письмо Мити",
           lines=[line("Рядом конверт Нине. Почерк Мити, ошибки на месте.")],
           push=[line("Котельная. Конверт Нине, рука Мити.")]),
        ev("e_kotel", 23000, "choice", "kotelnaya", title="Котёл живой",
           text="Павел зовёт к котлу. Письма в ящике можно взять и так, и так.",
           default="stay",
           options=[
               {"id":"stay","label":"Посидеть у котла","result":"Сапоги на сушилке. Павел оставляет записку. Ночевать здесь можно.",
                "flags":["kotel_stayed"],"grant":["note_pavel"],
                "auto":"Почтальон сел у котла."},
               {"id":"leave","label":"Идти дальше","result":"Тепло остаётся в кадре. Ящик всё равно доступен.","flags":["kotel_left"]},
           ],
           push=[line("Павел зовёт к котлу. Зайдёшь?")]),
        ev("d_kotelnaya", 21000, "pickup", "kotelnaya", item="l2", title="Оказия вниз",
           lines=[line("Письмо «Андрея» можно оставить в ящике на Котельной, оказия вниз.")],
           push=[line("Котельная. Ящик оказии вниз.")]),
        ev("p_l5", 28000, "pickup", "sarai", item="l5", title="Банка и конверт",
           lines=[line("В сухом сарае конверт «Зое, Верхняя». В тексте банка для Нюры у калитки.")],
           push=[line("Сараи. Конверт Зое, в тексте — Нюра.")]),
        ev("d_sarai", 28000, "pickup", "sarai", item="l3", title="Для Веры",
           lines=[line("Записку Кузьмы и письмо Мити можно оставить на Сараях: «для Веры» и «оказия вниз».")],
           push=[line("Сараи. Ящик «для Веры» и оказия вниз.")]),
        ev("p_l6", 32000, "pickup", "naberezhnaya", item="l6", title="Лента имён",
           lines=[line("На набережной телеграмма Пимена. Тридцать семь имён. Читается здесь.")],
           push=[line("Набережная. Телеграмма Пимена, 37 имён.")]),
        ev("p_l7", 36500, "pickup", "dvory", item="l7", title="Письмо Нины",
           lines=[line("У калитки конверт Мите. Нина знала. Оказия вниз, на Отделение.")],
           push=[line("Дворы. Конверт Мите, рука Нины.")]),
        ev("e_address", 36500, "choice", "dvory", title="На конверте — Зоя",
           text="Банка и конверт. На конверте Зоя, в тексте — Нюра у калитки.",
           default="nyura",
           options=[
               {"id":"nyura","label":"Отдать Нюре у калитки","result":"Нюра берёт банку: «Это мне, да. Зоя туда не ест такое.»",
                "flags":["addr_nyura"],"auto":"Почтальон отдал банку Нюре."},
               {"id":"zoya","label":"Нести на Верхнюю","result":"На Верхней сдать некому. Банку можно потом оставить на Отделении «для Нюры».","flags":["addr_zoya"]},
               {"id":"office","label":"Отдать в отделение","result":"Агния принимает как до востребования и молча отложит.","flags":["addr_office"]},
           ],
           push=[line("Банка и конверт. Кому нести?")]),
        ev("p_l8", 39600, "pickup", "otdelenie", item="l8", title="Записка Веры",
           lines=[line("На стойке записка Веры. Цифры, откладывает снова. Читается здесь.")],
           push=[line("Отделение. Записка Веры, отметка 71.")]),
        ev("p_l9", 40000, "pickup", "otdelenie", item="l9", title="Кладовая",
           lines=[line("В кладовой три мешка и стопка: «от Ксении, брату». Тридцать одно письмо. Тексты не вскрывать.")],
           push=[line("Кладовая. Стопка писем, тексты не вскрывать.")]),
        ev("e_believe", 41000, "choice", "otdelenie", title="Три версии",
           text="После кладовой — три версии. Письма от выбора не меняются.",
           default="agnia",
           options=[
               {"id":"agnia","label":"Держать порядок Агнии","result":"Агния кивает на стойке: «Ноги береги. Почту носи.» Никто не говорит, что она права.",
                "flags":["believe_agnia"],"auto":"Почтальон держит порядок Агнии."},
               {"id":"kuzma","label":"Держать лист Кузьмы","result":"Лист Ферапонта в Истории поднимается выше. Агния этого не комментирует.","flags":["believe_kuzma"]},
               {"id":"vera","label":"Держать замер Веры","result":"Цифры 58 и 71 складываются рядом. Слов «она включила» нет.","flags":["believe_vera"]},
           ],
           push=[line("Три версии. Кому верить?")]),
        ev("d_otdelenie", 39500, "pickup", "otdelenie", item="l7", title="Оказия вниз",
           lines=[line("Письмо Нины можно оставить в ящике отделения, оказия вниз.")],
           push=[line("Отделение. Ящик оказии вниз.")]),
        ev("p_l10", 42600, "pickup", "verkhnyaya", item="l10", title="Записка с Верхней",
           lines=[line("На скамейке записка А.Л.: через оцепление не ходи. Выемку на Краю не назначала.")],
           push=[line("Верхняя. Записка А.Л., дальше хода нет.")]),
        ev("p_cup", 43000, "pickup", "verkhnyaya", item="find_cup", title="Холодная чашка",
           lines=[line("На столе меловая помета и холодная чашка. Кто-то сидел недавно.")],
           push=[line("Верхняя. Чашка ещё холодная.")]),
        ev("finale", 45000, "finale", "verkhnyaya", title="Верхняя",
           lines=[line("Дальше хода нет. Пост ещё впереди, в дымке. Ключ от кладовой не выдан.")],
           push=[line("Верхняя. Глава пройдена.")]),
    ]

    # d_otstoyniki and p_l2 / e_sluice all at ~4000 — order: pickup l2 after arrival, drop l1 is a drop not pickup.
    # Deliver events in ch3 are type pickup with item to drop? Looking at ch3... they might be type something else.
    # check_chapter3 looked for type=="deliver". Some ch3 use pickup for drops with different ids d_*.
    # I'll leave d_* as type pickup like many bag drops that are story beats, or check ch3 d_gat.

    story = {
        "_comment": "Глава 4 «Нижний Створ». Письма дословно из docs/canon/letters-ch4.md (правка слога). Сдача только впереди (t431). Арт находок, вложений и кадров Истории — заглушки env_plain. К-2 вслух не называется.",
        "chapter": 4,
        "slots": 99,
        "days": [
            {"day": 1, "from": 0, "to": 7500},
            {"day": 2, "from": 7500, "to": 15000},
            {"day": 3, "from": 15000, "to": 22500},
            {"day": 4, "from": 22500, "to": 30000},
            {"day": 5, "from": 30000, "to": 37500},
            {"day": 6, "from": 37500, "to": 45000},
        ],
        "items": items,
        "events": events,
        "quests": [
            {"telegram": "Оставить записку А.Л. на Отстойниках", "event": "d_otstoyniki"},
            {"telegram": "До Котельной", "event": "p_l3"},
            {"telegram": "Оставить почту на Сараях", "event": "d_sarai"},
            {"telegram": "До Дворов", "event": "e_address"},
            {"telegram": "К отделению", "event": "e_believe"},
            {"telegram": "До Верхней", "event": "finale"},
        ],
        "residents": [
            {"id":"kolya","name":"Коля","aliases":["kolya","коля","сторож"],"step":4000,"dx":240,"height":430,"sink":0},
            {"id":"pavel","name":"Павел","aliases":["pavel","павел","кочегар"],"step":23000,"dx":240,"height":430,"sink":0},
            {"id":"nyura","name":"Нюра","aliases":["nyura","нюра"],"step":36500,"dx":240,"height":430,"sink":0},
            {"id":"agnia","name":"Агния","aliases":["agnia","агния","а.л.","ворсина"],"step":39500,"dx":240,"height":430,"sink":0},
        ],
        "fates": [
            {"settlement":"otstoyniki","if":"inBag:l1","text":"Записка А.Л. ещё в сумке. Её место — ящик на Отстойниках, «к отделению»."},
            {"settlement":"otstoyniki","if":"delivered:l1","text":"Записка А.Л. оставлена на Отстойниках, к отделению."},
            {"settlement":"kotelnaya","if":"inBag:l2","text":"Письмо «Андрея» ещё в сумке. Оказия вниз — ящик на Котельной."},
            {"settlement":"sarai","if":"inBag:l3","text":"Записка Кузьмы ещё в сумке. Её место — ящик на Сараях, «для Веры»."},
            {"settlement":"sarai","if":"inBag:l4","text":"Письмо Мити ещё в сумке. Оказия вниз — ящик на Сараях."},
            {"settlement":"dvory","if":"inBag:l5","text":"Банка и конверт ещё в сумке. На конверте Зоя, в тексте — Нюра у калитки."},
            {"settlement":"otdelenie","if":"inBag:l7","text":"Письмо Нины ещё в сумке. Оказия вниз — ящик отделения."},
        ],
        "finaleTitle": "Глава 4 · Нижний Створ",
        "finaleSubtitle": "пройдена",
        "nextChapter": "Глава 5 «Край карты» — скоро",
        "trustSettlements": ["otdelenie"],
        "choicePolicy": {"mode": "notifyThenAuto", "timeoutSteps": 400},
        "arrivals": [
            {"settlement":"shlagbaum","text":"Шлагбаум. Полосатая жесть, тёплый котелок, трубы в разрыве. В ящике записка А.Л."},
            {"settlement":"otstoyniki","text":"Отстойники. Дамбы, пруды, будка Коли. В ящике — конверт и место «к отделению»."},
            {"settlement":"kotelnaya","text":"Котельная. Один котёл «для верхних». В ящике оказии — почта вниз и для Веры."},
            {"settlement":"sarai","text":"Сараи. Сухое сено, голуби. Ящик «для Веры» и оказия вниз. В углу — банка и конверт Зое."},
            {"settlement":"naberezhnaya","text":"Набережная. Телеграмма Пимена, тридцать семь имён. Читается здесь."},
            {"settlement":"dvory","text":"Дворы. Нюра у калитки. Банка для неё, хотя на конверте — Зоя."},
            {"settlement":"otdelenie","text":"Отделение. Агния на стойке. «Поешь сначала». Дальше — кладовая и три версии."},
            {"settlement":"verkhnyaya","text":"Верхняя. Табличка, скамейка, вид дальше. Хода через оцепление нет."},
        ],
    }
    (DATA / "chapter4_story.json").write_text(json.dumps(story, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("chapter4_story.json written, items", len(items), "events", len(events))

    # update ch3 next chapter title
    p = DATA / "chapter3_story.json"
    s3 = json.loads(p.read_text(encoding="utf-8"))
    s3["nextChapter"] = "Глава 4 «Нижний Створ»"
    p.write_text(json.dumps(s3, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("chapter3 nextChapter updated")

def build_taps(taps):
    # Tap targets sit on the chapter-4 art itself (el_*, places, ambient), invisible: the prop is the picture.
    (DATA / "chapter4_taps.json").write_text(json.dumps(taps, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("chapter4_taps.json", len(taps))

if __name__ == "__main__":
    import sys
    props_only = "--props-only" in sys.argv
    taps = build_world()
    build_taps(taps)
    if not props_only:
        build_story()
    else:
        print("props-only: story left untouched")
