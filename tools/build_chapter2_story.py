#!/usr/bin/env python3
"""Собирает GameAssets/Data/chapter2_story.json — сюжет главы 2 «Горы».

Тексты писем — ДОСЛОВНО из walking-sim/letters-ch2.md (блоки «> » под «## Письмо N»).
События, реплики, телеграммы — по chapter2-timeline.md v1 + story-bible §5б (draft).
Шаги — позиция на ленте гл.2 от Седла (0…25000). Не трогает chapter1_story.json.

Запуск: python3 tools/build_chapter2_story.py [путь к walking-sim]
"""
import sys, os, re, json

WS = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "/workspace/walking-sim")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "Postman/GameAssets/Data/chapter2_story.json")

md = open(os.path.join(WS, "letters-ch2.md"), encoding="utf-8").read()

def letter_blocks(n):
    m = re.search(r"^## Письмо %d\..*?$(.*?)(?=^## )" % n, md, re.S | re.M)
    assert m, f"letter {n} missing"
    blocks, cur = [], []
    for ln in m.group(1).split("\n"):
        if ln.startswith(">"):
            cur.append(ln[1:].lstrip(" ") if ln.startswith("> ") or ln == ">" else ln[1:])
        elif cur:
            blocks.append("\n".join(cur).strip()); cur = []
    if cur:
        blocks.append("\n".join(cur).strip())
    return blocks

L = {n: letter_blocks(n) for n in range(1, 10)}
# letter 1: [0]=А.Л. note, [1]=Тима body
assert "Задержалось на сортировке" in L[1][0] or "задержалось" in L[1][0].lower(), L[1][0][:80]
assert L[1][1].startswith("Мам"), L[1][1][:40]
assert "0,25" in L[2][0] or "0.25" in L[2][0], L[2][0][:60]
assert "СГОРЕЛ" in L[3][0], L[3][0][:60]
assert "до петухов" in L[4][0], L[4][0]
assert "ТЧК" in L[5][0], L[5][0]
assert "7,3" in L[6][0] or "7.3" in L[6][0], L[6][0][:80]
assert "МАМОЧКА" in L[7][0], L[7][0][:40]
assert "44" in L[8][0], L[8][0]
assert "ДВА СОРОК" in L[9][0], L[9][0]

def line(who, text, cond=None):
    d = {"who": who, "text": text}
    if cond:
        d["if"] = cond
    return d

