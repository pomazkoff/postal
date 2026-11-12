#!/usr/bin/env python3
"""Собирает GameAssets/Data/chapter1_story.json — сюжет главы 1 для ChapterEngine.

Тексты писем берутся ДОСЛОВНО из walking-sim/letters-ch1.md (блоки цитат «> » под «## Письмо N»;
правки библии 2026-11-04 там уже учтены). Реплики жителей, события с выбором и телеграммы-задания
написаны здесь по chapter1-timeline.md (отрезки 1–11) и story-bible.md §4 — черновик, помечен "draft".

Условия (поле "if", через запятую, все должны выполняться; "!" — отрицание):
  inBag:ID  inPocket:ID  delivered:ID  missed:ID (=не вручено)  opened:ID  sealed:ID (вручено и не вскрыто)
  sent:ID  lost:ID  atPost:ID  left:ID  flag:NAME  carried:ID (было в сумке хоть раз)
Запуск: python3 tools/build_chapter1_story.py [путь к walking-sim]
"""
import sys, os, re, json
WS = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "/workspace/walking-sim")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "Postman/GameAssets/Data/chapter1_story.json")

md = open(os.path.join(WS, "letters-ch1.md"), encoding="utf-8").read()
def letter_blocks(n):
    m = re.search(r"^## Письмо %d\..*?$(.*?)(?=^## )" % n, md, re.S | re.M)
    assert m, n
    blocks, cur = [], []
    for ln in m.group(1).split("\n"):
        if ln.startswith(">"):
            cur.append(ln[1:].lstrip(" ") if ln.startswith("> ") or ln == ">" else ln[1:])
        elif cur:
            blocks.append("\n".join(cur).strip()); cur = []
    if cur: blocks.append("\n".join(cur).strip())
    return blocks

L = {n: letter_blocks(n) for n in range(1, 8)}
assert L[5][0].startswith("СЧЁТ") and L[5][1].startswith("ВЕРА ТЧК"), L[5]
assert L[7][1].startswith("Уважаемый почтальон"), L[7]
assert L[6][0].startswith("МАМОЧКА ЗДРАСТВУЙ"), L[6][0]

def line(who, text, cond=None):
    d = {"who": who, "text": text}
    if cond: d["if"] = cond
    return d

