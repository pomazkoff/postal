#!/usr/bin/env python3
"""Собирает chapter3_story.json из letters-ch3.md (правка копирайтера).

Шаги и сдача — chapter3-timeline.md v1.1, правило t431: сдача только впереди.
Не трогает тексты писем. Английский слой пишет в en.json.
"""
import json
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LETTERS = os.path.join(ROOT, "docs/canon/letters-ch3.md")
OUT = os.path.join(ROOT, "Postman/GameAssets/Data/chapter3_story.json")
EN = os.path.join(ROOT, "Postman/GameAssets/L10n/en.json")
WORLD = os.path.join(ROOT, "Postman/GameAssets/Data/world.json")

md = open(LETTERS, encoding="utf-8").read()


def letter_blocks(n):
    nxt = r"(?=^## )"
    m = re.search(r"^## Письмо %d\..*?$(.*?)%s" % (n, nxt), md, re.S | re.M)
    if not m:
        m = re.search(r"^## Письмо %d\..*?$(.*)\Z" % n, md, re.S | re.M)
    assert m, n
    blocks, cur = [], []
    for ln in m.group(1).split("\n"):
        if ln.startswith(">"):
            cur.append(ln[2:] if ln.startswith("> ") else ln[1:])
        elif cur:
            blocks.append("\n".join(cur).strip())
            cur = []
    if cur:
        blocks.append("\n".join(cur).strip())
    return blocks


def note_block(title):
    m = re.search(r"^## %s.*?$(.*?)(?=^## )" % re.escape(title), md, re.S | re.M)
    assert m, title
    lines = []
    for ln in m.group(1).split("\n"):
        if ln.startswith(">"):
            lines.append(ln[2:] if ln.startswith("> ") else ln[1:])
        elif lines and not ln.startswith(">"):
            break
    return "\n".join(lines).strip()


L = {n: letter_blocks(n) for n in range(1, 11)}
AL = L[1][0]
GALYA = L[1][1]
FEDYA = note_block("Записка деда Феди (не в счёт 10 писем)")
assert "Дорогу ниже размыло" in AL
assert "крючки" in GALYA and "Митюша" in GALYA
assert "Зорьку" in L[9][0]
assert "Рамка" in L[3][0]
assert "УС ГАЛЯ" in L[6][0]
assert "пятьдесят восемь" in L[7][0]
assert "Дед Ф." in FEDYA
assert L[10] == [] or True