# --- items (9 letters + AL note is on l1) -------------------------------------------------
items = [
    {"id": "l1", "kind": "letter", "takesSlot": True, "to": "Нине", "place": "Кадушки · через Веру",
     "settlement": "sedlo", "from": "Тимофей", "senderSettlement": "sedlo",
     "art": "env_plain", "stick": "stick_plain", "initial": "onRoad", "road": "road_envstake",
     "reader": {"paper": "sheet", "font": "hand", "envelope": "renv_open",
                "address": ["КАДУШКИ.", "КОЛОБОВОЙ Н.А.", "ОТ СЫНА"],
                "stamp": ["Н. СТВОР", "накануне"],
                "attachment": None, "attachmentCaption": "расчётный листок получки, сложенный вчетверо; сумма «к выдаче» — 40"},
     "note": L[1][0], "text": L[1][1]},
    {"id": "l2", "kind": "parcel", "takesSlot": True, "to": "Мите", "place": "Сваи · через Веру",
     "settlement": "sedlo", "from": "Вера", "senderSettlement": "nii",
     "art": "parcel", "stick": "stick_parcel", "initial": "onRoad", "road": "road_parcel",
     "reader": {"paper": "sheet_form", "font": "draft", "envelope": None, "address": ["Дмитрию Усу"],
                "attachment": None, "attachmentCaption": "стеклянный предохранитель 0,25 А в конвертике из миллиметровки; бирка «К-2»"},
     "text": L[2][0]},
    {"id": "l3", "kind": "letter", "takesSlot": True, "to": "Вере", "place": "НИИ",
     "settlement": "sedlo", "from": "Митя", "senderSettlement": "svai",
     "art": "env_plain", "stick": "stick_plain", "initial": "onRoad", "road": "road_envstake",
     "reader": {"paper": "sheet", "font": "hand", "envelope": "renv_open",
                "address": ["НИИ РАДИОТЕНЬ.", "ПАСЕЧНИК В.И."],
                "attachment": None, "attachmentCaption": "сгоревший предохранитель, усики обгоревшие; помета «0,25 А — СГОРЕЛ»"},
     "text": L[3][0]},
    {"id": "l4", "kind": "letter", "takesSlot": True, "to": "Мите", "place": "Сваи · через Веру",
     "settlement": "penki", "from": "Кузьма", "senderSettlement": "svai",
     "art": "env_plain", "stick": "stick_plain", "initial": "onRoad", "road": "road_envstake",
     "reader": {"paper": "sheet", "font": "hand", "envelope": "renv_open",
                "address": ["МИТЕ УСУ"],
                "attachment": None, "attachmentCaption": "севшая батарейка «бочонок» 1,5 В; обёртка с жирным пятном"},
     "text": L[4][0]},
    {"id": "l5", "kind": "letter", "takesSlot": True, "to": "Мите", "place": "Сваи · через Веру",
     "settlement": "sedlo", "from": "Пимен", "senderSettlement": "zvonarnya",
     "art": "env_wax", "stick": "stick_wax", "initial": "onRoad", "road": "road_envstake",
     "reader": {"paper": "sheet_telegram", "font": "tape", "envelope": "renv_wax",
                "address": ["ОТРОКУ МИТРИЮ УСУ"],
                "attachment": None, "attachmentCaption": "огарок восковой свечи; таблица азбуки Морзе на обрывке ленты"},
     "text": L[5][0]},
    {"id": "l6", "kind": "letter", "takesSlot": True, "to": "Вере", "place": "НИИ",
     "settlement": "sedlo", "from": "Митя", "senderSettlement": "svai",
     "art": "env_plain", "stick": "stick_plain", "initial": "onRoad", "road": "road_envstake",
     "reader": {"paper": "sheet", "font": "hand", "envelope": "renv_open",
                "address": ["НИИ РАДИОТЕНЬ.", "ПАСЕЧНИК В.И."],
                "attachment": None, "attachmentCaption": "лист журнала замеров: день / час / 7,3; у чт — «тише»"},
     "text": L[6][0]},
    {"id": "l7", "kind": "letter", "takesSlot": True, "to": "Нине", "place": "Кадушки · через Веру",
     "settlement": "penki", "from": "«Тимофей»", "senderSettlement": "kadushki",
     "art": "env_tima", "stick": "stick_tima", "initial": "onRoad", "road": "road_envstake",
     "reader": {"paper": "sheet", "font": "hand", "envelope": "renv_open",
                "address": ["КАДУШКИ.", "КОЛОБОВОЙ Н.А.", "ОТ СЫНА ТИМОФЕЯ"],
                "stamp": ["КАДУШКИ", "ящ. 2"],
                "attachment": "att_wrapper_yellow", "attachmentCaption": "фантик, сложенный «ёлочкой»-антенной"},
     "text": L[7][0]},
    {"id": "l8", "kind": "secret", "takesSlot": True, "to": "Вере", "place": "НИИ · лично",
     "settlement": "sedlo", "from": "Кузьма", "senderSettlement": "svai",
     "art": "env_wax", "artOpened": "env_wax2", "stick": "stick_wax", "initial": "onRoad", "road": "road_envstake",
     "reader": {"paper": "sheet", "font": "hand", "envelope": "renv_wax", "envelopeOpened": "renv_wax2",
                "address": ["В.И. Пасечник.", "Лично"],
                "attachment": None, "attachmentCaption": "щепка с зарубкой 44; смоляная капля"},
     "outside": "В.И. Пасечник. Лично.", "text": L[8][0]},
    {"id": "l9", "kind": "form", "takesSlot": False, "to": "Почтальону", "place": "от Пимена",
     "settlement": "krivulya", "from": "Пимен", "senderSettlement": "zvonarnya",
     "art": "card_telegram", "stick": "stick_plain", "initial": "onRoad", "road": "road_envstake",
     "reader": {"paper": "sheet_telegram", "font": "tape", "envelope": None, "address": ["ПОЧТАЛЬОНУ"],
                "attachment": None, "attachmentCaption": "узкая полоска телеграфной ленты; печать — оттиск большого пальца в воске"},
     "text": L[9][0]},
    {"id": "note_gar", "kind": "form", "takesSlot": False, "to": "Кадушки", "place": "записка лесника",
     "settlement": "gar", "from": "Лесник", "senderSettlement": "gar",
     "art": "env_plain", "stick": "stick_plain", "initial": "onRoad",
     "reader": {"paper": "sheet", "font": "hand", "envelope": None, "address": [],
                "attachment": None, "attachmentCaption": "в будку на Хомуте, с почтой вниз"},
     "text": "Кадушкам. Жив. Калитку чиню. Чаю мало. Если оказия — соли пришлите. Л."},
]

