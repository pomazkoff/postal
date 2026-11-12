#!/usr/bin/env python3
"""Put the chapter 3 English overlay into en.json. Strings only; no ids or flags."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EN = ROOT / "Postman/GameAssets/L10n/en.json"


def letters():
    src = (ROOT / "tools/build_chapter3_story.py").read_text(encoding="utf-8")
    start = src.index("EN_LETTERS = ")
    depth = 0
    end = start
    for i, ch in enumerate(src[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    ns = {}
    exec(src[start:end], ns)
    return ns["EN_LETTERS"]


L = letters()
AL = L[1][0]

ITEMS = {
    "l1": {
        "to": "For Mitya", "from": "Galya",
        "place": "Stilts · a chance downstream, the box on the Boardwalk",
        "text": L[1][1], "note": AL,
        "attachmentCaption": "three thin hooks in a paper marked “for the roach”; no stamp",
        "address": ["FOR MITYA US", "FROM MAMA"],
    },
    "l4": {
        "to": "For Vera", "from": "Mitya",
        "place": "Institute · for Vera, the hut at the Mire",
        "text": L[4],
        "attachmentCaption": "a drawing of the loop and a fir-tree wrapper",
        "address": ["RADIOSHADOW INSTITUTE.", "PASECHNIK V.I."],
    },
    "frame": {"to": "For the postman", "from": "Mitya", "place": "Personal things",
              "text": "A wire loop. You turn it and listen for where the hum is louder."},
    "note_fedya": {
        "to": "For Marya", "from": "Old Fedya",
        "place": "Tubs · a chance downstream, the hut at the Mire",
        "text": L and None,
        "attachmentCaption": "pencil on a nail wrapper",
        "address": ["FOR MARYA", "THE TUBS"],
    },
    "l2": {
        "to": "For Timofey", "from": "Nina",
        "place": "Olkhovka · for A.L., the box at the Peat Cut",
        "text": L[2],
        "attachmentCaption": "no enclosure",
        "address": ["OLKHOVKA, TO BE CALLED FOR.", "KOLOBOV T.G."],
    },
    "l3": {
        "to": "For Nina", "from": "Timofey",
        "place": "Tubs · a chance downstream, the box on the barge",
        "text": L[3],
        "attachmentCaption": "a label, “Sprats in tomato”",
        "address": ["THE TUBS.", "KOLOBOVA N.A."],
    },
    "l5": {
        "to": "For Mitya", "from": "Galya",
        "place": "Stilts · a chance downstream, the box in the Reeds",
        "text": L[5],
        "attachmentCaption": "no enclosure",
        "address": ["FOR MITYA US"],
    },
    "l6": {
        "to": "For the postman", "from": "Mitya",
        "place": "Old Channel · read where it is found",
        "text": L[6],
        "attachmentCaption": "a scrap of tape: four names, Us Galya among them",
        "address": ["FOR THE POSTMAN"],
    },
    "l7": {
        "to": "For Vera", "from": "Kuzma", "outside": "V.I. Pasechnik. Personal.",
        "place": "Institute · for Vera, the box in the Reeds",
        "text": L[7],
        "attachmentCaption": "a chip notched 58",
        "address": ["V.I. PASECHNIK.", "PERSONAL"],
    },
    "l8": {
        "to": "For the postman", "from": "Vera", "outside": "For the postman. Personal.",
        "place": "Gullet · read where it is found",
        "text": L[8],
        "attachmentCaption": "graph paper: 31, 44, 58; “at the 3rd” crossed out, “at the 4th”",
        "address": ["FOR THE POSTMAN.", "PERSONAL"],
    },
    "l9": {
        "to": "For Vera", "from": "Nina",
        "place": "Institute · a chance to the Valley, the box at the Settling Pool",
        "text": L[9],
        "attachmentCaption": "no enclosure",
        "address": ["RADIOSHADOW INSTITUTE.", "PASECHNIK V.I."],
    },
    "l10": {
        "to": "For the postman", "from": "Kuzma", "outside": "For the postman.",
        "place": "Settling Pool · read where it is found",
        "text": L[10],
        "attachmentCaption": "a refusal sheet: Somov Ferapont Ilyich, the Tubs",
        "address": ["FOR THE POSTMAN"],
    },
    "find_edge": {"to": "For the postman", "from": "Boardwalk", "place": "Personal things",
                  "text": "The edge of a stamp from under the planks. No letters. The colour still holds."},
    "find_tag": {"to": "For the postman", "from": "Old Fedya", "place": "Personal things",
                 "text": "A chip stamped by the plant. From the lower store."},
    "find_card": {"to": "For the postman", "from": "Hummocks", "place": "Personal things",
                  "text": "A memorial card. “Somov F.I.”. The ribbon on the stake has faded."},
    "find_pole": {"to": "For the postman", "from": "Mire", "place": "Personal things",
                  "text": "A pole with no nicks. Someone else's. In the silt by the boardwalk."},
    "find_graph": {"to": "For the postman", "from": "Mire", "place": "Personal things",
                   "text": "A scrap of graph paper. Another hand. The word “pilot”, no figures."},
    "find_pass": {"to": "For the postman", "from": "Peat Cut", "place": "Personal things",
                  "text": "A work pass on a string. An old pattern. The name cannot be made out."},
    "find_wet": {"to": "For the postman", "from": "Old Channel", "place": "Personal things",
                 "text": "A wet envelope. The stamp says “N. Stvor”. No letters inside. The stamp is still coloured."},
}

# Fedya's note is not in EN_LETTERS. Keep it beside the Russian.
ITEMS["note_fedya"]["text"] = (
    "For Marya at the Tubs. I am alive, I am holding the boardwalk, I have not gone lower: the road has washed out. "
    "Send socks if there is a chance. Mine have rotted. There is tea, and bread too.\nOld F."
)


def ev(title=None, text=None, lines=(), push=(), fallback=None, options=None):
    out = {}
    if title:
        out["title"] = title
    if text:
        out["text"] = text
    if lines:
        out["lines"] = [{"text": line} for line in lines]
    if push:
        out["push"] = [{"text": line} for line in push]
    if fallback:
        out["fallback"] = fallback
    if options:
        out["options"] = options
    return out


EVENTS = {
    "p_l1": ev("A clean envelope", lines=("In the clay by the stake lies a clean envelope with no stamp. Hooks inside, a note: “for the roach”.",), push=("The Throat. An envelope with no stamp in the clay.",)),
    "s_al": ev("A note in the box", text=AL, lines=(AL,), push=("The Throat. A.L.: the road below has washed out.",)),
    "e_gati_fog": ev(
        "A plank road in the fog",
        "The poles run off into the fog. The length of the path is the same.",
        push=("A plank road in the fog. Where to step?",),
        options={
            "poles": {"label": "Walk the poles", "result": "Feet dry. The planks breathe a little with the water.", "auto": "The postman walked the poles."},
            "hummocks": {"label": "Step onto the hummocks", "result": "Feet wet. The bag sloshes. From the hummocks you can take the edge of a stamp."},
        },
    ),
    "p_edge": ev("An edge from a crack", lines=("The edge of a stamp sticks out of a crack in the boardwalk. There are no letters.",), push=("The Boardwalk. The edge of an envelope in a crack of the planks.",)),
    "d_gat": ev("The box on the Boardwalk", "A tin box, “a chance”. Mail goes down from here, into the Valley.", lines=(
        "Galya's letter went into the box on the Boardwalk, “a chance downstream”.",
        "The stamp edge was left in the same box, for old Fedya.",
    ), push=("The Boardwalk. The chance box.",)),
    "p_l4": ev(lines=("A chance from the Valley: Mitya to Vera. A drawing of the loop, and a wrapper.",), push=("The Boardwalk. Mitya's letter to Vera.",)),
    "p_frame": ev(lines=("A wire loop went into the personal things.",), push=("The Boardwalk. A loop for taking a bearing.",)),
    "e_fedya_help": ev(
        "A span has come apart",
        "Old Fedya is laying a span. Help does not change the length of the path.",
        push=("Old Fedya is laying a span. Will you help?",),
        options={
            "hand": {"label": "Pass him a pole", "result": "A short job at the planks. Fedya pushes over a note for Marya: socks, if there is a chance.", "auto": "The postman passed him a pole."},
            "walk": {"label": "Walk on", "result": "Fedya pushes the note over anyway. “Go on, then. Only put it in the box.”"},
        },
    ),
    "p_card": ev("A card on a stake", lines=("On a crooked stake, a faded ribbon and a card: Somov F.I.",), push=("The Hummocks. Somov's card on a stake.",)),
    "e_somov": ev(
        "Somov's card",
        "It can be given once, through a box still ahead. There is no need to go back to the Tubs or the Belfry.",
        push=("Somov's card. Who should have it?",),
        options={
            "pimen": {"label": "Leave it for Pimen", "result": "Pimen will answer by a chance: he buried Somov Ferapont in August. The apples were not picked yet."},
            "nina": {"label": "Leave it for Nina", "result": "Nina will answer by a chance: Ferapont has been gone since August, the apple trees were still standing, she used to bring him a jar."},
            "keep": {"label": "Keep it", "result": "The card stays with the personal things. The refusal sheet can be set beside it later.", "auto": "The postman kept the card."},
        },
    ),
    "d_top": ev("The hut at the Mire", "The hut is empty. In the box, notes: “for Vera” and “a chance downstream”.", lines=(
        "Mitya's letter and Fedya's note went into the hut at the Mire.",
        "Fedya's note went “downstream, by a chance”, to Marya.",
        "The stamped chip was left for Vera. She answers: the lower stamp, noted.",
        "Somov's card was left for Pimen. He buried Ferapont in August. The apples were not picked.",
        "Somov's card was left for Nina. Ferapont has been gone since August. She used to bring him a jar.",
    ), push=("The Mire. The hut. The chance box.",)),
    "p_l2": ev(lines=("A chance from the Valley: Nina to Timofey. She asks what the goat was called.",), push=("The Mire. Nina's letter to Timofey.",)),
    "p_pole": ev(lines=("In the silt by the boardwalk, a pole with not a single nick.",), push=("The Mire. Someone else's pole in the silt.",)),
    "p_graph": ev(lines=("By the hut, a scrap of graph paper. “Pilot”. No figures.",), push=("The Mire. Someone else's scrap of graph paper.",)),
    "d_torf": ev("The box at the Peat Cut", "A service box. A note: “for A.L.”.", lines=(
        "Nina's letter went into the box at the Peat Cut, “for A.L.”.",
        "The pole with no nicks was left for Kuzma. Not his. Someone further down is measuring too.",
        "Mitya was left the scrap: pilot, not his hand, someone had already measured.",
    ), push=("The Peat Cut. The box for A.L.",)),
    "p_l3": ev(lines=("A chance: “Tima” to Nina. He called the goat Ramka. A tin label.",), push=("The Peat Cut. A letter “from Tima” to Nina.",)),
    "p_pass": ev(lines=("In the peat, a pass on a string. An old pattern.",), push=("The Peat Cut. A pass in the peat.",)),
    "e_bearing": ev(
        "Where the loop is louder",
        "A note on the post: louder toward the top. The loop can be turned. That does not make the road longer.",
        fallback="The loop is not among the things. On the post, in pencil: “louder toward the top”.",
        push=("A note on the post: louder toward the top. Turn the loop?",),
        options={
            "valley": {"label": "Take a bearing toward the Valley", "result": "Louder toward the Valley than toward the Reach. Steady, like a refrigerator.", "auto": "The postman took a bearing toward the Valley."},
            "stvor": {"label": "Take a bearing toward the Reach", "result": "Quieter toward the Reach. Louder back, toward the Valley."},
            "skip": {"label": "Don't turn it", "result": "The post still says: louder toward the top. There is no bearing of his own."},
        },
    ),
    "p_l5": ev(lines=("A chance: “Galya” to Mitya. “Received in one piece”. There are no hooks.",), push=("The Old Channel. A letter “from Galya” to Mitya.",)),
    "d_barge": ev("The box on the barge", "A “chance” box on the deck.", lines=(
        "The letter “from Tima” went into the box on the barge, “a chance downstream”.",
        "The pass was left for old Fedya. The lower yard, an old pattern. He has not gone there since autumn.",
    ), push=("The Old Channel. The box on the barge.",)),
    "p_l7": ev(lines=("Kuzma to Vera. On the chip, fifty-eight. Pitch.",), push=("The Old Channel. Kuzma to Vera: fifty-eight.",)),
    "p_l6": ev(lines=("Mitya to the postman. Four names from the bell. Us Galya among them.",), push=("The Old Channel. Mitya made out a piece of the bell.",)),
    "p_wet": ev(lines=("Under the barge, a wet envelope. The stamp says “N. Stvor”. No letters.",), push=("The Old Channel. The envelope under the barge cannot be read.",)),
    "d_reeds": ev("The box in the Reeds", "A tin box by the verst post. The figure on the post is washed off.", lines=("The letter “from Galya” went “downstream, by a chance”.", "Kuzma's chip went in “for Vera”.",), push=("The Reeds. The box by the verst post.",)),
    "e_radio": ev(
        "A radio in the reeds",
        "An abandoned radio lies on the path. Night is not required for this.",
        fallback="The song had already broken off. The radio was touched earlier.",
        push=("A radio lies in the reeds. Listen?",),
        options={
            "listen": {"label": "Listen", "result": "The song broke off. After that, only noise.", "auto": "The postman listened. The song broke off."},
            "walk": {"label": "Walk on", "result": "The radio stays on the path. It can be touched later."},
        },
    ),
    "p_l8": ev(lines=("Vera to the postman. 58 is the third nick. The shutdown is put off until the fourth.",), push=("The Gullet. Vera puts off the third mark.",)),
    "e_plug": ev(
        "A wall of mud",
        "A grey wall across the river. It can be seen from the road anyway.",
        push=("A grey wall ahead. Go closer?",),
        options={
            "close": {"label": "Go closer", "result": "In the wall: a box door, a rim, a thermos, a pass on a string. Nobody says what the wall is.", "auto": "The postman went up to the wall."},
            "stay": {"label": "Stay on the boardwalk", "result": "The wall can be seen from the boardwalk. A closer look can be taken later, by scrolling."},
        },
    ),
    "p_l9": ev(lines=("Nina to Vera. The goat was called Zorka. She asks for the truth, with no accusations.",), push=("The Gullet. Nina writes to Vera.",)),
    "d_otstoy": ev("The box at the Settling Pool", "The last stake. The kettle on the hook is still warm. Nobody is here.", lines=("Nina's letter went into the box at the Settling Pool, “a chance to the Valley, for Vera”.",), push=("The Settling Pool. The box by the last stake.",)),
    "p_l10": ev(lines=("A bundle, “For the postman, personal”. A refusal sheet inside. The line: Somov Ferapont Ilyich, the Tubs. No annotations.",), push=("The Settling Pool. A bundle without a single word.",)),
    "finale": ev(lines=(
        "The landing “Settling Pool”. The barrier in the fog does not open.",
        "In a break in the sheet, pipes show for a moment. Then fog again.",
        "The kettle is still warm. Who was here is not said. Beyond is raw clay.",
    ), push=("The Settling Pool. The kettle is warm. Beyond, the town in the fog.",)),
}

STORY = {
    "finaleTitle": "Chapter 3 · Marshes",
    "finaleSubtitle": "finished",
    "nextChapter": "Chapter 4, “The City of Silence” — soon",
    "items": ITEMS,
    "events": EVENTS,
    "quests": {
        "d_gat|inBag:l1": "Carry the clean envelope to the box on the Boardwalk",
        "d_top|": "To the Mire: a letter for Vera and Fedya's note",
        "d_torf|": "To the Peat Cut, the box for A.L.",
        "d_reeds|": "To the Reeds",
        "finale|": "To the Settling Pool",
    },
    "residents": {
        "fedya": "Old Fedya",
        "nyura": "Aunt Nyura",
        "semyon": "Semyon",
        "grisha": "Uncle Grisha",
        "petka": "Petka",
    },
    "fates": {
        "gat|inBag:l1": "The clean envelope is still in the bag. Its place is the box on the Boardwalk.",
        "gat|delivered:l1": "Galya's letter was left on the Boardwalk, a chance downstream.",
        "top|flag:bearing_done": "The loop was turned. It was louder toward the Valley.",
        "gorlo|flag:plug_close": "The wall in the Gullet was approached. It holds household things, not bodies.",
        "otstoy|read:l10": "The refusal sheet has been read. Nobody circled Ferapont's signature.",
    },
    "arrivals": {
        "gorlovina": "The Throat. The path dives into the fog. A clean envelope in the clay.",
        "gat": "The Boardwalk. Planks, a hut, the chance box. Old Fedya is mending a span.",
        "top": "The Mire. The same boardwalk by day and by night. A box in the hut.",
        "torfyanik": "The Peat Cut. Stacks, a tally, an empty barrack.",
        "staraya_protoka": "The Old Channel. A barge by the bank, a box on the deck.",
        "kamyshi": "The Reeds. A straight boardwalk, a verst post, a box by the post.",
        "gorlo": "The Gullet. A grey wall across the river. A box by the stake.",
        "otstoy": "The Settling Pool. A barrier, a warm kettle, pipes in a break in the fog.",
    },
}

WORLD = {
    "title": "Marshes",
    "settlements": {
        "gorlovina": {"name": "Throat", "nameGenitive": "the Throat", "fullName": "Ravine “the Throat”"},
        "gat": {"name": "Boardwalk", "nameGenitive": "the Boardwalk", "fullName": "Boardwalk"},
        "top": {"name": "Mire", "nameGenitive": "the Mire", "fullName": "Mire"},
        "torfyanik": {"name": "Peat Cut", "nameGenitive": "the Peat Cut", "fullName": "Peat Cut"},
        "staraya_protoka": {"name": "Old Channel", "nameGenitive": "the Old Channel", "fullName": "Old Channel"},
        "kamyshi": {"name": "Reeds", "nameGenitive": "the Reeds", "fullName": "Reeds"},
        "gorlo": {"name": "Gullet", "nameGenitive": "the Gullet", "fullName": "Gorge “the Gullet”"},
        "otstoy": {"name": "Settling Pool", "nameGenitive": "the Settling Pool", "fullName": "Landing “the Settling Pool”"},
    },
    "quests": {
        "4000": "Carry the clean envelope to the box on the Boardwalk",
        "9000": "To the Mire",
        "20000": "To the Reeds",
        "30000": "To the Settling Pool",
    },
}

MAP = {
    "gat": "Boardwalk",
    "top": "Mire",
    "torfyanik": "Peat Cut",
    "staraya_protoka": "Old Channel",
    "gorlo": "Gullet",
    "otstoy": "Settling Pool",
}


def main():
    doc = json.loads(EN.read_text(encoding="utf-8"))
    doc["stories"]["3"] = STORY
    doc["world"]["chapters"]["3"] = WORLD
    doc["map"]["settlements"].update(MAP)
    EN.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("en.json updated")


if __name__ == "__main__":
    main()