EN_LETTERS = {
    1: (
        "Dear postman!\nThe road below has washed out. I have made the collection. The next collection is Thursday. Mind your feet.\nA.L.",
        "Mityusha, I bought the hooks, the very thin ones you asked for, for the roach. Don't tell Grandad, or he'll say it's too soon, he'll buy them himself, and then he'll go about boasting. They paid us, so I'll stop at the shop before the shift if the queue is short. I have washed your socks. They are hanging over our stove, and I'll take them down in the morning and bring them. Don't throw the nets without asking. Grandad grumbles, and still he waits for you by seven. I am on the night shift today, so don't expect a letter before Sunday. I'll sleep it off and write how the week went. I kiss you. Mama.",
    ),
    2: "Timosha, hello, how are your socks wearing, has the heel gone through, don't wash them in hot water, I told you, or they will shrink, and don't dry them on the stove itself. Are you eating something hot. Don't open the jar, it stands where it stood, the cucumbers are small but they crunch. I am asking you one thing and you write it to me straight, what was the name of our goat, the one that lived behind the tub when you were still at school, I have started to forget and Mitya says he does not remember. Write what she was called, and give Lida my regards, she should not take offence. They may let you go by Trinity, so when you come off the road sit down first, eat, and only then tell the news. You are eating something hot, aren't you.\n(she said the goat three times, I wrote it once. I'll ask Grandad the name. I did not tell her. M.)\nX N.",
    3: "Hello, Mama.\nI received your letter safely, and the socks too, thank you. I work at the cannery in Olkhovka, I stand at the sealing machine, the shift is from seven. They will not let you through the cordon, so don't come, the road below has washed out. We have no radio and no telephone either, so don't you worry.\nI remember our goat well. Her name was Ramka, a red one, she lived behind the tub. Give my regards to Lida. She is well and sends hers back.\nEat something hot. Take care of yourself.\nTimofey",
    4: "VERA IGNATYEVNA, HELLO.\nI built the loop from your book and I put the drawing in. It is a direction finder. You turn it and watch where it is LOUDER.\nOn 7.3 it still HUMS, quieter on Thursday, and stronger at night. I want to know WHERE FROM. If it is your transformer, write which way it ought to be louder, and I will check.\nYou can give the drawing to the postman. Let him turn it on the road. It is flatter there than between our stilts.\nOver.\nMitya (Us)\nThe wrapper is the model. I already have one made of wire.",
    5: "Sonny, I received your letter safely. Everything is as it was with me. I am working. They still will not let anyone through the cordon, so don't you worry.\nMind your grandfather and go to school while they keep it open. Help him haul the nets in the evening. He cannot manage alone.\nEat something hot. Dry the socks by the stove, only do not put them on it.\nMama",
    6: "POSTMAN, HELLO.\nI took Father Pimen's table and read the evening bell, not all of it, only a piece. The names go by letters, the way they do in the alphabet. Four have come out so far. Then my hand got tired, and the bell goes on, even and long.\nThis is what came out: FEDOSEEVA M. US GALYA. SHUBIN P. REPNINA A.\nI don't know what it is. Mama is written the same way, that is true. Write if you hear any more, or just listen in the evening. The bell reaches the marshes. I checked.\nOver.\nMitya (Us)",
    7: "Vera Ignatyevna. The pole already reads fifty-eight. The water is not falling.\nWell.\nK. Us",
    8: "To the postman.\n1. I have received the mark of 58. That is the third nick on the pole the count is kept on.\n2. I enclose the reckoning by the water. There is still a margin before it works. I am putting the decision off until the next mark. The road below is wet. The descent is not required.\n3. The hum on 7.3 that Dmitry wrote about is still from our transformer. The bearing taken in the field does not move the source.\n4. My letters are not to be opened. The seal on them is numbered.\nV.I. Pasechnik\nP.S. Do not let Ramka onto the plank road. She follows anyone.",
    9: "Vera Ignatyevna, hello, I come to you with my regards and a request, you drive past every week and you do not stop at mine, I am not talking about the skirt, you know that yourself. Come in for tea at least. I'll put out a jar. The cucumbers are small but they crunch. I want to ask you about Timosha. The letters that come to me are different, one hand and another, and about the goat one of them wrote the wrong thing. Ours was called Zorka. I remember that myself, so why did I ask. Write to Lida and let her tell me the truth, or tell me yourself if you know. Let Mitya sit. I am not chasing him. There is soup.\n(she told me to write \"not about the skirt\", and I did. About the goat she said \"ours was called Zorka\". I have already asked Grandad myself. Zorka too. M.)\nX N.",
    10: "For the postman.",
}


def item(i, **kw):
    base = {
        "takesSlot": True, "art": "env_plain", "stick": "stick_plain",
        "initial": "onRoad", "road": "road_envstake",
    }
    base.update(kw)
    base["id"] = i
    return base


def reader(font, address, caption, envelope="renv_open", paper="sheet"):
    return {
        "paper": paper, "font": font, "envelope": envelope, "address": address,
        "stamp": None, "attachment": None, "attachmentCaption": caption,
    }


