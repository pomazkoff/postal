#!/usr/bin/env python3
"""Linux-friendly data/source regression checks, NOT an iOS runtime/UI test.

Run: python3 tools/check_resident_interactions.py
The selection fixtures exercise the story data; source contracts guard the Swift wiring.
See docs/RESIDENT_TAP.md for the required device/simulator smoke test.
"""
import json
import math
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
ENGINE = (ROOT / "Postman/App/ChapterEngine.swift").read_text()
SCENE = (ROOT / "Postman/Scene/WorldScene.swift").read_text()
GAME = (ROOT / "Postman/App/GameModel.swift").read_text()
HUD = (ROOT / "Postman/UI/HUDView.swift").read_text()
CARDS = (ROOT / "Postman/UI/StoryCards.swift").read_text()
CONFIG = (ROOT / "Postman/Model/StoryConfig.swift").read_text()
READABILITY = (ROOT / "Postman/Scene/Readability.swift").read_text()
LORE = json.loads((ROOT / "Postman/GameAssets/Data/resident_lore.json").read_text())
WORLD = json.loads((ROOT / "Postman/GameAssets/Data/world.json").read_text())
STORIES = [json.loads((ROOT / f"Postman/GameAssets/Data/chapter{n}_story.json").read_text())
           for n in (1, 2)]


def body(source, signature):
    start = source.index("{", source.index(signature))
    depth = 1
    end = start + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start + 1:end - 1]


def available_choice(story, resident, done=(), flags=()):
    """Data-only fixture oracle; resident choices currently use flag requirements."""
    def requirements_met(event):
        for atom in event.get("requires", "").split(","):
            if not atom:
                continue
            negative = atom.startswith("!")
            kind, value = atom.lstrip("!").split(":", 1)
            assert kind == "flag", "Extend fixture oracle if story conditions change"
            if (value in flags) == negative:
                return False
        return True
    events = sorted(story["events"], key=lambda e: e["step"])
    return next((e for e in events if e.get("resident") == resident and e["type"] == "choice"
                 and e["id"] not in done and requirements_met(e) and e.get("options")), None)


class StoryDataTests(unittest.TestCase):
    def test_all_animal_choices_have_renderable_resident_ids(self):
        count = 0
        for story in STORIES:
            residents = {r["id"] for r in story["residents"]}
            for event in story["events"]:
                if event["id"].startswith("e_animal_") and event["type"] == "choice":
                    count += 1
                    self.assertIn(event["resident"], residents)
                    self.assertTrue(event["options"])
        self.assertEqual(count, 7)

    def test_matrena_branches_and_once_fixtures(self):
        story = STORIES[0]
        self.assertEqual(available_choice(story, "matrena")["id"], "e_animal_matrena")
        self.assertEqual(available_choice(story, "matrena", flags={"ramka"})["id"],
                         "e_animal_matrena_jealous")
        self.assertIsNone(available_choice(story, "matrena", done={"e_animal_matrena"}))
        self.assertIsNone(available_choice(story, "matrena", flags={"ramka"},
                                          done={"e_animal_matrena_jealous"}))

    def test_reward_choices_become_replay_not_another_reward(self):
        for story, resident, event_id in [(STORIES[0], "cat_barrel", "e_animal_cat"),
                                           (STORIES[1], "raven_saddle", "e_animal_raven"),
                                           (STORIES[1], "dog_penki", "e_animal_dog")]:
            self.assertEqual(available_choice(story, resident)["id"], event_id)
            self.assertIsNone(available_choice(story, resident, done={event_id}))

    def test_goat_positions_are_separate_without_changing_story_steps(self):
        residents = {r["id"]: r for r in STORIES[0]["residents"]}
        pps = WORLD["game"]["pixelsPerStep"]
        kid, matrena = residents["goat_kid"], residents["matrena"]
        self.assertEqual((kid["step"], kid["dx"], kid["height"]), (12920, -420, 140))
        self.assertEqual((matrena["step"], matrena["dx"], matrena["height"]), (13320, 380, 210))
        kid_x = kid["step"] * pps + kid["dx"]
        matrena_x = matrena["step"] * pps + matrena["dx"]
        self.assertAlmostEqual(kid_x, 14696.4)
        self.assertAlmostEqual(matrena_x, 15964.4)
        self.assertGreaterEqual(abs(matrena_x - kid_x), 350)
        events = {e["id"]: e for e in STORIES[0]["events"]}
        self.assertEqual(events["e_animal_goat_kid"]["step"], 13050)
        self.assertEqual(events["e_animal_matrena"]["step"], 13400)

    def test_ramka_is_not_added_without_full_png(self):
        ramka = ROOT / "Postman/GameAssets/Chapter1/residents/ramka/full.png"
        residents = {r["id"]: r for r in STORIES[0]["residents"]}
        self.assertEqual("ramka" in residents, ramka.is_file())
        if ramka.is_file():
            self.assertEqual((residents["ramka"]["step"], residents["ramka"]["dx"],
                              residents["ramka"]["height"]), (13280, -120, 230))

    def test_every_resident_has_short_lore_with_plain_string_lines(self):
        residents = {r["id"] for story in STORIES for r in story["residents"]}
        companions = {e["companion"]["id"] for story in STORIES for e in story["events"]
                      if e.get("companion")}
        self.assertTrue((residents | companions) <= LORE.keys())
        for resident, lore in LORE.items():
            with self.subTest(resident=resident):
                self.assertEqual(set(lore), {"title", "lines"})
                self.assertTrue(isinstance(lore["title"], str) and lore["title"].strip())
                self.assertTrue(1 <= len(lore["lines"]) <= 3)
                self.assertTrue(all(isinstance(line, str) and line.strip() for line in lore["lines"]))
                self.assertLessEqual(sum(map(len, lore["lines"])), 280)

    def test_lore_does_not_contain_author_only_reveals_or_goat_age_resolution(self):
        text = json.dumps(LORE, ensure_ascii=False).lower()
        for secret in ("к-2", "к–2", "41", "лид", "поддел", "214", "смерт", "погиб", "эвакуац"):
            self.assertNotIn(secret, text)
        for resident in ("matrena", "goat_kid", "ramka"):
            for age in ("старш", "младш"):
                self.assertNotIn(age, " ".join(LORE[resident]["lines"]))


