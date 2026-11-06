#!/usr/bin/env python3
"""Box-only regression checks: extracted Swift math + source/data/art contracts.

This is NOT an iOS build or SpriteKit runtime test. Run with python3; needs Pillow/numpy.
"""
import ast
import json
from pathlib import Path
import re
from types import SimpleNamespace as Obj
import unittest
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'Postman/GameAssets'
WORLD = json.loads((ASSETS / 'Data/world.json').read_text())
CORE = (ROOT / 'Postman/App/AppCore.swift').read_text()
MODEL = (ROOT / 'Postman/App/GameModel.swift').read_text()
SCENE = (ROOT / 'Postman/Scene/WorldScene.swift').read_text()
PROGRESS = (ROOT / 'Postman/Services/ProgressStore.swift').read_text()


def body(source, signature):
    start = source.index('{', source.index(signature)) + 1
    depth, end = 1, start
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end - 1]


def extracted_steps(source, total, chapter_index, forced=None, base=None):
    """Evaluate the actual arithmetic return expressions from both Swift call paths."""
    fn = body(source, 'func chapterSteps(total: Int) -> Int')
    formulas = re.findall(r'return ([^\n]+)', fn)
    assert len(formulas) == 2, formulas
    formula = formulas[0] if forced == chapter_index and base is not None else formulas[1]
    tree = ast.parse(formula, mode='eval')
    allowed = (ast.Expression, ast.Call, ast.Name, ast.Load, ast.Attribute,
               ast.BinOp, ast.Sub, ast.Constant)
    assert all(isinstance(n, allowed) for n in ast.walk(tree))
    chapter = Obj(**WORLD['chapters'][chapter_index])
    context = {'max': max, 'min': min, 'chapter': chapter, 'total': total,
               'base': base, 'world': Obj(game=Obj(**WORLD['game']))}
    return eval(compile(tree, '<Swift chapterSteps arithmetic>', 'eval'), {'__builtins__': {}}, context)


def resolve(total, forced=None, chapters=None):
    chapters = chapters or WORLD['chapters']
    if forced is not None:
        return max(0, min(len(chapters) - 1, forced))
    return max(i for i, c in enumerate(chapters) if c['startStep'] <= max(0, min(total, WORLD['game']['totalSteps'])))


def boundary_coverage():
    """Place the real road and underground tiles at their scene X and require opaque ground.

    Crops meet at the chapter boundary. Nothing is faded. This is the geometry after
    removing the alpha that opened holes in 17746c5.
    """
    pps = WORLD['game']['pixelsPerStep']
    boundary = 20000 * pps
    design_w = WORLD['game']['designWidth']
    ch1, ch2 = WORLD['chapters']

    def roads(chapter):
        spans = []
        for prop in chapter['props']:
            if prop['layer'] != 'main' or 'road/road_main' not in prop['image']:
                continue
            height = prop['height']
            width = height * prop['pixelSize'][0] / max(1, prop['pixelSize'][1])
            left = (chapter['startStep'] + prop['step']) * pps + prop['dx']
            spans.append((left, left + width, prop['image'], chapter))
        return spans

    def ug_tiles(chapter):
        ug = chapter['underground']
        tile_w = ug['tilePixelSize'][0] * ug['scale']
        spans = []
        # Neutral strip covers the chapter plus four screens, then the crop cuts it.
        margin = design_w * 4
        strip_left = chapter['startStep'] * pps - margin
        strip_right = (chapter['startStep'] + chapter['lengthSteps']) * pps + margin
        crop_left = margin * -1 if chapter['id'] == 1 else chapter['startStep'] * pps
        crop_right = (chapter['startStep'] + chapter['lengthSteps']) * pps if chapter['id'] == 1 else strip_right
        if chapter['id'] == 1:
            crop_left = -margin
            crop_right = boundary
        else:
            crop_left = boundary
            crop_right = (chapter['startStep'] + chapter['lengthSteps']) * pps + margin
        spans.append((max(strip_left, crop_left), min(strip_right, crop_right), ug['neutralTile'], chapter))
        for module in ug['modules']:
            left = (chapter['startStep'] + module['step']) * pps + module['dx'] - tile_w / 2
            spans.append((max(left, crop_left), min(left + tile_w, crop_right), module['image'], chapter))
        return spans

    def covered(spans, x):
        return any(a <= x < b for a, b, _, _ in spans)

    road = roads(ch1) + roads(ch2)
    ug = ug_tiles(ch1) + ug_tiles(ch2)
    holes = []
    for x in range(int(boundary - 2 * design_w), int(boundary + 2 * design_w), 20):
        if not covered(road, x):
            holes.append(('road', x))
        if not covered(ug, x):
            holes.append(('ug', x))
    # Sample the opaque ground row of whichever road owns this x. No alpha was removed.
    def owner(spans, x):
        hits = [s for s in spans if s[0] <= x < s[1]]
        return hits[-1] if hits else None

    y_from_bottom = 40
    opaque = 0
    checked = 0
    for x in range(int(boundary - 400), int(boundary + 400), 40):
        hit = owner(road, x)
        if hit is None:
            continue
        left, right, image, chapter = hit
        im = Image.open(ASSETS / chapter['assetsFolder'] / (image + '.png')).convert('RGBA')
        width = right - left
        src_x = int((x - left) / width * im.size[0])
        src_y = im.size[1] - 1 - int(y_from_bottom / 700 * im.size[1])
        src_x = min(max(src_x, 0), im.size[0] - 1)
        src_y = min(max(src_y, 0), im.size[1] - 1)
        if im.getpixel((src_x, src_y))[3] > 200:
            opaque += 1
        checked += 1
    return {'holes': holes, 'opaque': opaque, 'checked': checked}