items = [
    {"id": "l1", "kind": "letter", "takesSlot": True, "to": "Кузьме", "place": "Сваи", "settlement": "svai",
     "from": "Нина", "senderSettlement": "kadushki", "art": "env_plain", "stick": "stick_plain", "initial": "atPost",
     "reader": {"paper": "sheet", "font": "hand", "envelope": "renv_open", "address": ["СВАИ.", "КУЗЬМЕ ЕРОФЕИЧУ", "ОТ НИНЫ"],
                "attachment": None, "attachmentCaption": "засушенный зонтик укропа в обрывке газеты"},
     "text": L[1][0]},
    {"id": "l2", "kind": "letter", "takesSlot": True, "to": "Пимену", "place": "Звонарня", "settlement": "zvonarnya",
     "from": "Митя", "senderSettlement": "svai", "art": "env_plain", "stick": "stick_plain", "initial": "atPost",
     "reader": {"paper": "sheet", "font": "hand", "envelope": "renv_open", "address": ["ЗВОНАРНЯ.", "ОТЦУ ПИМЕНУ", "ОТ МИТИ (УС)"],
                "attachment": "att_drawing", "attachment2": "att_wrapper_yellow",
                "attachmentCaption": "чертёж на миллиметровке и жёлтый фантик «ёлочкой»"},
     "text": L[2][0]},
    {"id": "l3", "kind": "letter", "takesSlot": True, "to": "Тимофею", "place": "Ольховка · через Седло", "settlement": "sedlo",
     "from": "Нина", "senderSettlement": "kadushki", "art": "env_fat", "stick": "stick_fat", "initial": "atPost",
     "reader": {"paper": "sheet", "font": "hand", "envelope": "renv_fat",
                "address": ["Ольховка, до востребования.", "Колобову Тимофею", "Григорьевичу"],
                "attachment": None, "attachmentCaption": "серые шерстяные носки, пятка двойная"},
     "text": L[3][0]},
    {"id": "l4", "kind": "form", "takesSlot": False, "to": "Почтальону", "place": "от Веры · НИИ", "settlement": "nii",
     "from": "Вера", "senderSettlement": "nii", "art": "form", "stick": "stick_plain", "initial": "inPocket",
     "reader": {"paper": "sheet_form", "font": "draft", "envelope": None, "address": [],
                "attachment": None, "attachmentCaption": "сдать Вере в руки, в ящик НИИ не опускать"},
     "text": L[4][0]},
    {"id": "batteries", "kind": "parcel", "takesSlot": True, "to": "Вере", "place": "НИИ · 12 шт.", "settlement": "nii",
     "from": "Лавка", "senderSettlement": "kadushki", "art": "parcel", "stick": "stick_parcel", "initial": "onRoad",
     "road": "road_parcel",
     "reader": None, "text": "Элементы питания 1,5 В, «бочонок» — 12 шт. Холщовый мешочек. Нести отдельно от писем: подтекают."},
    {"id": "l5", "kind": "secret", "takesSlot": True, "to": "Вере", "place": "НИИ · лично", "settlement": "nii",
     "from": "Пимен", "senderSettlement": "zvonarnya", "art": "env_wax", "artOpened": "env_wax2", "stick": "stick_wax",
     "initial": "onRoad", "road": "road_envstake",
     "reader": {"paper": "sheet_telegram", "font": "tape", "envelope": "renv_wax", "envelopeOpened": "renv_wax2",
                "address": ["В И ПАСЕЧНИК", "ЛИЧНО"], "attachment": None,
                "attachmentCaption": "печать — оттиск большого пальца в свечном воске"},
     "outside": L[5][0], "text": L[5][1]},
    {"id": "l6", "kind": "letter", "takesSlot": True, "to": "Нине", "place": "Кадушки", "settlement": "kadushki",
     "from": "«Тимофей»", "senderSettlement": "kadushki", "art": "env_tima", "stick": "stick_tima", "initial": "onRoad",
     "road": "road_envstake",
     "reader": {"paper": "sheet", "font": "hand", "envelope": "renv_open",
                "address": ["КАДУШКИ.", "КОЛОБОВОЙ Н.А.", "ОТ СЫНА ТИМОФЕЯ"], "stamp": ["КАДУШКИ", "ящ. 2"],
                "attachment": "att_wrapper_green", "attachmentCaption": "зелёный фантик «ёлочкой»"},
     "text": L[6][0]},
    {"id": "l7", "kind": "letter", "takesSlot": False, "to": "Почтальону", "place": "Седло · выемка", "settlement": "sedlo",
     "from": "«Ксения»", "senderSettlement": "sedlo", "art": "env_ksenia", "stick": "stick_plain", "initial": "onRoad",
     "reader": {"paper": "sheet_telegram", "font": "violet", "envelope": "renv_open",
                "address": ["Долина, Почта на Развилке.", "Почтальону"], "stamp": ["Н. СТВОР", "{postmark}"],
                "attachment": "att_label", "attachmentDate": "{labelDate}",
                "attachmentCaption": "этикетка «Килька. Ольховский консервный», отмочена с банки"},
     "note": L[7][1], "text": L[7][0]},
]