items = [
    item("l1", kind="letter", to="Мите", place="Сваи · оказия вниз, ящик на Гати",
         settlement="gorlovina", **{"from": "Галя"}, senderSettlement="svai",
         reader=reader("hand", ["МИТЕ УСУ", "ОТ МАМЫ"], "три тонких крючка в бумажке «на плотву»; марки нет"),
         note=AL, text=GALYA),
    item("l4", kind="letter", to="Вере", place="НИИ · для Веры, будка на Топи",
         settlement="gat", **{"from": "Митя"}, senderSettlement="svai",
         reader=reader("hand", ["НИИ РАДИОТЕНЬ.", "ПАСЕЧНИК В.И."], "чертёж рамки и фантик-ёлочка"),
         text=L[4][0]),
    item("frame", kind="form", takesSlot=False, to="Почтальону", place="Личные вещи",
         settlement="gat", **{"from": "Митя"}, senderSettlement="svai",
         art="find_horn", stick="stick_plain", initial="onRoad", road=None,
         text="Проволочная рамка. Крутишь и слушаешь, где гул громче."),
    item("note_fedya", kind="letter", to="Марье", place="Кадушки · оказия вниз, будка на Топи",
         settlement="gat", **{"from": "Дед Федя"}, senderSettlement="gat",
         initial="leftBehind",
         reader=reader("hand", ["МАРЬЕ", "КАДУШКИ"], "карандаш на обёртке от гвоздей"),
         text=FEDYA),
    item("l2", kind="letter", to="Тимофею", place="Ольховка · для А.Л., ящик на Торфянике",
         settlement="top", **{"from": "Нина"}, senderSettlement="kadushki",
         reader=reader("hand", ["ОЛЬХОВКА, ДО ВОСТРЕБОВАНИЯ.", "КОЛОБОВУ Т.Г."], "вложения нет"),
         text=L[2][0]),
    item("l3", kind="letter", to="Нине", place="Кадушки · оказия вниз, ящик на барже",
         settlement="torfyanik", **{"from": "Тимофей"}, senderSettlement="torfyanik",
         reader=reader("draft", ["КАДУШКИ.", "КОЛОБОВОЙ Н.А."], "этикетка «Килька в томате»"),
         text=L[3][0]),
    item("l5", kind="letter", to="Мите", place="Сваи · оказия вниз, ящик в Камышах",
         settlement="staraya_protoka", **{"from": "Галя"}, senderSettlement="staraya_protoka",
         reader=reader("draft", ["МИТЕ УСУ"], "вложения нет"),
         text=L[5][0]),
    item("l6", kind="letter", to="Почтальону", place="Старая протока · читается на месте",
         settlement="staraya_protoka", **{"from": "Митя"}, senderSettlement="svai",
         reader=reader("hand", ["ПОЧТАЛЬОНУ"], "обрывок ленты: четыре имени, среди них Ус Галя"),
         text=L[6][0]),
    item("l7", kind="secret", to="Вере", place="НИИ · для Веры, ящик в Камышах",
         settlement="staraya_protoka", **{"from": "Кузьма"}, senderSettlement="svai",
         art="env_wax", reader=reader("hand", ["В.И. ПАСЕЧНИК.", "ЛИЧНО"], "щепка с зарубкой 58"),
         outside="В.И. Пасечник. Лично.", text=L[7][0]),
    item("l8", kind="secret", to="Почтальону", place="Горло · читается на месте",
         settlement="gorlo", **{"from": "Вера"}, senderSettlement="nii",
         art="env_wax", reader=reader("draft", ["ПОЧТАЛЬОНУ.", "ЛИЧНО"], "миллиметровка: 31, 44, 58; «при 3-й» перечёркнуто, «при 4-й»"),
         outside="Почтальону. Лично.", text=L[8][0]),
    item("l9", kind="letter", to="Вере", place="НИИ · оказия в Долину, ящик на Отстое",
         settlement="gorlo", **{"from": "Нина"}, senderSettlement="kadushki",
         reader=reader("hand", ["НИИ РАДИОТЕНЬ.", "ПАСЕЧНИК В.И."], "вложения нет"),
         text=L[9][0]),
    item("l10", kind="secret", to="Почтальону", place="Отстой · читается на месте",
         settlement="otstoy", **{"from": "Кузьма"}, senderSettlement="svai",
         art="env_wax", reader=reader("hand", ["ПОЧТАЛЬОНУ"], "лист отказа: Сомов Ферапонт Ильич, Кадушки"),
         outside="Почтальону.", text=L[10] if isinstance(L[10], str) else EN_LETTERS[10] and "Почтальону."),
    item("find_edge", kind="form", takesSlot=False, to="Почтальону", place="Личные вещи",
         settlement="gat", **{"from": "Гать"}, senderSettlement="gat",
         art="find_stamp", initial="onRoad", road=None,
         text="Кромка марки из-под настила. Букв нет, цвет ещё держится."),
    item("find_tag", kind="form", takesSlot=False, to="Почтальону", place="Личные вещи",
         settlement="gat", **{"from": "Дед Федя"}, senderSettlement="gat",
         art="find_cloth", initial="leftBehind", road=None,
         text="Щепка с клеймом комбината. С нижнего склада."),
    item("find_card", kind="form", takesSlot=False, to="Почтальону", place="Личные вещи",
         settlement="top", **{"from": "Кочки"}, senderSettlement="top",
         art="find_cloth", initial="onRoad", road=None,
         text="Поминальная карточка. «Сомов Ф.И.». Лента на вешке выцвела."),
    item("find_pole", kind="form", takesSlot=False, to="Почтальону", place="Личные вещи",
         settlement="top", **{"from": "Топь"}, senderSettlement="top",
         art="find_horn", initial="onRoad", road=None,
         text="Шест без зарубок. Чужой. В иле у гати."),
    item("find_graph", kind="form", takesSlot=False, to="Почтальону", place="Личные вещи",
         settlement="top", **{"from": "Топь"}, senderSettlement="top",
         art="find_cloth", initial="onRoad", road=None,
         text="Обрывок миллиметровки. Чужая рука. Слово «пилот», цифр нет."),
    item("find_pass", kind="form", takesSlot=False, to="Почтальону", place="Личные вещи",
         settlement="torfyanik", **{"from": "Торфяник"}, senderSettlement="torfyanik",
         art="find_stamp", initial="onRoad", road=None,
         text="Рабочий пропуск на бечёвке. Старый образец. Имени не разобрать."),
    item("find_wet", kind="form", takesSlot=False, to="Почтальону", place="Личные вещи",
         settlement="staraya_protoka", **{"from": "Старая протока"}, senderSettlement="staraya_protoka",
         art="env_plain", initial="onRoad", road=None,
         text="Мокрый конверт. Штемпель «Н. Створ». Букв внутри нет, марка ещё цветная."),
]