# --- events (steps = гл.2 от Седла) -------------------------------------------------------
events = [
    {"id": "p_l1", "step": 50, "type": "pickup", "settlement": "sedlo", "item": "l1",
     "lines": [line("", "Выемка: Седло. Конверт Колобовой Н.А. и записка А.Л. «Задержалось на сортировке».", "inBag:l1"),
               line("", "Ящик на Седле: конверт есть, а в сумке нет места.", "left:l1")]},
    {"id": "p_l2", "step": 200, "type": "pickup", "settlement": "sedlo", "item": "l2",
     "title": "Ящик НИИ · скролл",
     "text": "В ящике у НИИ (скролл назад) — посылка-мелочь от Веры Мите. Предохранитель 0,25 А.",
     "lines": [line("", "Посылка Веры: предохранитель 0,25 А, бирка «К-2».", "inBag:l2"),
               line("", "Посылка Веры не влезла.", "left:l2")]},
    {"id": "s_nii_drop", "step": 400, "type": "scene", "settlement": "sedlo",
     "title": "Ящик «для нижних»",
     "text": "Чтобы Нина получила настоящее письмо Тимофея, его нужно оставить в ящике НИИ — Вера заберёт в четверг.",
     "lines": [line("", "Оставил письмо 1 в ящике НИИ «для нижних».", "inBag:l1"),
               line("", "Письмо 1 ещё в сумке — без НИИ Нине не дойдёт.", "inBag:l1")],
     "flags": ["nii_drop_hint"]},
    {"id": "e_windfall", "step": 1600, "type": "choice", "settlement": "gar",
     "title": "Ветровал",
     "text": "Ельник «Лапы». Поперёк дороги лежит ствол. Лапы елей как рукава.",
     "options": [
         {"id": "climb", "label": "Перелезть", "result": "Перелез. Хвоя в сумке, колени мокрые."},
         {"id": "around", "label": "Обойти", "result": "Обошёл по прогалу. +~400 шагов (предв.).",
          "flags": ["windfall_detour"]}],
     "default": "climb"},
    {"id": "arrive_gar", "step": 2800, "type": "scene", "settlement": "gar", "resident": "lesnik",
     "title": "Кордон «Гарь»",
     "text": "Сторожка, колодец, две кружки на столе — вторая чуть качается. Лесник чинит калитку.",
     "lines": [line("Лесник", "Жив. Калитку чиню. Передай вниз родичам в Кадушки — соли бы."),
               line("Лесник", "Чаю мало. Керосин есть. Садись."),
               line("", "Две кружки. Вторая качается.", "")]},
    {"id": "p_note_gar", "step": 2850, "type": "pickup", "settlement": "gar", "resident": "lesnik", "item": "note_gar",
     "lines": [line("Лесник", "В будку на Хомуте положи, с почтой вниз. Просто весточка.", "inPocket:note_gar"),
               line("Лесник", "Ну, как знаешь.", "")]},
    {"id": "arrive_penki", "step": 6500, "type": "scene", "settlement": "penki", "resident": "brigadir",
     "title": "Лесосека «Пеньки»",
     "text": "Пни-дома, штабеля, трактор без колёс. Дымок костра. Ночёвка «где застал день».",
     "lines": [line("Бригадир", "Консервы на свечи Звонарни — если оказия."),
               line("Бригадир", "Завтра четверг. Вера заберёт «нижних» из ящика НИИ — если успел оставить."),
               line("", "Напоминание: письмо 1 должно лежать в НИИ.", "flag:nii_drop_hint")]},
    {"id": "e_blizzard", "step": 9500, "type": "choice", "settlement": "khomut",
     "title": "Метель на метку",
     "text": "Подъём к Хомуту. Щит: «Перевал. Темп. Не стоять в низовом ветре».",
     "options": [
         {"id": "shelter", "label": "Укрыться за щитом", "result": "Переждал за щитом. Ветер слабее.",
          "flags": ["sheltered"]},
         {"id": "push", "label": "Идти", "result": "Пошёл. На Хомуте сразу занос, если темпа не будет.",
          "flags": ["pushed_blizzard"]}],
     "default": "shelter"},
    {"id": "e_khomut", "step": 11000, "type": "choice", "settlement": "khomut",
     "title": "Перевал «Хомут»",
     "text": "Седловина узкая. Флажок. Будка дорожника пустая. Нужна быстрая прогулка — иначе занос.",
     "options": [
         {"id": "burst", "label": "Темп (burst)", "result": "Прошёл 11 000→12 500. Флажок «открыто». В будке помета: «По чт ветер слабее».",
          "flags": ["khomut_ok"], "trust": {"gar": 1}},
         {"id": "wait", "label": "Ждать / обход", "result": "Занос. Обход низом по осыпи ~+1 800. Писем на обходе нет.",
          "flags": ["khomut_detour"]}],
     "default": "burst"},
    {"id": "arrive_repka", "step": 15500, "type": "scene", "settlement": "repka",
     "title": "Радиореле «Репка»",
     "text": "Мачта, будка на крючке. Из динамика сыплется глина. Гул как у холодильника — громче, чем в Долине.",
     "lines": [line("", "Служебный ящик пуст. Записка: «не работает с осени»."),
               line("", "Ночью в пустом окне жёлтый дежурный свет.", "")]},
    {"id": "e_krivulya_tempo", "step": 18500, "type": "choice", "settlement": "krivulya",
     "title": "Прижим",
     "text": "Кривуля. Тропа в полкорпуса. Короткий занос на прижиме.",
     "options": [
         {"id": "burst", "label": "Темп", "result": "Проскочил прижим. Верёвочные поручни скрипят."},
         {"id": "wait", "label": "Ждать", "result": "Обход длиннее ~+1 200. Туман снизу.",
          "flags": ["krivulya_detour"]}],
     "default": "burst"},
    {"id": "p_l9", "step": 20000, "type": "pickup", "settlement": "krivulya", "item": "l9",
     "title": "Вечерний звон",
     "text": "С подветренной стороны — колокол Звонарни. Ритм ровный, длинный. В ящике / оказии — телеграмма почтальону.",
     "lines": [line("", "Телеграмма Пимена: «ДВА СОРОК ТЧК ЛАМПА ТЧК ЗАПИСАЛ ТЧК».", "inPocket:l9"),
               line("", "Звон «на помин» — без подписи. Кто знает Морзе, может позже сопоставить.", "")]},
    {"id": "s_bell", "step": 20050, "type": "scene", "settlement": "krivulya",
     "lines": [line("", "Вечерний звон доносится с Долины. Счёт без слов."),
               line("", "С собой телеграмма Пимена про лампу.", "inPocket:l9")]},
    # Counter-mail results appear as scenes/pickups after Thursday (approx day2+)
    {"id": "p_l3", "step": 7200, "type": "pickup", "settlement": "penki", "item": "l3",
     "title": "Оказия вверх",
     "text": "После четверга: в оказии / ящике — ответ Мити Вере. Предохранитель сгорел.",
     "lines": [line("", "Письмо Мити: предохранитель СГОРЕЛ.", "inBag:l3"),
               line("", "Письмо Мити не влезло.", "left:l3")]},
    {"id": "p_l4", "step": 7400, "type": "pickup", "settlement": "penki", "item": "l4",
     "lines": [line("", "От Кузьмы Мите: батарейка. «Играл до петухов».", "inBag:l4"),
               line("", "Письмо Кузьмы не влезло.", "left:l4")]},
    {"id": "p_l5", "step": 7600, "type": "pickup", "settlement": "penki", "item": "l5",
     "lines": [line("", "От Пимена Мите: колокольню не дам. По четвергам тем более. Морзе во вложении.", "inBag:l5"),
               line("", "Письмо Пимена не влезло.", "left:l5")]},
    {"id": "p_l6", "step": 14000, "type": "pickup", "settlement": "repka", "item": "l6",
     "lines": [line("", "Митя снова слышит эфир. Журнал 7,3 — в чт тише.", "inBag:l6"),
               line("", "Журнал Мити не влез.", "left:l6")]},
    {"id": "p_l7", "step": 14200, "type": "pickup", "settlement": "repka", "item": "l7",
     "lines": [line("", "Ящик №2 / оказия: «от Тимы» Нине. Фантик-ёлочка. «Работаю на радиостанции».", "inBag:l7"),
               line("", "Письмо «от Тимы» не влезло.", "left:l7")]},
    {"id": "p_l8", "step": 16800, "type": "pickup", "settlement": "krivulya", "item": "l8",
     "lines": [line("", "Кузьма Вере. Смола. Зарубка 44.", "inBag:l8"),
               line("", "Секретное Кузьмы не влезло.", "left:l8")]},
    {"id": "finale", "step": 25000, "type": "finale", "settlement": "gorlovina",
     "lines": [line("", "Яр «Горловина». Тропа ныряет вниз. Сырой пластилин впереди — гл.3."),
               line("", "Пары пустых сапог по краям яра. В пластилине — один чистый конверт без марки."),
               line("", "Можно скроллом проверить, ушли ли «нижние» письма с четвергом.", "")]},
]