S = lambda k: k  # settlement ids as in world.json
events = [
    {"id": "sort", "step": 0, "type": "sort", "settlement": "pochta", "candidates": ["l1", "l2", "l3"],
     "log": [line("", "Почта: утренний разбор. В сумку взяты письма.", "")]},
    {"id": "e_cart", "step": 1200, "type": "choice", "settlement": "svai",
     "title": "Тачка поперёк дороги",
     "text": "Тачка с капустой съехала колесом в канаву и стоит поперёк дороги. Рядом старуха из Кадушек, держит оглоблю.",
     "options": [
         {"id": "help", "label": "Помочь", "result": "Вытащили вдвоём. Старуха сунула в сумку кочерыжку: «Нине поклон».",
          "trust": {"kadushki": 1}},
         {"id": "around", "label": "Обойти", "result": "Обошёл по меже. За спиной долго ругают колесо."}]},
    {"id": "d_l1", "step": 2900, "type": "deliver", "settlement": "svai", "resident": "kuzma", "items": ["l1"],
     "lines": [line("Кузьма", "Ну. От Нины. Лещей нету — вон, внук и приписал.", "delivered:l1"),
               line("Кузьма", "Зонтик посажу. Банку пусть шлёт.", "delivered:l1"),
               line("Митя", "Это я писал. Рука быстрая. Приём.", "delivered:l1"),
               line("Кузьма", "Ну. Пусто сегодня? Ага. Гони дальше.", "missed:l1"),
               line("Митя", "А от бабы Нины ничего? Она ж писала.", "missed:l1")]},
    {"id": "e_ramka", "step": 4500, "type": "choice", "settlement": "zvonarnya",
     "title": "Коза на дороге",
     "text": "На подъёме за пасекой стоит коза, жуёт кипрей. На левом ухе надрез.",
     "options": [
         {"id": "lead", "label": "Взять с собой", "result": "Пошёл вверх — коза пошла следом. Не отстаёт.",
          "trust": {"nii": 1}, "flags": ["ramka"]},
         {"id": "chase", "label": "Согнать", "result": "Махнул сумкой. Коза отошла к ульям и смотрит вслед."}]},
    {"id": "d_l2", "step": 6000, "type": "deliver", "settlement": "zvonarnya", "resident": "pimen", "items": ["l2"],
     "lines": [line("Пимен", "Антенну, значит. На колокольню. Пчёл он не боится.", "delivered:l2"),
               line("Пимен", "Передай отроку: подумаю.", "delivered:l2"),
               line("Пимен", "Пусто? Бог даст, в другой раз.", "missed:l2")]},
    {"id": "p_l5", "step": 6100, "type": "pickup", "settlement": "zvonarnya", "resident": "pimen", "item": "l5",
     "lines": [line("Пимен", "Вере Игнатьевне. Лично. В руки.", "inBag:l5"),
               line("Пимен", "Сумка полна? Ну, у ворот оставлю. Бог даст, кто подберёт.", "left:l5")]},
    {"id": "s_nina", "step": 8900, "type": "scene", "settlement": "kadushki", "resident": "nina",
     "lines": [line("Нина", "Ну что, донёс Тимоше?"),
               line("", "Письмо Тимофею лежит в сумке.", "inBag:l3"),
               line("", "Письмо Тимофею осталось на Почте.", "atPost:l3")]},
    {"id": "p_l6", "step": 9000, "type": "pickup", "settlement": "kadushki", "item": "l6",
     "lines": [line("", "Выемка: ящик №2 у колодца. Один конверт. Отметка выемки: «Кадушки, ящ. 2».", "inBag:l6"),
               line("", "Ящик №2: один конверт. Места в сумке нет — остался в ящике.", "left:l6")]},
    {"id": "d_l6", "step": 9100, "type": "deliver", "settlement": "kadushki", "resident": "nina", "items": ["l6"],
     "lines": [line("Нина", "От Тимоши? Ты положи на стол. Митя придёт — прочитает.", "delivered:l6"),
               line("Нина", "Ты с дороги сядь сначала, покушай.", "delivered:l6"),
               line("Нина", "Ничего сегодня? Ну, сядь хоть, покушай.", "missed:l6")]},
    {"id": "p_bat", "step": 9300, "type": "pickup", "settlement": "kadushki", "item": "batteries",
     "lines": [line("Лавка", "Двенадцать. Пересчитай, она велела. Мешочек не переворачивай.", "inBag:batteries"),
               line("Лавка", "Сумка полная — куда тебе. Пусть лежат, сыр уплачен.", "left:batteries")]},
    {"id": "e_storm", "step": 11000, "type": "choice", "settlement": "nii",
     "title": "Гроза",
     "text": "Над ручьём гремит. У водовода будка гидротурбины, дверь приоткрыта.",
     "options": [
         {"id": "shelter", "label": "Переждать в будке", "result": "Внутри сухо. Гудит громче, чем снаружи. Переждал.",
          "flags": ["hum"]},
         {"id": "go", "label": "Идти дальше", "result": "Промок. Клапан сумки держит, конверты сухие."}]},
    {"id": "d_vera", "step": 13200, "type": "deliver", "settlement": "nii", "resident": "vera", "items": ["batteries", "l5", "l4"],
     "lines": [line("Вера", "Двенадцать. Пересчитаю.", "delivered:batteries"),
               line("Вера", "Элементов нет. Требование верните.", "missed:batteries"),
               line("Вера", "Счёт от Звонарни. Хорошо.", "sealed:l5"),
               line("Вера", "Печать вскрывали. Отпечатков два. Второй, полагаю, ваш.", "opened:l5,delivered:l5"),
               line("Вера", "Рамку привели. Благодарю.", "flag:ramka"),
               line("Вера", "P.S. Рамка опять ночевала в антенне.", "!flag:ramka")]},
    {"id": "e_wind", "step": 15500, "type": "choice", "settlement": "sedlo", "requires": "inBag:l3",
     "title": "Ветер",
     "text": "На серпантине ветер рвёт клапан сумки. Пухлый конверт уносит вниз по склону, к отбойнику.",
     "fallback": "Ветер треплет пустой клапан сумки. Терять нечего.",
     "options": [
         {"id": "chase", "label": "Догнать", "result": "Догнал у отбойника. Конверт в грязи, но целый."},
         {"id": "let", "label": "Отпустить", "result": "Конверт ушёл в туман вместе с носками.",
          "effects": [{"item": "l3", "status": "lostWind"}], "trust": {"kadushki": -1}}]},
    {"id": "finale", "step": 20000, "type": "finale", "settlement": "sedlo", "send": "l3", "receive": "l7",
     "lines": [line("", "Ящик на Седле. Табличка: «Выемка: вт, чт».", ""),
               line("", "Письмо Нины опущено в ящик.", "sent:l3"),
               line("", "Опускать в ящик нечего.", "!sent:l3"),
               line("", "Внутри конверт «Почтальону» и записка на бланке.", "")],
     "note": L[7][1]},
]