class ChapterProgressTests(unittest.TestCase):
    def test_force_does_not_add_steps(self):
        fn = body(CORE, 'func debugForceChapter2()')
        self.assertNotIn('addDebugSteps', fn)
        self.assertIn('forceChapterBaseSteps = steps.totalSteps', fn)
        self.assertIn('switchToChapter(1)', fn)
        self.assertIn('syncEngine(total: steps.totalSteps)', fn)

    def test_force_zero_then_500_in_both_consumers(self):
        for src in (CORE, MODEL):
            for base in (0, 3500, 19999, 23500, 150000):
                self.assertEqual(extracted_steps(src, base, 1, 1, base), 0)
                self.assertEqual(extracted_steps(src, base + 500, 1, 1, base), 500)

    def test_forced_clamping_and_real_total_cap_independence(self):
        for src in (CORE, MODEL):
            self.assertEqual(extracted_steps(src, 3000, 1, 1, 3500), 0)
            self.assertEqual(extracted_steps(src, 50000, 1, 1, 3500), 25000)
            self.assertEqual(extracted_steps(src, 150500, 1, 1, 150000), 500)

    def test_force_only_affects_selected_chapter(self):
        for src in (CORE, MODEL):
            self.assertEqual(extracted_steps(src, 3500, 0, 1, 3500), 3500)

    def test_natural_boundaries_and_clear(self):
        for total in (0, 500, 3500, 19999):
            self.assertEqual(resolve(total), 0)
        self.assertEqual(resolve(20000), 1)
        self.assertEqual(resolve(23500), 1)
        for src in (CORE, MODEL):
            self.assertEqual(extracted_steps(src, 20500, 1), 500)
            self.assertEqual(extracted_steps(src, 4000, 0), 4000)
        clear = body(CORE, 'func debugClearChapterForce()')
        self.assertIn('forceChapterIndex = nil', clear)
        self.assertIn('forceChapterBaseSteps = nil', clear)

    def test_persisted_base_can_be_zero_and_is_reset(self):
        prop = body(PROGRESS, 'var forceChapterBaseSteps: Int?')
        self.assertIn('defaults.object(forKey:', prop)
        for name in ('func resetAll()', 'func resetStory(now:'):
            fn = body(PROGRESS, name)
            self.assertIn('Key.forceChapterIndex', fn)
            self.assertIn('Key.forceChapterBaseSteps', fn)
        reset = body(MODEL, 'func resetStory()')
        self.assertIn('core.switchToChapter(0)', reset)
        self.assertIn('for chapter in world.chapters', reset)
        self.assertIn('scene.resetForNewStory()', reset)

    def test_explicit_scene_refresh_when_total_is_unchanged(self):
        panel = (ROOT / 'Postman/UI/DebugPanel.swift').read_text()
        self.assertIn('game.refreshChapterProgress()', panel)
        self.assertIn('game.objectWillChange.send()', panel)
        apply = body(MODEL, 'private func applyTotal(')
        self.assertIn('chapterSteps(total: total)', apply)
        self.assertIn('scene.setTargetSteps(worldSteps(total: total))', apply)

    def test_stale_healthkit_result_cannot_undo_reset(self):
        steps = (ROOT / 'Postman/Services/StepService.swift').read_text()
        self.assertIn('startGeneration += 1', body(steps, 'func resetForNewStart()'))
        refresh = body(steps, 'private func performRefresh()')
        self.assertIn('let generation = startGeneration', refresh)
        self.assertEqual(refresh.count('guard generation == startGeneration'), 2)