class SwiftContractTests(unittest.TestCase):
    def test_tap_selects_any_resident_choice_without_step_gate(self):
        code = body(ENGINE, "func interactWithResident(")
        self.assertIn("$0.resident == residentID", code)
        self.assertIn("$0.type == .choice", code)
        self.assertIn("!state.doneEvents.contains($0.id) && check($0.requires)", code)
        self.assertNotIn("e_animal_", code)
        self.assertNotIn(".step <=", code)
        self.assertNotIn(".step >=", code)

    def test_tap_has_no_story_effects_and_preserves_queue(self):
        code = body(ENGINE, "func interactWithResident(")
        for forbidden in ("applyChoice(", "apply(", "flags.insert", "addTrust(", "state.items[",
                          "doneEvents.insert", "state.choices[", "beat(", "log("):
            # state.choices is read, never assigned, when finding the previous result.
            if forbidden == "state.choices[":
                self.assertNotIn("state.choices[event.id] =", code)
            else:
                self.assertNotIn(forbidden, code)
        self.assertIn("state.pendingCards.removeAll { $0.id == interaction.id }", code)
        self.assertIn("state.pendingCards.insert(interaction, at: 0)", code)
        self.assertNotIn("pendingCards =", code)

    def test_repeat_is_read_only_lore_not_event_or_reward_replay(self):
        code = body(ENGINE, "func interactWithResident(")
        self.assertIn('id: "resident:" + residentID, kind: .scene', code)
        self.assertIn("title: lore.title, text: lore.text, lines: []", code)
        self.assertNotIn("events.reversed()", code)
        self.assertNotIn("?.result", code)
        self.assertNotIn("Пока тихо", code)

    def test_only_presented_choice_can_resolve_before_step_and_only_once(self):
        code = body(ENGINE, "func resolveChoice(")
        self.assertIn("!state.doneEvents.contains(eventID)", code)
        self.assertIn("event.step <= currentStep || state.pendingCards.contains", code)
        self.assertIn("$0.id == eventID && $0.kind == .choice", code)
        self.assertIn("guard check(event.requires)", code)
        self.assertEqual(code.count("applyChoice(event, option, by: chooser)"), 1)
        apply = body(ENGINE, "private func applyChoice(")
        self.assertIn("state.doneEvents.insert(event.id)", apply)
        self.assertIn("state.pendingCards.removeAll { $0.id == event.id }", apply)

    def test_invalidated_early_choice_does_not_stick(self):
        tap = body(ENGINE, "func interactWithResident(")
        self.assertIn("!check(event.requires)", tap)
        self.assertIn("$0.id == event.id && $0.kind == .choice", tap)
        resolve = body(ENGINE, "func resolveChoice(")
        self.assertIn("state.pendingCards.removeAll { $0.id == eventID }", resolve)
        process = body(ENGINE, "private func process()")
        self.assertIn("state.pendingCards.removeAll { $0.id == event.id }", process)

    def test_step_auto_entry_stays_intact(self):
        code = body(ENGINE, "private func process()")
        self.assertIn("guard stop.step <= currentStep else { break }", code)
        self.assertIn("guard shouldAutoResolve(after: index, step: event.step)", code)
        self.assertIn("let option = defaultOption(event)", code)
        self.assertIn("applyChoice(event, option, by: .postman)", code)

    def test_tap_defers_to_pan_and_pinch_and_is_removed_with_view(self):
        install = body(SCENE, "override func didMove(to view:")
        for fragment in ("tap.cancelsTouchesInView = false", "tap.require(toFail: pan)",
                         "tap.require(toFail: pinch)", "view.addGestureRecognizer(tap)"):
            self.assertIn(fragment, install)
        self.assertIn("view.removeGestureRecognizer(tap)", body(SCENE, "override func willMove(from view:"))
        self.assertNotIn("override func touches", SCENE)
        simultaneous = body(SCENE, "shouldRecognizeSimultaneouslyWith")
        self.assertIn("[panRecognizer, pinchRecognizer]", simultaneous)

    def test_hit_test_is_sprite_local_not_whole_screen(self):
        code = body(SCENE, "private func residentKey(at")
        self.assertIn("nodes(at: point)", code)
        self.assertIn("node.contains(convert(point, to: parent))", code)
        self.assertIn("residentNodes[key] === node || companionNode === node", code)
        receive = body(SCENE, "shouldReceive touch:")
        self.assertIn("isUserInteractionEnabled", receive)
        self.assertIn("residentKey(at: convertPoint(fromView:", receive)
        handle = body(SCENE, "private func handleResidentTap(")
        self.assertIn("g.state == .ended, !isPanning", handle)
        self.assertIn("onResidentTap?(chapterID, parts[1])", handle)

    def test_chapter_context_never_switches_progress_or_duplicates_active_writer(self):
        code = body(GAME, "private func visitResident(")
        self.assertIn("if chapterID == self.chapter.id", code)
        self.assertIn("visitEngine = self.engine", code)
        self.assertIn(r'chapter\(chapterID)_state.json', code)
        for fragment in ("switchToChapter(", "syncEngine(", "addDebugSteps(", "update(chapterSteps:"):
            self.assertNotIn(fragment, code)
        self.assertIn(".environmentObject(visit.engine)", HUD)
        self.assertIn("StoryCardView(card: card, chapter: visit.chapter)", HUD)
        self.assertIn("chapter ?? game.chapter", CARDS)
        self.assertIn("ResidentLibrary.figure(for: resident, assetsFolder: assetsFolder)", CARDS)

    def test_lore_loader_uses_bundled_data_and_safe_fallback(self):
        self.assertIn('appendingPathComponent("Data/resident_lore.json")', CONFIG)
        self.assertIn('JSONDecoder().decode([String: ResidentLore].self', CONFIG)
        self.assertIn('lines.joined(separator: "\\n")', CONFIG)
        self.assertIn('ResidentLore(title: fallbackTitle, lines:', CONFIG)
        project = (ROOT / "Postman.xcodeproj/project.pbxproj").read_text()
        self.assertIn('lastKnownFileType = folder; path = GameAssets', project)

    def test_tap_card_keeps_choice_identity_and_puts_lore_before_event_prompt(self):
        code = body(ENGINE, "func interactWithResident(")
        self.assertIn("ResidentLore.entry(for: residentID, fallbackTitle: resident?.name ?? residentID)", code)
        self.assertIn("[lore.text, event.text.map(resolve)]", code)
        self.assertIn("StoryCard(id: event.id, kind: .choice", code)
        self.assertIn("title: lore.title, text: text", code)
        self.assertIn("(event.lines ?? []).filter { check($0.if) }", code)

    def test_lore_only_scene_says_understood_without_changing_normal_scenes(self):
        code = body(CARDS, "private func scene(")
        self.assertIn('card.id.hasPrefix("resident:") ? "Понятно" : "Дальше"', code)
        self.assertIn("body_: card.text", code)

    def test_companion_only_ramka_has_lore_without_stationary_resident(self):
        code = body(ENGINE, "func interactWithResident(")
        self.assertIn("resident != nil || orderedEvents.contains", code)
        self.assertIn("$0.companion?.id == residentID", code)
        self.assertIn("ramka", LORE)
        self.assertTrue(any(e.get("companion", {}).get("id") == "ramka" for e in STORIES[0]["events"]))
        # Stationary residents stay driven by the JSON list only.
        install = body(GAME, "private func installStory(")
        self.assertIn("for r in story.residents", install)

    def test_soft_readability_rim_and_shadow(self):
        self.assertIn("rimAlpha: CGFloat = 0.18", READABILITY)
        self.assertIn("rimOffset = CGPoint(x: -2.0, y: 1.5)", READABILITY)
        self.assertIn("shadowAlpha: CGFloat = 0.35", READABILITY)

    def test_animals_react_on_sprite_transform_without_spritesheet_or_scale_conflict(self):
        code = body(SCENE, "func playResidentReact(")
        for animal in ("matrena", "goat_kid", "ramka", "cat_barrel", "rooster", "dog_penki", "raven_saddle"):
            self.assertIn('"' + animal + '"', code)
        for fragment in ("residentNodes[key]", "companionID == key", "duration: TimeInterval = 0.6",
                         "SKAction.customAction", "sprite.position =", "sprite.zRotation =",
                         'withKey: "residentReact"'):
            self.assertIn(fragment, code)
        for forbidden in (".texture =", "animate(with:", ".yScale =", ".xScale =", "repeatForever"):
            self.assertNotIn(forbidden, code)
        # Numeric fixture for the transform envelope, not a SpriteKit runtime test.
        for t in (0, 1):
            self.assertAlmostEqual(36 * math.sin(math.pi * t), 0)
            self.assertAlmostEqual(math.sin(6 * math.pi * t) * (1 - t), 0)
        self.assertAlmostEqual(36 * math.sin(math.pi * 0.5), 36)

    def test_reaction_restores_pose_and_companion_follow_does_not_overwrite_it(self):
        code = body(SCENE, "func playResidentReact(")
        self.assertIn('guard node.action(forKey: "residentReact") == nil', code)
        for fragment in ("let origin = node.position", "let rotation = node.zRotation",
                         "node?.position = origin", "node?.zRotation = rotation",
                         "shadow?.position = shadowOrigin"):
            self.assertIn(fragment, code)
        companion = body(SCENE, "private func updateCompanion(")
        guard = companion.index('guard node.action(forKey: "residentReact") == nil')
        self.assertLess(guard, companion.index("node.position ="))
        self.assertLess(guard, companion.index("node.zRotation ="))

    def test_card_queue_waits_until_after_reaction_and_pending_visit_is_cancellable(self):
        code = body(GAME, "private func visitResident(")
        react = code.index("scene.playResidentReact(chapterID: chapterID, id: residentID)")
        delayed = code.index("DispatchQueue.main.asyncAfter(deadline: .now() + reactionDuration)")
        enqueue = code.index("visitEngine.interactWithResident(residentID)")
        self.assertLess(react, delayed)
        self.assertLess(delayed, enqueue)
        self.assertIn("self.residentVisitRequestID == requestID", code)
        for signature in ("func endResidentVisit()", "func appWentToBackground()"):
            self.assertIn("residentVisitRequestID = nil", body(GAME, signature))
        self.assertIn("endResidentVisit()", body(GAME, "private func handleChapterChanged("))


if __name__ == "__main__":
    unittest.main(verbosity=2)