quests = [
    {"telegram": "Вся почта уже в сумке", "event": "sort"},
    {"telegram": "Отнести письмо Нины Кузьме в Сваи", "event": "d_l1", "if": "inBag:l1"},
    {"telegram": "Отнести письмо Мити отцу Пимену в Звонарню", "event": "d_l2", "if": "inBag:l2"},
    {"telegram": "Зайти в Звонарню к отцу Пимену", "event": "p_l5"},
    {"telegram": "Дойти до Кадушек, заглянуть в ящик №2", "event": "p_l6"},
    {"telegram": "Отдать Нине письмо из ящика №2", "event": "d_l6", "if": "inBag:l6"},
    {"telegram": "Забрать 12 батареек в Лавке для Веры", "event": "p_bat"},
    {"telegram": "Отнести батарейки и письмо Пимена Вере в НИИ", "event": "d_vera", "if": "inBag:batteries"},
    {"telegram": "Отнести письмо Пимена Вере в НИИ", "event": "d_vera", "if": "inBag:l5"},
    {"telegram": "Дойти до НИИ, к Вере Игнатьевне", "event": "d_vera"},
    {"telegram": "Донести письмо Нины до ящика на Седле", "event": "finale", "if": "inBag:l3"},
    {"telegram": "Дойти до ящика на Седле", "event": "finale"},
]