# sort events by step for engine
events.sort(key=lambda e: (e["step"], e["id"]))

CHOICE_DEFAULTS = {
    "e_windfall": ("climb", "Почтальон перелез через ствол — сумка зацепилась за лапу ели."),
    "e_blizzard": ("shelter", "Почтальон встал за щит и переждал метель."),
    "e_khomut": ("burst", "Почтальон набрал темп и прошёл Хомут до заноса."),
    "e_krivulya_tempo": ("burst", "Почтальон проскочил прижим без обхода."),
}
PUSH = {
    "p_l1": [line("", "Седло. В выемке — письмо Нине и записка А.Л.", "inBag:l1")],
    "e_windfall": [line("", "Ельник «Лапы». Ветровал поперёк дороги.", "")],
    "arrive_gar": [line("", "Кордон «Гарь». Лесник чинит калитку.", "")],
    "arrive_penki": [line("", "Пеньки. Бригадир у костра: консервы на свечи.", "")],
    "e_khomut": [line("", "Хомут. Перевал. Нужна быстрая прогулка.", "")],
    "arrive_repka": [line("", "Репка. Из динамика сыплется глина.", "")],
    "p_l9": [line("", "Кривуля. Звон с Долины. Телеграмма: «ДВА СОРОК».", "")],
    "finale": [line("", "Горловина. Дорога уходит к болотам.", "")],
}
for ev in events:
    if ev["id"] in CHOICE_DEFAULTS:
        default, auto = CHOICE_DEFAULTS[ev["id"]]
        ev["default"] = default
        for opt in ev.get("options") or []:
            if opt["id"] == default:
                opt["auto"] = auto
    if ev["id"] in PUSH:
        ev["push"] = PUSH[ev["id"]]