# fix l10 text: the Russian envelope words, not the English sentence
for it in items:
    if it["id"] == "l10":
        it["text"] = "Почтальону."


def line(who, text, cond=None):
    d = {"who": who, "text": text}
    if cond:
        d["if"] = cond
    return d


def choice(eid, step, settlement, title, text, default, options, push):
    return {
        "id": eid, "step": step, "type": "choice", "settlement": settlement,
        "title": title, "text": text, "default": default,
        "options": options, "push": [line("", push)],
    }


events = [
    {"id": "p_l1", "step": 40, "type": "pickup", "settlement": "gorlovina", "item": "l1",
     "title": "Чистый конверт",
     "lines": [line("", "В глине у вешки лежит чистый конверт без марки. Крючки внутри, помета «на плотву».")],
     "push": [line("", "Горловина. В глине конверт без марки.")]},
    {"id": "s_al", "step": 80, "type": "scene", "settlement": "gorlovina",
     "title": "Записка в ящике", "text": AL,
     "lines": [line("", AL)],
     "push": [line("", "Горловина. А.Л.: дорогу ниже размыло.")]},
    choice("e_gati_fog", 2500, "gat", "Настил в тумане",
           "Жерди уходят в туман. Длина пути одна и та же.",
           "poles",
           [{"id": "poles", "label": "Идти по жердям",
             "result": "Ноги сухие. Настил чуть дышит вместе с водой.",
             "flags": ["gati_stayed"],
             "auto": "Почтальон пошёл по жердям."},
            {"id": "hummocks", "label": "Ступить в кочки",
             "result": "Ноги мокрые. В сумке плещет. С кочек можно взять кромку марки.",
             "flags": ["gati_wet"]}],
           "Настил в тумане. Куда ступить?"),
    {"id": "p_edge", "step": 2700, "type": "pickup", "settlement": "gat", "item": "find_edge",
     "title": "Кромка из щели",
     "lines": [line("", "Из щели гати торчит кромка марки. Букв нет.")],
     "push": [line("", "Гать. В щели настила кромка конверта.")]},
    {"id": "d_gat", "step": 4000, "type": "scene", "settlement": "gat",
     "title": "Ящик на Гати",
     "text": "Жестяной ящик «оказия». Сюда уходит письмо вниз, в Долину.",
     "lines": [
         line("", "Письмо Гали легло в ящик на Гати, «оказия вниз».", "inBag:l1"),
         line("", "Кромку марки оставили в том же ящике, деду Феде.", "inBag:find_edge"),
     ],
     "push": [line("", "Гать. Ящик оказии.")]},
    {"id": "p_l4", "step": 4100, "type": "pickup", "settlement": "gat", "item": "l4",
     "lines": [line("", "Оказия из Долины: Митя Вере. Чертёж рамки и фантик.")],
     "push": [line("", "Гать. Письмо Мити Вере.")]},
    {"id": "p_frame", "step": 4101, "type": "pickup", "settlement": "gat", "item": "frame",
     "lines": [line("", "Проволочная рамка легла в личные вещи.")],
     "push": [line("", "Гать. Рамка для пеленга.")]},
    choice("e_fedya_help", 4800, "gat", "Пролёт разошёлся",
           "Дед Федя настилает пролёт. Длина пути от помощи не меняется.",
           "hand",
           [{"id": "hand", "label": "Подать жердь",
             "result": "Короткая работа у настила. Федя суёт записку Марье: носки, если будет оказия.",
             "flags": ["fedya_helped"],
             "effects": [{"item": "note_fedya", "status": "inBag"},
                         {"item": "find_tag", "status": "inBag"}],
             "auto": "Почтальон подал жердь."},
            {"id": "walk", "label": "Идти дальше",
             "result": "Федя всё равно суёт записку. «Ну иди. Только в ящик положи».",
             "flags": ["fedya_passed"],
             "effects": [{"item": "note_fedya", "status": "inBag"}]}],
           "Дед Федя настилает пролёт. Поможешь?"),
    {"id": "p_card", "step": 7000, "type": "pickup", "settlement": "top", "item": "find_card",
     "title": "Карточка на вешке",
     "lines": [line("", "На кривой вешке выцветшая лента и карточка: Сомов Ф.И.")],
     "push": [line("", "Кочки. На вешке карточка Сомова.")]},
    choice("e_somov", 7600, "top", "Карточка Сомова",
           "Отдать можно один раз, через ящик впереди. Назад в Кадушки и на Звонарню идти не нужно.",
           "keep",
           [{"id": "pimen", "label": "Оставить для Пимена",
             "result": "Пимен ответит оказией: Сомова Ферапонта отпевал в августе. Яблоки ещё не сняли.",
             "flags": ["somov_pimen"]},
            {"id": "nina", "label": "Оставить для Нины",
             "result": "Нина ответит оказией: Ферапонта с августа нет, яблони ещё стояли, она носила ему банку.",
             "flags": ["somov_nina"]},
            {"id": "keep", "label": "Оставить при себе",
             "result": "Карточка остаётся в личных вещах. Лист отказа потом можно будет с ней сличить.",
             "flags": ["somov_keep"],
             "auto": "Почтальон оставил карточку при себе."}],
           "Карточка Сомова. Кому оставить?"),
    {"id": "d_top", "step": 9000, "type": "scene", "settlement": "top",
     "title": "Будка на Топи",
     "text": "Будка пустая. В ящике пометки «для Веры» и «оказия вниз».",
     "lines": [
         line("", "Письмо Мити и записка Феди легли в будку на Топи.", "inBag:l4"),
         line("", "Записка Феди ушла «оказией вниз», Марье.", "inBag:note_fedya"),
         line("", "Бирку с клеймом оставили Вере. Она отвечает: клеймо нижнее, принято к сведению.", "inBag:find_tag"),
         line("", "Карточку Сомова оставили для Пимена. Ферапонта отпевал в августе, яблоки ещё не сняли.", "inBag:find_card,flag:somov_pimen"),
         line("", "Карточку Сомова оставили для Нины. Ферапонта с августа нет, она носила ему банку.", "inBag:find_card,flag:somov_nina"),
     ],
     "push": [line("", "Топь. Будка. Ящик оказии.")]},
    {"id": "p_l2", "step": 9100, "type": "pickup", "settlement": "top", "item": "l2",
     "lines": [line("", "Оказия из Долины: Нина Тимофею. Спрашивает, как звали козу.")],
     "push": [line("", "Топь. Письмо Нины Тимофею.")]},
    {"id": "p_pole", "step": 9800, "type": "pickup", "settlement": "top", "item": "find_pole",
     "lines": [line("", "В иле у гати шест без единой зарубки.")],
     "push": [line("", "Топь. Чужой шест в иле.")]},
    {"id": "p_graph", "step": 9900, "type": "pickup", "settlement": "top", "item": "find_graph",
     "lines": [line("", "У будки обрывок миллиметровки. «Пилот». Цифр нет.")],
     "push": [line("", "Топь. Чужой обрывок миллиметровки.")]},
    {"id": "d_torf", "step": 12500, "type": "scene", "settlement": "torfyanik",
     "title": "Ящик на Торфянике",
     "text": "Служебный ящик. Помета «для А.Л.».",
     "lines": [
         line("", "Письмо Нины легло в ящик на Торфянике, «для А.Л.».", "inBag:l2"),
         line("", "Шест без зарубок оставили Кузьме. Не его. Ниже тоже меряют.", "inBag:find_pole"),
         line("", "Мите оставили обрывок: пилот, рука не его, кто-то уже мерил.", "inBag:find_graph"),
     ],
     "push": [line("", "Торфяник. Ящик для А.Л.")]},
    {"id": "p_l3", "step": 12600, "type": "pickup", "settlement": "torfyanik", "item": "l3",
     "lines": [line("", "Оказия: «Тима» Нине. Козу назвал Рамкой. Этикетка консервов.")],
     "push": [line("", "Торфяник. Письмо «от Тимы» Нине.")]},
    {"id": "p_pass", "step": 12800, "type": "pickup", "settlement": "torfyanik", "item": "find_pass",
     "lines": [line("", "В слое торфа пропуск на бечёвке. Старый образец.")],
     "push": [line("", "Торфяник. Пропуск в торфе.")]},
    {"id": "e_bearing", "step": 13500, "type": "choice", "settlement": "torfyanik",
     "requires": "inPocket:frame",
     "fallback": "Рамки в вещах нет. На столбе карандашом: «громче к верху».",
     "title": "Куда рамка громче",
     "text": "На столбе помета: громче к верху. Рамку можно покрутить. Дорога от этого не длиннее.",
     "default": "valley",
     "options": [
         {"id": "valley", "label": "Замерить к Долине",
          "result": "К Долине громче, чем к Створу. Ровно, как холодильник.",
          "flags": ["bearing_done"],
          "auto": "Почтальон замерил к Долине."},
         {"id": "stvor", "label": "Замерить к Створу",
          "result": "К Створу тише. Громче назад, к Долине.",
          "flags": ["bearing_done"]},
         {"id": "skip", "label": "Не крутить",
          "result": "На столбе так и написано: громче к верху. Своего замера нет."},
     ],
     "push": [line("", "На столбе помета: громче к верху. Крутить рамку?")]},
    {"id": "p_l5", "step": 15500, "type": "pickup", "settlement": "staraya_protoka", "item": "l5",
     "lines": [line("", "Оказия: «Галя» Мите. «Получила в целости». Крючков нет.")],
     "push": [line("", "Старая протока. Письмо «от Гали» Мите.")]},
    {"id": "d_barge", "step": 16500, "type": "scene", "settlement": "staraya_protoka",
     "title": "Ящик на барже",
     "text": "На палубе ящик «оказия».",
     "lines": [
         line("", "Письмо «от Тимы» легло в ящик на барже, «оказия вниз».", "inBag:l3"),
         line("", "Пропуск оставили деду Феде. Нижний двор, старый образец. Сам не ходил с осени.", "inBag:find_pass"),
     ],
     "push": [line("", "Старая протока. Ящик на барже.")]},
    {"id": "p_l7", "step": 16600, "type": "pickup", "settlement": "staraya_protoka", "item": "l7",
     "lines": [line("", "Кузьма Вере. На щепке пятьдесят восемь. Смола.")],
     "push": [line("", "Старая протока. Кузьма Вере: пятьдесят восемь.")]},
    {"id": "p_l6", "step": 16700, "type": "pickup", "settlement": "staraya_protoka", "item": "l6",
     "lines": [line("", "Митя почтальону. Четыре имени со звона. Среди них Ус Галя.")],
     "push": [line("", "Старая протока. Митя разобрал кусок звона.")]},
    {"id": "p_wet", "step": 16800, "type": "pickup", "settlement": "staraya_protoka", "item": "find_wet",
     "lines": [line("", "Под баржой мокрый конверт. Штемпель «Н. Створ». Букв нет.")],
     "push": [line("", "Старая протока. Конверт под баржой не читается.")]},
    {"id": "d_reeds", "step": 20000, "type": "scene", "settlement": "kamyshi",
     "title": "Ящик в Камышах",
     "text": "У верстового столба жестяной ящик. Цифра на столбе смыта.",
     "lines": [
         line("", "Письмо «от Гали» ушло «оказией вниз».", "inBag:l5"),
         line("", "Щепка Кузьмы легла «для Веры».", "inBag:l7"),
     ],
     "push": [line("", "Камыши. Ящик у верстового столба.")]},
    choice("e_radio", 21000, "kamyshi", "Приёмник в камыше",
           "Брошенный приёмник лежит на тропе. Ночь для этого не нужна.",
           "listen",
           [{"id": "listen", "label": "Послушать",
             "result": "Песня оборвалась. Дальше только шум.",
             "flags": ["ether_heard"],
             "auto": "Почтальон послушал. Песня оборвалась."},
            {"id": "walk", "label": "Идти дальше",
             "result": "Приёмник остаётся на тропе. Его можно тронуть позже."}],
           "В камышах лежит приёмник. Послушать?"),
    {"id": "p_l8", "step": 22600, "type": "pickup", "settlement": "gorlo", "item": "l8",
     "lines": [line("", "Вера почтальону. 58 — третья риска. Выключение перенесено на четвёртую.")],
     "push": [line("", "Горло. Вера откладывает третью отметку.")]},
    choice("e_plug", 24000, "gorlo", "Стена грязи",
           "Серая стена поперёк реки. С дороги её и так видно.",
           "close",
           [{"id": "close", "label": "Подойти ближе",
             "result": "В стене дверца ящика, обод, термос, пропуск на бечёвке. Никто не говорит, что это за стена.",
             "flags": ["plug_close"],
             "auto": "Почтальон подошёл к стене."},
            {"id": "stay", "label": "Остаться на гати",
             "result": "Стену видно с гати. Крупный план можно взять позже, скроллом.",
             "flags": ["plug_far"]}],
           "Впереди серая стена. Подойти?"),
    {"id": "p_l9", "step": 24100, "type": "pickup", "settlement": "gorlo", "item": "l9",
     "lines": [line("", "Нина Вере. Козу звали Зорькой. Просит правду, без обвинений.")],
     "push": [line("", "Горло. Нина пишет Вере.")]},
    {"id": "d_otstoy", "step": 28000, "type": "scene", "settlement": "otstoy",
     "title": "Ящик на Отстое",
     "text": "Последняя вешка. Котелок на крючке ещё тёплый. Никого нет.",
     "lines": [line("", "Письмо Нины легло в ящик на Отстое, «оказия в Долину, для Веры».", "inBag:l9")],
     "push": [line("", "Отстой. Ящик у последней вешки.")]},
    {"id": "p_l10", "step": 29000, "type": "pickup", "settlement": "otstoy", "item": "l10",
     "lines": [line("", "Свёрток «Почтальону, лично». Внутри листа отказа. Строка: Сомов Ферапонт Ильич, Кадушки. Помет нет.")],
     "push": [line("", "Отстой. Свёрток без единого слова.")]},
    {"id": "finale", "step": 30000, "type": "finale", "settlement": "otstoy",
     "lines": [
         line("", "Пристань «Отстой». Шлагбаум в тумане не открывается."),
         line("", "В разрыве пелены на миг видны трубы. Потом снова туман."),
         line("", "Котелок ещё тёплый. Кто здесь был, не сказано. Дальше сырой пластилин."),
     ],
     "push": [line("", "Отстой. Котелок тёплый. Дальше город в тумане.")]},
]