residents = [
    {"id": "kuzma", "name": "Кузьма", "aliases": ["kuzma", "кузьма", "kuzma_us"], "step": 2900, "dx": 300, "height": 410},
    {"id": "mitya", "name": "Митя", "aliases": ["mitya", "митя", "mitia", "dima"], "step": 2900, "dx": 520, "height": 300},
    {"id": "pimen", "name": "Пимен", "aliases": ["pimen", "пимен"], "step": 6000, "dx": 300, "height": 420},
    {"id": "nina", "name": "Нина", "aliases": ["nina", "нина", "baba_nina"], "step": 8900, "dx": 300, "height": 370},
    {"id": "vera", "name": "Вера", "aliases": ["vera", "вера"], "step": 13200, "dx": 300, "height": 410},
    {"id": "agnia", "name": "А.Л.", "aliases": ["agnia", "агния", "al"], "step": 99999, "dx": 0, "height": 400},
]

fates = [
    {"settlement": "svai", "if": "delivered:l1", "text": "Кузьме — письмо Нины: вручено. Зонтик укропа — в ящик на мостках."},
    {"settlement": "svai", "if": "!delivered:l1", "text": "Кузьме письма не было: осталось на Почте."},
    {"settlement": "zvonarnya", "if": "delivered:l2", "text": "Пимену — просьба Мити про антенну: вручено, «подумаю»."},
    {"settlement": "zvonarnya", "if": "!delivered:l2", "text": "Просьба Мити про антенну осталась на Почте."},
    {"settlement": "kadushki", "if": "delivered:l6", "text": "Нине — письмо «от сына» из ящика №2: вручено."},
    {"settlement": "kadushki", "if": "!delivered:l6", "text": "Письмо «от сына» Нина не получила."},
    {"settlement": "nii", "if": "delivered:batteries", "text": "Вере — 12 элементов питания по требованию № 23."},
    {"settlement": "nii", "if": "!delivered:batteries", "text": "Батарейки Вере не принесены. Требование № 23 вернулось."},
    {"settlement": "nii", "if": "sealed:l5", "text": "Счёт Пимена: печать цела, один отпечаток."},
    {"settlement": "nii", "if": "opened:l5", "text": "Письмо Пимена вскрыто: на печати два отпечатка. Вера заметила."},
    {"settlement": "nii", "if": "flag:ramka", "text": "Рамка дома, в антенне."},
    {"settlement": "sedlo", "if": "sent:l3", "text": "Тимофею — носки и письмо Нины: опущено в ящик на Седле."},
    {"settlement": "sedlo", "if": "lost:l3", "text": "Письмо Нины унёс ветер на серпантине."},
    {"settlement": "sedlo", "if": "atPost:l3", "text": "Письмо Нины Тимофею осталось на Почте."},
]