class WorldStripTests(unittest.TestCase):
    def test_chapter_boundary_is_solid_again_with_no_alpha_holes(self):
        nodes = (ROOT / 'Postman/Scene/WorldNodes.swift').read_text()
        for gone in ('JoinBake', 'chapterJoinRoad', 'HorizontalFade', 'edgeFade', 'installBakedJoins', 'u_fade0'):
            self.assertNotIn(gone, SCENE)
            self.assertNotIn(gone, nodes)
        # The hole was destinationIn punching the tiles. The remaining use is the far-tile top fade.
        self.assertNotIn('destinationIn', SCENE)
        stats = boundary_coverage()
        self.assertEqual(stats['holes'], [])
        self.assertGreater(stats['checked'], 10)
        self.assertEqual(stats['opaque'], stats['checked'])

    def test_one_scene_not_replaced_at_chapter_boundary(self):
        changed = body(MODEL, 'private func handleChapterChanged(')
        self.assertNotIn('WorldScene(', changed)
        self.assertNotIn('replaceScene', MODEL)
        self.assertNotIn('.id(game.chapterIndex)', (ROOT / 'Postman/UI/GameView.swift').read_text())
        self.assertEqual(MODEL.count('WorldScene(config:'), 1)
        self.assertIn('for (index, chapter) in config.chapters.enumerated()', SCENE)

    def test_global_environment_and_story_coordinates(self):
        self.assertIn('Double(chapter.startStep + p.step)', SCENE)
        self.assertIn('Double(chapter.startStep + m.step)', SCENE)
        self.assertIn('chapter.startStep + event.step', MODEL)
        self.assertIn('chapter.startStep + r.step', MODEL)
        self.assertIn('chapter.id)/', MODEL)
        self.assertIn('chapterID: Int', SCENE)
        self.assertIn('worldEndStep', body(SCENE, 'func setTargetSteps('))
        camera = body(SCENE, 'private var minCameraX:')
        self.assertNotIn('chapter', camera)

    def test_future_chapters_have_no_special_case_camera_boundary(self):
        chapters = WORLD['chapters'] + [dict(id=3, startStep=45000, lengthSteps=25000)]
        self.assertEqual(resolve(45000, chapters=chapters), 2)
        pps = WORLD['game']['pixelsPerStep']
        self.assertAlmostEqual((45000 * pps) - (44999 * pps), pps)
        sync = body(CORE, 'func syncEngine(total:')
        self.assertIn('while chapterIndex < idx', sync)
        self.assertIn('chapter.lengthSteps', sync)

    def test_neutral_covers_modules_before_async_decode(self):
        ug = body(SCENE, 'private func buildUnderground(')
        self.assertLess(ug.index('while baseX < stripEnd'), ug.index('guard let first'))
        self.assertIn('undergroundParallax', SCENE)
        self.assertEqual(WORLD['layers']['undergroundParallax'], 1)


class AssetTests(unittest.TestCase):
    def test_layer_dimensions_preserve_global_layout(self):
        for key in ('far', 'mid'):
            spec = WORLD['layers'][key]
            for chapter in WORLD['chapters']:
                with Image.open(ASSETS / chapter['assetsFolder'] / (spec['image'] + '.png')) as im:
                    self.assertEqual(im.size, tuple(spec['pixelSize']))
        self.assertEqual((WORLD['layers']['far']['height'], WORLD['layers']['mid']['height']), (1100, 520))

    def test_background_periodic_edges(self):
        for name in ('bg_far_ridges_tile', 'bg_mid_fields_tile'):
            a = np.array(Image.open(ASSETS / 'Chapter2/places' / (name + '.png')))
            np.testing.assert_array_equal(a[:, 0], a[:, -1])
            self.assertGreater((a[:a.shape[0] // 2, :, 3] > 128).mean(), 0.2)

    def test_underground_assets_load_and_match_edges(self):
        chapter = WORLD['chapters'][1]
        ug = chapter['underground']
        neutral = np.array(Image.open(ASSETS / chapter['assetsFolder'] / (ug['neutralTile'] + '.png')).convert('RGB'))
        np.testing.assert_array_equal(neutral[:, 0], neutral[:, -1])
        for module in ug['modules']:
            im = Image.open(ASSETS / chapter['assetsFolder'] / (module['image'] + '.png')).convert('RGBA')
            self.assertEqual(im.size, tuple(ug['tilePixelSize']))
            a = np.array(im)
            self.assertEqual(int(a[:, :, 3].min()), 255)
            np.testing.assert_array_equal(a[:, 0, :3], neutral[:, 0])
            np.testing.assert_array_equal(a[:, -1, :3], neutral[:, -1])

    def test_no_surface_gap(self):
        ug = WORLD['chapters'][1]['underground']
        self.assertEqual(WORLD['game']['roadLineY'] - ug['top'], 20)
        self.assertGreaterEqual(ug['top'] + ug['tilePixelSize'][1] * ug['scale'], WORLD['game']['designHeight'] - 4)


if __name__ == '__main__':
    unittest.main(verbosity=2)