quests = [
    {"telegram": "Забрать письмо 1 из выемки на Седле", "event": "p_l1"},
    {"telegram": "Письма для нижней долины останутся в ящике НИИ", "event": "s_nii_drop", "if": "inBag:l1"},
    {"telegram": "Дойти до Кордона «Гарь»", "event": "arrive_gar"},
    {"telegram": "До Пеньков · ночёвка", "event": "arrive_penki"},
    {"telegram": "Перевал Хомут — темп", "event": "e_khomut"},
    {"telegram": "До Репки", "event": "arrive_repka"},
    {"telegram": "Кривуля · звон", "event": "p_l9"},
    {"telegram": "К Горловине", "event": "finale"},
]

residents = [
    {"id": "lesnik", "name": "Лесник", "aliases": ["lesnik", "лесник", "ranger"], "step": 2800, "dx": 280, "height": 400},
    {"id": "brigadir", "name": "Бригадир", "aliases": ["brigadir", "бригадир"], "step": 6500, "dx": 320, "height": 420},
    {"id": "penki_worker", "name": "Рабочий", "aliases": ["penki_worker", "рабочий"], "step": 6600, "dx": 520, "height": 380},
]

fates = [
    {"settlement": "sedlo", "if": "inBag:l1", "text": "Письмо Тимофея из мешка ещё в сумке — Нине через Веру не ушло."},
    {"settlement": "sedlo", "if": "delivered:l1", "text": "Письмо Тимофея оставлено «для нижних» / ушло с Верой."},
    {"settlement": "gar", "if": "inPocket:note_gar", "text": "Записка лесника с собой — в будку на Хомуте."},
    {"settlement": "khomut", "if": "flag:khomut_ok", "text": "Хомут пройден темпом."},
    {"settlement": "khomut", "if": "flag:khomut_detour", "text": "Хомут обойдён низом — писем на обходе нет."},
    {"settlement": "krivulya", "if": "inPocket:l9", "text": "Телеграмма Пимена: лампа погасла в 02:40."},
    {"settlement": "gorlovina", "if": "flag:khomut_ok", "text": "Дорога к болотам открыта. Гл.3 ждёт."},
]

