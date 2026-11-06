#!/usr/bin/env python3
"""Последствия выборов главы 1 (walking-sim/choices-plan-ch1.md, утверждён 2026-11-04).

Вызывается из build_chapter1_story.py перед записью json; можно запустить и отдельно —
патчит Postman/GameAssets/Data/chapter1_story.json на месте (идемпотентно).
Тексты — ЧЕРНОВИК (имя «Матрёна» не утверждено).
"""
import json, os

def L(who, text, cond=""):
    d = {"who": who, "text": text}
    if cond:
        d["if"] = cond
    return d

def apply(story):
    ev = {e["id"]: e for e in story["events"]}

    # 2.1 Тачка: флаги и отдача у Нины.
    cart = ev["e_cart"]
    for o in cart["options"]:
        o["flags"] = ["cart_helped"] if o["id"] == "help" else ["cart_bypassed"]
    nina = ev["s_nina"]
    nina["lines"] = [l for l in nina["lines"] if "cart_" not in (l.get("if") or "")]
    nina["lines"][1:1] = [
        L("Нина", "Кочерыжку Матрёна передала? Значит, вытащили. Спасибо, сынок.", "flag:cart_helped"),
        L("Нина", "Матрёна говорит, почтальон мимо прошёл. Ну, у почты ноги казённые.", "flag:cart_bypassed"),
    ]

    # 2.2 Рамка: спутник 4500→13200 и строчки на пути.
    ramka = ev["e_ramka"]
    ramka["companion"] = {"id": "ramka", "from": 4500, "to": 13200, "if": "flag:ramka"}
    d_l2 = ev["d_l2"]
    d_l2["lines"] = [l for l in d_l2["lines"] if l.get("if") != "flag:ramka,delivered:l2"]
    d_l2["lines"].append(L("Пимен", "Козу-то чью ведёшь? НИИшная. Вера её по уху узнает.", "flag:ramka,delivered:l2"))
    p_l6 = ev["p_l6"]
    p_l6["lines"] = [l for l in p_l6["lines"] if l.get("if") != "flag:ramka"]
    p_l6["lines"].append(L("", "Рамка съела у колодца полведра ботвы. Никто не возражал.", "flag:ramka"))

    # 3. Гроза — атмосферная сцена без выбора (флаг hum в запас).
    storm = ev["e_storm"]
    for k in ("options", "default"):
        storm.pop(k, None)
    storm["type"] = "scene"
    storm["text"] = ("Над ручьём гремит. Почтальон пережидает в будке турбины. "
                     "Внутри гудит громче, чем снаружи, ровно, будто не от воды.")
    storm["flags"] = ["hum"]
    storm["lines"] = [L("", "Рамка встала у будки и дальше не идёт.", "flag:ramka")]
    storm["push"] = [L("", "Гроза у НИИ. Переждал в будке турбины. Гудит.")]

    # 2.3 Ветер: условная записка А.Л. и строка в финале.
    for it in story["items"]:
        if it["id"] == "l7":
            it["notes"] = [L("", "Уважаемый почтальон! Выемку произвела. Отправление Колобовой Н.А. не поступило. "
                                 "Следующая выемка — четверг. Береги ноги. А.Л.", "lost:l3")]
    fin = ev["finale"]
    fin["lines"] = [l for l in fin["lines"] if l.get("if") != "sent:l3,choice:e_wind=chase"]
    i = next((n for n, l in enumerate(fin["lines"]) if l.get("if") == "sent:l3"), len(fin["lines"]) - 1)
    fin["lines"].insert(i + 1, L("", "Конверт в грязи, но носки сухие.", "sent:l3,choice:e_wind=chase"))

    # 4. Финал: по строке на каждый выбор.
    fates = [f for f in story["fates"] if f["if"] not in ("flag:cart_helped", "flag:cart_bypassed", "!flag:ramka")]
    def insert_after(settlement, items):
        idx = max((n for n, f in enumerate(fates) if f["settlement"] == settlement), default=len(fates) - 1)
        for k, f in enumerate(items):
            fates.insert(idx + 1 + k, f)
    insert_after("svai", [
        {"settlement": "svai", "if": "flag:cart_helped", "text": "Старухе с тачкой — помог. Нина получила поклон с кочерыжкой."},
        {"settlement": "svai", "if": "flag:cart_bypassed", "text": "Тачку обошёл. Кадушки об этом узнали раньше тебя."},
    ])
    insert_after("nii", [
        {"settlement": "nii", "if": "!flag:ramka", "text": "Рамку согнал. Домой дошла сама, переночевала в антенне."},
    ])
    story["fates"] = fates
    return story

if __name__ == "__main__":
    path = os.path.join(os.path.dirname(__file__), "..", "Postman", "GameAssets", "Data", "chapter1_story.json")
    with open(path, encoding="utf-8") as fh:
        story = json.load(fh)
    apply(story)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(story, fh, ensure_ascii=False, indent=1)
    print("patched", path)