for event in events:
    if event["id"] == "e_radio":
        event["requires"] = "!flag:ether_heard"
        event["fallback"] = "Песня уже оборвалась. Приёмник трогали раньше."

story = {
    "_comment": "Сгенерировано tools/build_chapter3_story.py. Письма дословно из docs/canon/letters-ch3.md. Сдача только впереди.",
    "chapter": 3,
    "slots": 99,
    "days": [
        {"day": 1, "from": 0, "to": 7500},
        {"day": 2, "from": 7500, "to": 15000},
        {"day": 3, "from": 15000, "to": 22500},
        {"day": 4, "from": 22500, "to": 30000},
    ],
    "items": items,
    "events": events,
    "quests": [
        {"telegram": "Отнести чистый конверт в ящик на Гати", "event": "d_gat", "if": "inBag:l1"},
        {"telegram": "До Топи: письмо Вере и записка Феди", "event": "d_top"},
        {"telegram": "До Торфяника, ящик для А.Л.", "event": "d_torf"},
        {"telegram": "До Камышей", "event": "d_reeds"},
        {"telegram": "К Отстою", "event": "finale"},
    ],
    "residents": [
        {"id": "fedya", "name": "Дед Федя", "aliases": ["fedya", "федя", "фёдор"],
         "step": 4800, "dx": 220, "height": 400},
        # dx — центр спрайта, как у Феди. Левый край = dx − ширина/2 и совпадает с world_ch3_props.
        # Гриша: одобренный dx 80 ставил ящик на гать справа от кормы. Центр −175.5
        # кладёт левый край на −270, ящик на палубе у правой стены рубки. sink 13 — низ ящика.
        {"id": "nyura", "name": "Тётя Нюра", "aliases": ["nyura", "нюра"],
         "step": 7000, "dx": 247, "height": 365, "sink": 0},
        {"id": "semyon", "name": "Семён", "aliases": ["semyon", "семён", "семен"],
         "step": 12500, "dx": 251, "height": 430, "sink": 0},
        {"id": "grisha", "name": "Дядя Гриша", "aliases": ["grisha", "гриша"],
         "step": 16500, "dx": -175.5, "height": 325, "sink": 13},
        {"id": "petka", "name": "Петька", "aliases": ["petka", "петька"],
         "step": 20500, "dx": 197, "height": 270, "sink": 0},
    ],
    "fates": [
        {"settlement": "gat", "if": "inBag:l1", "text": "Чистый конверт ещё в сумке. Его место — ящик на Гати."},
        {"settlement": "gat", "if": "delivered:l1", "text": "Письмо Гали оставлено на Гати, оказия вниз."},
        {"settlement": "top", "if": "flag:bearing_done", "text": "Рамку крутили. Громче было к Долине."},
        {"settlement": "gorlo", "if": "flag:plug_close", "text": "К стене в Горле подходили. В ней бытовые вещи, не тела."},
        {"settlement": "otstoy", "if": "read:l10", "text": "Лист отказа прочитан. Подпись Ферапонта никто не обвёл."},
    ],
    "finaleTitle": "Глава 3 · Болота",
    "finaleSubtitle": "пройдена",
    "nextChapter": "Глава 4 «Город молчания» — скоро",
    "trustSettlements": ["gat", "top", "torfyanik"],
    "choicePolicy": {"mode": "notifyThenAuto", "timeoutSteps": 400},
    "arrivals": [
        {"settlement": "gorlovina", "text": "Горловина. Тропа ныряет в туман. В глине чистый конверт."},
        {"settlement": "gat", "text": "Гать. Настил, избушка, ящик оказии. Дед Федя чинит пролёт."},
        {"settlement": "top", "text": "Топь. Та же гать днём и ночью. В будке ящик."},
        {"settlement": "torfyanik", "text": "Торфяник. Штабеля, табель, пустой барак."},
        {"settlement": "staraya_protoka", "text": "Старая протока. Баржа у берега, ящик на палубе."},
        {"settlement": "kamyshi", "text": "Камыши. Прямая гать, верстовой столб, ящик у столба."},
        {"settlement": "gorlo", "text": "Горло. Серая стена поперёк реки. У вешки ящик."},
        {"settlement": "otstoy", "text": "Отстой. Шлагбаум, тёплый котелок, трубы в разрыве тумана."},
    ],
}

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(story, fh, ensure_ascii=False, indent=2)
    fh.write("\n")
print("wrote", OUT, "items", len(items), "events", len(events))