ARRIVALS = [
    {"settlement": "sedlo", "text": "Седло. Ящик. За перевалом — ельник и туман."},
    {"settlement": "gar", "text": "Гарь. Чёрные стволы, две кружки, сторожка."},
    {"settlement": "penki", "text": "Пеньки. Опилки, дымок, пни-дома."},
    {"settlement": "khomut", "text": "Хомут. Два склона как клещи. Ветер."},
    {"settlement": "repka", "text": "Репка. Мачта. Гул."},
    {"settlement": "krivulya", "text": "Кривуля. Прижим. Туман снизу."},
    {"settlement": "gorlovina", "text": "Горловина. Сырой пластилин впереди."},
]

story = {
    "_comment": "Сгенерировано tools/build_chapter2_story.py. Письма — дословно из letters-ch2.md. "
                "События/реплики — draft по chapter2-timeline.md. Шаги от Седла (гл.2).",
    "chapter": 2, "slots": 3,
    "days": [
        {"day": 1, "from": 0, "to": 7500},
        {"day": 2, "from": 7500, "to": 15000},
        {"day": 3, "from": 15000, "to": 22500},
        {"day": 4, "from": 22500, "to": 25000},
    ],
    "items": items, "events": events, "quests": quests, "residents": residents, "fates": fates,
    "finaleTitle": "Глава 2 · Горы", "finaleSubtitle": "пройдена", "nextChapter": "Глава 3 «Болота»",
    "trustSettlements": ["gar", "penki", "khomut"],
    "choicePolicy": {"mode": "notifyThenAuto", "timeoutSteps": 400},
    "arrivals": ARRIVALS,
    "sortDefault": [],
    "sortAuto": "",
}

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(story, fh, ensure_ascii=False, indent=1)
print("wrote", OUT, len(items), "items", len(events), "events", len(residents), "residents")
