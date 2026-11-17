#!/usr/bin/env python3
"""Глава 1: связные фразы не подменяют факты, шифры и механику.

19 пар сверены с главой. Сомнительные места поправлены по исходному смыслу
и должны стоять в тексте именно так. Глава 2 не трогалась.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
story = json.loads((ROOT / "Postman/GameAssets/Data/chapter1_story.json").read_text(encoding="utf-8"))
en = json.loads((ROOT / "Postman/GameAssets/L10n/en.json").read_text(encoding="utf-8"))
events = {e["id"]: e for e in story["events"]}
en_events = en["stories"]["1"]["events"]
FAILS = []


def fail(msg):
    FAILS.append(msg)


def opt(event, oid, field="result"):
    for item in event.get("options") or []:
        if item["id"] == oid:
            return item[field]
    fail(f"missing option {oid}")
    return ""


expect_ru = {
    ("e_cart", "text"): "Тачка с капустой съехала колесом в канаву и встала поперёк дороги. Рядом стоит старуха из Кадушек и держит оглоблю.",
    ("e_cart", "help"): "Почтальон со старухой вытащили тачку из канавы. Старуха сунула в сумку кочерыжку и сказала: «Нине поклон».",
    ("e_cart", "around"): "Почтальон обошёл тачку по меже. За спиной ещё долго ругали колесо.",
    ("e_animal_rooster", "text"): "Петух у мостков вытянул шею и смотрит на сумку. Он вот-вот закричит.",
    ("e_ramka", "text"): "На подъёме за пасекой стоит коза и жуёт кипрей. На левом ухе у неё надрез.",
    ("e_ramka", "lead"): "Почтальон пошёл вверх, и коза пошла следом. Она не отстаёт.",
    ("e_ramka", "chase"): "Почтальон махнул сумкой. Коза отошла к ульям и смотрит ему вслед.",
    ("e_animal_cat", "twine"): "Кошка отобрала бечёвку, уселась на неё и отвернулась. Бочка теперь тоже её.",
    ("e_animal_cat", "look"): "Кошка спрыгнула с бочки. Под бочкой лежит латунный штемпель без ручки, и он поместился в кармане.",
    ("e_storm", "text"): "Над ручьём гремит, и почтальон пережидает грозу в будке турбины. Внутри гудит громче, чем снаружи, — ровно, будто не от воды.",
    ("e_animal_goat_kid", "feed"): "Козлёнок схрумкал корку и теперь ждёт у калитки. Он проводит почтальона за НИИ и обратно к антенне.",
    ("e_animal_matrena", "text"): "К сумке подошла коза с зарубкой на ухе, как у Рамки. Только сама коза старше и шире.",
    ("e_animal_matrena", "hand"): "Матрёна обнюхала пальцы и боднула сумку. Внутри одна бумага, есть нечего, так что она ушла.",
    ("e_animal_matrena_jealous", "text"): "Рамка уже стоит у загона. Матрёна заметила, как та смотрит вслед почтальону, боднула сумку и встала поперёк тропы. Она ревнует.",
    ("e_animal_matrena_jealous", "greens"): "Матрёна занялась ботвой, и тропа освободилась. Рамка делает вид, что не смотрит.",
    ("e_animal_matrena_jealous", "chase"): "Почтальон махнул рукой. Матрёна отступила, напоследок боднула сумку и пропустила его.",
    ("e_wind", "text"): "На серпантине ветер рвёт клапан сумки, и пухлый конверт летит вниз, к отбойнику. Догонять?",
}
expect_en = {
    ("e_cart", "text"): "A barrow of cabbage has slid one wheel into the ditch and ended up across the road. An old woman from the Tubs stands beside it, holding the shaft.",
    ("e_cart", "help"): "The postman and the old woman hauled the barrow out of the ditch. She tucked a cabbage stump into the bag and said, “Regards to Nina.”",
    ("e_cart", "around"): "The postman went around the barrow along the boundary. Behind him, they kept scolding the wheel for a long while.",
    ("e_animal_cat", "look"): "The cat jumped off the barrel. Under the barrel lies a brass stamp with no handle, and it fit in the pocket.",
    ("e_animal_goat_kid", "feed"): "The kid crunched up the crust and is now waiting by the gate. He walks the postman past the Institute and back to the antenna.",
    ("e_wind", "text"): "On the switchbacks the wind tears at the bag's flap, and a fat envelope flies down toward the barrier. Go after it?",
}

def ru_value(eid, field):
    ev = events[eid]
    if field == "text":
        return ev["text"]
    return opt(ev, field)

def en_value(eid, field):
    ev = en_events[eid]
    if field == "text":
        return ev["text"]
    return ev["options"][field]["result"]

for key, text in expect_ru.items():
    if ru_value(*key) != text:
        fail(f"RU {key} drifted")
for key, text in expect_en.items():
    if en_value(*key) != text:
        fail(f"EN {key} drifted")

# Сомнительные формулировки черновика не должны пройти.
blob = json.dumps(story, ensure_ascii=False) + json.dumps(en, ensure_ascii=False)
for banned in ("Судя по всему", "By the looks of it", "вернётся к антенне", "Под ней лежит", "field edge", "wandered off", "broader"):
    if banned in blob:
        fail(f"rejected wording still present: {banned}")

# Шифры и орфография писем.
raw = (ROOT / "Postman/GameAssets/Data/chapter1_story.json").read_text(encoding="utf-8")
for keep in ("СЧЁТ ТЧК ЗВОНАРНЯ", "АНТЕНУ", "антена во какая", "Х Н.", "«Нине поклон»", "«Почтальону»", "Ящик №2 у колодца"):
    if keep not in raw:
        fail(f"canon string missing: {keep}")

# Идентификаторы событий не сдвинулись.
for eid in ("e_cart", "e_animal_rooster", "e_ramka", "p_l6", "e_animal_cat", "e_storm",
            "e_animal_goat_kid", "e_animal_matrena", "e_animal_matrena_jealous", "e_wind", "finale"):
    if eid not in events or eid not in en_events:
        fail(f"missing event {eid}")

if events["e_cart"]["options"][0]["id"] != "help" or events["e_wind"]["default"] != "chase":
    fail("choice ids or defaults changed")

if FAILS:
    print(f"{len(FAILS)} copy check(s) failed:")
    for item in FAILS:
        print(" -", item)
    raise SystemExit(1)
print(f"chapter 1 copy checks ok ({len(expect_ru)} RU lines)")