# --- История без игрока (ПРЕДВАРИТЕЛЬНО, ждёт подтверждения) -------------------------------------------
# default — вариант «в характере» почтальона, если игрок не ответил; auto — строка «выбрал почтальон».
# push — строки локального пуша (первая с выполненным условием). Режим — choicePolicy ниже.
CHOICE_DEFAULTS = {
    "e_cart": ("help", "Почтальон не стал ждать — упёрся плечом в тачку."),
    "e_ramka": ("lead", "Почтальон пожал плечами и пошёл в гору. Коза — следом."),
    "e_storm": ("shelter", "Почтальон нырнул в будку турбины — пусть гремит."),
    "e_wind": ("chase", "Почтальон сорвался с места и побежал за конвертом."),
}
PUSH = {
    "sort": [line("", "Почта. Сумка застёгнута, почтальон вышел затемно.", "")],
    "e_cart": [line("", "Сваи, дорога. Тачка с капустой поперёк пути — помочь старухе?", "")],
    "d_l1": [line("", "Сваи. Кузьма взял письмо мокрыми руками: «Ну. От Нины.»", "delivered:l1"),
             line("", "Сваи. Кузьма глядит в пустую сумку: «Ну. Гони дальше.»", "missed:l1")],
    "e_ramka": [line("", "Подъём к Звонарне. Коза с надрезом на ухе жуёт кипрей и смотрит на сумку.", "")],
    "d_l2": [line("", "Звонарня. Пимен прочёл про антенну и сказал: «Подумаю».", "delivered:l2"),
             line("", "Звонарня. Писем нет — колокол гудит за двоих.", "missed:l2")],
    "p_l5": [line("", "Звонарня. Пимен сунул в сумку письмо: «Вере Игнатьевне. Лично.»", "inBag:l5"),
             line("", "Звонарня. Сумка полна — письмо Пимена осталось у ворот.", "left:l5")],
    "s_nina": [line("", "Кадушки. Нина вытирает руки о передник: «Донёс Тимоше?»", "")],
    "p_l6": [line("", "Кадушки. В ящике №2 у колодца — один конверт.", "inBag:l6"),
             line("", "Кадушки. В ящике №2 конверт, а в сумке нет места.", "left:l6")],
    "d_l6": [line("", "Кадушки. Нина положила письмо «от сына» на стол — ждать Митю.", "delivered:l6"),
             line("", "Кадушки. Нина: «Ничего сегодня? Ну, сядь хоть, покушай.»", "missed:l6")],
    "p_bat": [line("", "Лавка в Кадушках. Двенадцать батареек в мешочке — не переворачивать.", "inBag:batteries"),
              line("", "Лавка в Кадушках. Батарейки не влезли — пусть лежат, сыр уплачен.", "left:batteries")],
    "e_storm": [line("", "Над ручьём гремит. Будка гидротурбины приоткрыта — переждать?", "")],
    "d_vera": [line("", "НИИ. Вера пересчитывает батарейки. Двенадцать.", "delivered:batteries"),
               line("", "НИИ. Вера Игнатьевна приняла почту и ничего не сказала.", "")],
    "e_wind": [line("", "Седло, серпантин. Ветер уносит пухлый конверт к отбойнику!", "inBag:l3"),
               line("", "Седло. Ветер треплет пустой клапан сумки.", "")],
    "finale": [line("", "Седло. В синем ящике конверт «Почтальону».", "")],
}
for ev in events:
    if ev["id"] in CHOICE_DEFAULTS:
        default, auto = CHOICE_DEFAULTS[ev["id"]]
        ev["default"] = default
        for opt in ev["options"]:
            if opt["id"] == default:
                opt["auto"] = auto
    if ev["id"] in PUSH:
        ev["push"] = PUSH[ev["id"]]
ARRIVALS = [
    {"settlement": "svai", "text": "Сваи. Под ногами доски, под досками — вода. Кто-то сушит лещей."},
    {"settlement": "zvonarnya", "text": "Звонарня. Пахнет воском, над головой гудит колокол."},
    {"settlement": "kadushki", "text": "Кадушки. Бочки, укроп, дым из граммофонной трубы."},
    {"settlement": "nii", "text": "НИИ. Окна горят и днём."},
    {"settlement": "sedlo", "text": "Седло. Перевал. Туман и синий почтовый ящик."},
]

story = {
    "_comment": "Сгенерировано tools/build_chapter1_story.py. Тексты писем — дословно из walking-sim/letters-ch1.md "
                "(правки библии от 2026-11-04 применены). Реплики, события и телеграммы — черновик (draft).",
    "chapter": 1, "slots": 3,
    "days": [{"day": 1, "from": 0, "to": 7500}, {"day": 2, "from": 7500, "to": 15000}, {"day": 3, "from": 15000, "to": 20000}],
    "items": items, "events": events, "quests": quests, "residents": residents, "fates": fates,
    "finaleTitle": "Глава 1 · Долина", "finaleSubtitle": "пройдена", "nextChapter": "Глава 2 «Горы»",
    "trustSettlements": ["svai", "zvonarnya", "kadushki", "nii"],
    # notifyThenAuto | auto | wait. timeoutSteps — сколько шагов ждать ответа, если следующая остановка далеко.
    "choicePolicy": {"mode": "notifyThenAuto", "timeoutSteps": 400},
    "arrivals": ARRIVALS,
    "sortDefault": ["l1", "l2", "l3"],
    "sortAuto": "Почтальон берёт всю почту. На бирке написано, куда нести каждое письмо.",
}
import sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ch1_choices
ch1_choices.apply(story)

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(story, fh, ensure_ascii=False, indent=1)
print("wrote", OUT, len(items), "items", len(events), "events")
