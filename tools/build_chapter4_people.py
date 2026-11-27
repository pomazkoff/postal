#!/usr/bin/env python3
"""Chapter 4 people pass (on top of chapter4_story.json): own resident ids and lore for
Kolya, Pavel, Nyura (Stvor) and Agnia (Stvor), choices tied to them, the e_address fix,
Agnia's scene and the storeroom, finds handed to people, and the wet envelope from chapter 3.
Idempotent: run again and the result is the same. RU copy here, EN in L10n/en.json."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "Postman/GameAssets/Data"
EN = ROOT / "Postman/GameAssets/L10n/en.json"

def L(text, who="", cond=None):
    d = {"who": who, "text": text}
    if cond:
        d["if"] = cond
    return d

RESIDENTS = [
    # id, name, aliases, step
    ("kolya", "Коля", ["kolya", "коля", "сторож"], 4000),
    ("pavel", "Павел", ["pavel", "павел", "кочегар"], 23000),
    ("nyura_stvor", "Нюра", ["nyura_stvor", "нюра", "соседка"], 36500),
    ("agnia_stvor", "Агния", ["agnia_stvor", "агния", "а.л.", "ворсина"], 39500),
]
EN_NAMES = {"kolya": "Kolya", "pavel": "Pavel", "nyura_stvor": "Nyura", "agnia_stvor": "Agnia"}

LORE = {
    "kolya": ("Сторож Коля", [
        "Задвижки обхожу. Они стоят, я хожу. Так и живём.",
        "По дамбе ходи. В пульпу — нет. Пульпа сапоги не отдаёт.",
    ]),
    "pavel": ("Кочегар Павел", [
        "Котёл один. Для верхних, чтоб не замёрзли.",
        "Сапоги на сушилку ставь. Утром спасибо скажешь. Не мне — ногам.",
    ]),
    "nyura_stvor": ("Соседка Нюра", [
        "Письма за соседей пишу. Кому ручку подержать, кому всё письмо.",
        "Калитку не толкай. Она с характером, вся в хозяйку.",
    ]),
    "agnia_stvor": ("Агния Львовна", [
        "Отделение работает. Часы приёма — пока я на ногах.",
        "Сумку не перегружайте. Береги ноги.",
    ]),
}
EN_LORE = {
    "kolya": ("Kolya the watchman", [
        "I walk the sluices. They stand, I walk. That is how we live.",
        "Walk the dike. Into the pulp — no. The pulp does not give boots back.",
    ]),
    "pavel": ("Pavel the stoker", [
        "One boiler. For the upper ones, so they do not freeze.",
        "Put your boots on the dryer. You will say thanks in the morning. Not to me — to your feet.",
    ]),
    "nyura_stvor": ("Nyura the neighbour", [
        "I write letters for the neighbours. For some I hold the pen, for some I write it all.",
        "Do not push the gate. It has a temper, just like its owner.",
    ]),
    "agnia_stvor": ("Agnia Lvovna", [
        "The branch is open. Hours of business — while I am on my feet.",
        "Do not overload the bag. Watch your feet.",
    ]),
}

CHOICE_RESIDENT = {"e_sluice": "kolya", "e_kotel": "pavel", "e_address": "nyura_stvor", "e_believe": "agnia_stvor"}

NEW_EVENTS = [
    dict(id="s_kolya_dam", step=6500, type="scene", settlement="otstoyniki", resident="kolya",
         title="Дальняя дамба",
         text="Коля идёт с ключом по дальней дамбе. Собака впереди.",
         lines=[
             L("Опять ты. Дамба та же, я тот же. Собака тоже та же.", "Коля"),
             L("Бирку давай. Это с третьего пруда. Ключ мой, бирку всё равно таскают.", "Коля", "inBag:find_sluice"),
             L("А задвижка-то пошла. Без тебя, между прочим.", "Коля", "flag:sluice_left"),
         ],
         push=[L("Отстойники. Коля на дальней дамбе.")]),
    dict(id="s_nyura", step=36500, type="scene", settlement="dvory", resident="nyura_stvor",
         title="Нюра у калитки",
         text="Нюра сидит у калитки с тетрадкой. Пишет за соседей.",
         lines=[
             L("Почтальон? Садись на лавку. Калитку не трогай, она с характером.", "Нюра"),
             L("Обрывок бланка Нюра разглядывает долго, потом кивает.", "", "inPocket:find_blank"),
             L("Так и пишем: то я, то сосед. Рука путается.", "Нюра", "inPocket:find_blank"),
         ],
         push=[L("Дворы. Нюра у калитки.")]),
    dict(id="s_agnia", step=39550, type="scene", settlement="otdelenie", resident="agnia_stvor",
         title="Поешь сначала",
         text="За стойкой отделения женщина в вязаной кофте. Фиолетовый карандаш за ухом.",
         lines=[
             L("Уважаемый почтальон. Поешь сначала. Почта подождёт, она у нас привычная.", "Агния"),
             L("На стойке миска, ложка и бланк под миской. Почтальон ест. Агния пишет."),
             L("Корешок извещения Агния держит дольше обычного.", "", "inPocket:find_stub"),
             L("Корешки у нас хранятся. К работе.", "Агния", "inPocket:find_stub"),
             L("Бланк отделения. Приму к сведению.", "Агния", "inPocket:find_blank"),
             L("Поел? Кладовая за стойкой. Береги ноги.", "Агния"),
         ],
         push=[L("Отделение. А.Л. на стойке: «Поешь сначала».")]),
    dict(id="e_wet", step=40500, type="choice", settlement="otdelenie", resident="agnia_stvor",
         title="Мокрый конверт",
         text="В сумке мокрый конверт с Болот. Штемпель «Н. Створ».",
         requires="kept:find_wet",
         default="show",
         options=[
             {"id": "show", "label": "Показать конверт",
              "result": "Агния берёт конверт в работу. Ничего не объясняет.",
              "flags": ["wet_agnia"], "auto": "Почтальон показал конверт."},
             {"id": "keep", "label": "Оставить при себе",
              "result": "Конверт остаётся в сумке. Агния смотрит на штемпель и молчит.",
              "flags": ["wet_kept"]},
         ],
         push=[L("Мокрый конверт со штемпелем Створа. Показать А.Л.?")]),
    dict(id="s_kladovaya", step=39950, type="scene", settlement="otdelenie", resident="agnia_stvor",
         title="Кладовая",
         text="Дверь за стойкой. Агния открывает своим ключом и ключ не выпускает.",
         lines=[
             L("Задержанное. 3 (три) мешка. Почту у нас не жгут.", "Агния"),
             L("Бечёвка, сургуч, живые штемпели. Ключ у неё на шнурке."),
             L("Смотреть можно. Вскрывать — нет.", "Агния"),
         ],
         push=[L("Отделение. Агния открывает кладовую.")]),
]

EN_EVENTS = {
    "s_kolya_dam": {"title": "The far dike", "text": "Kolya walks the far dike with the key. The dog runs ahead.",
        "lines": [{"who": "Kolya", "text": "You again. Same dike, same me. Same dog too."},
                  {"who": "Kolya", "text": "Give me the tag. It is from the third pond. The key is mine, the tag always walks off."},
                  {"who": "Kolya", "text": "The sluice went, by the way. Without you."}],
        "push": [{"text": "The Settling Ponds. Kolya on the far dike."}]},
    "s_nyura": {"title": "Nyura at the gate", "text": "Nyura sits at the gate with an exercise book. She writes for the neighbours.",
        "lines": [{"who": "Nyura", "text": "The postman? Sit on the bench. Leave the gate, it has a temper."},
                  {"who": "", "text": "Nyura looks at the scrap of the form for a long time, then nods."},
                  {"who": "Nyura", "text": "That is how we write: now me, now the neighbour. The hand gets muddled."}],
        "push": [{"text": "The Yards. Nyura at the gate."}]},
    "s_agnia": {"title": "Eat first", "text": "Behind the branch counter, a woman in a knitted cardigan. A violet pencil behind her ear.",
        "lines": [{"who": "Agnia", "text": "Dear postman. Eat first. The mail will wait, it is used to it."},
                  {"who": "", "text": "On the counter: a bowl, a spoon and a form under the bowl. The postman eats. Agnia writes."},
                  {"who": "", "text": "Agnia holds the notice stub longer than usual."},
                  {"who": "Agnia", "text": "Stubs are kept here. Accepted for processing."},
                  {"who": "Agnia", "text": "A branch form. Noted."},
                  {"who": "Agnia", "text": "Eaten? The storeroom is behind the counter. Watch your feet."}],
        "push": [{"text": "The Branch. A.L. at the counter: “Eat first.”"}]},
    "e_wet": {"title": "The wet envelope", "text": "A wet envelope from the Marshes in the bag. Postmark “N. Stvor.”",
        "push": [{"text": "A wet envelope with the Stvor postmark. Show it to A.L.?"}],
        "options": {"show": {"label": "Show the envelope", "result": "Agnia takes the envelope for processing. She explains nothing.",
                             "auto": "The postman showed the envelope."},
                    "keep": {"label": "Keep it", "result": "The envelope stays in the bag. Agnia looks at the postmark and says nothing."}}},
    "s_kladovaya": {"title": "The storeroom", "text": "A door behind the counter. Agnia opens it with her own key and does not let go of it.",
        "lines": [{"who": "Agnia", "text": "Held mail. 3 (three) sacks. We do not burn mail here."},
                  {"who": "", "text": "String, sealing wax, live postmarks. The key hangs on a cord around her neck."},
                  {"who": "Agnia", "text": "You may look. Opening — no."}],
        "push": [{"text": "The Branch. Agnia opens the storeroom."}]},
}

def main():
    p = DATA / "chapter4_story.json"
    story = json.loads(p.read_text(encoding="utf-8"))
    # 1. residents with own ids (chapter 3 has its own Nyura, chapter 1 its own A.L.)
    old = {r["id"]: r for r in story["residents"]}
    remap = {"nyura": "nyura_stvor", "agnia": "agnia_stvor"}
    res = []
    for rid, name, aliases, step in RESIDENTS:
        base = old.get(rid) or old.get({v: k for k, v in remap.items()}.get(rid, rid)) or {}
        res.append({"id": rid, "name": name, "aliases": aliases, "step": step,
                    "dx": base.get("dx", 240), "height": base.get("height", 430), "sink": base.get("sink", 0)})
    story["residents"] = res
    events = [e for e in story["events"] if e["id"] not in {n["id"] for n in NEW_EVENTS}]
    by = {e["id"]: e for e in events}
    for eid, rid in CHOICE_RESIDENT.items():
        by[eid]["resident"] = rid
    # 2. e_address: only with the jar in the bag; only Nyura's answer delivers it there.
    ea = by["e_address"]
    ea["requires"] = "inBag:l5"
    ea["fallback"] = "Банки при себе нет. Нюра пожимает плечами: «Ну, не мне — так не мне»."
    for o in ea["options"]:
        if o["id"] == "nyura":
            o["effects"] = [{"item": "l5", "status": "delivered"}]
        else:
            o.pop("effects", None)
    do = by["d_otdelenie"]
    do["lines"] = [
        L("Письмо Нины можно оставить в ящике отделения, оказия вниз."),
        L("Банку леща Агния приняла до востребования. Отложила молча.", "", "inBag:l5,choice:e_address=office"),
        L("Банку леща оставили на стойке, «для Нюры».", "", "inBag:l5,!choice:e_address=office"),
    ]
    # 3. finale: «не ходи»
    by["finale"]["lines"] = [
        L("Дальше хода нет. Пост ещё впереди, в дымке."),
        L("На прощание А.Л. сказала: «Через оцепление не ходи. Почту носи. Береги ноги»."),
        L("Ключ от кладовой не выдан."),
    ]
    # keep the old order; each new event goes right after the event it follows on the road
    # a choice keeps its window: the next stop is ≥ 400 steps away (notifyThenAuto)
    after = {"s_kolya_dam": "p_l2", "s_nyura": "p_l7", "s_agnia": "d_otdelenie",
             "s_kladovaya": "s_agnia", "e_wet": "p_l9"}
    for n in NEW_EVENTS:
        i = next(k for k, e in enumerate(events) if e["id"] == after[n["id"]])
        events.insert(i + 1, dict(n))
    story["events"] = events
    p.write_text(json.dumps(story, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # lore
    lp = DATA / "resident_lore.json"
    lore = json.loads(lp.read_text(encoding="utf-8"))
    for rid, (title, lines) in LORE.items():
        lore[rid] = {"title": title, "lines": lines}
    lp.write_text(json.dumps(lore, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # EN
    en = json.loads(EN.read_text(encoding="utf-8"))
    s4 = en["stories"]["4"]
    s4["residents"] = dict(EN_NAMES)
    ev = s4["events"]
    for k, v in EN_EVENTS.items():
        ev[k] = v
    ea_en = ev["e_address"]
    ea_en["fallback"] = "No jar on hand. Nyura shrugs: “Well, not for me, then.”"
    ev["d_otdelenie"]["lines"] = [
        {"text": "Nina's letter can be left in the branch box, a chance downstream."},
        {"text": "Agnia took the jar of bream poste restante. Set it aside without a word."},
        {"text": "The jar of bream was left on the counter, “for Nyura.”"},
    ]
    ev["finale"]["lines"] = [
        {"text": "There is no road beyond. The post is still ahead, in the haze."},
        {"text": "At parting A.L. said: “Do not go through the cordon. Carry the mail. Watch your feet.”"},
        {"text": "The storeroom key has not been issued."},
    ]
    for rid, (title, lines) in EN_LORE.items():
        en["lore"][rid] = {"title": title, "lines": lines}
    EN.write_text(json.dumps(en, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("chapter 4 people pass:", len(events), "events,", [r["id"] for r in res])

if __name__ == "__main__":
    main()
