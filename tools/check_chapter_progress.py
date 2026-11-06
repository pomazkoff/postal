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


def baked_boundary_sheet():
    """Same sampling as JoinBake.crossfade: row 0 of the PNG is the top, y grows up in the scene."""
    pps = WORLD['game']['pixelsPerStep']
    boundary = 20000 * pps
    blend = 640
    half = blend / 2
    ch1, ch2 = WORLD['chapters']

    def road(chapter):
        best = None
        for prop in chapter['props']:
            if prop['layer'] != 'main' or 'road/road_main' not in prop['image']:
                continue
            height = prop['height']
            width = height * prop['pixelSize'][0] / max(1, prop['pixelSize'][1])
            left = (chapter['startStep'] + prop['step']) * pps + prop['dx']
            if left < boundary < left + width:
                cover = min(left + width, boundary + half) - max(left, boundary - half)
                if best is None or cover > best[0]:
                    best = (cover, prop['image'], left, width, height)
        return best

    def load(chapter, image):
        return Image.open(ASSETS / chapter['assetsFolder'] / (image + '.png')).convert('RGBA')

    _, image1, left1, width1, height1 = road(ch1)
    _, image2, left2, width2, height2 = road(ch2)
    im1, im2 = load(ch1, image1), load(ch2, image2)
    out_h = int(round(max(height1, height2)))

    def sample(im, origin, width, height, world_x, y_from_bottom):
        if width <= 0 or height <= 0:
            return (0, 0, 0, 0)
        src_x = (world_x - origin) / width * im.size[0]
        src_y = y_from_bottom / height * im.size[1]
        ix, iy_top = int(src_x), im.size[1] - 1 - int(src_y)
        if ix < 0 or iy_top < 0 or ix >= im.size[0] or iy_top >= im.size[1]:
            return (0, 0, 0, 0)
        p = im.getpixel((ix, iy_top))
        a = p[3] / 255
        if a <= 0.001:
            return (0, 0, 0, 0)
        return (p[0] / 255 / a, p[1] / 255 / a, p[2] / 255 / a, a)

    # Ground band: the opaque walking surface, not the transparent sky in the road PNG.
    y_ground = 80
    row = []
    for x in range(blend):
        t = x / (blend - 1)
        world_x = boundary - half + x + 0.5
        a = sample(im1, left1, width1, height1, world_x, y_ground)
        b = sample(im2, left2, width2, height2, world_x, y_ground)
        alpha = a[3] * (1 - t) + b[3] * t
        rgb = tuple((a[i] * (1 - t) + b[i] * t) * alpha for i in range(3))
        row.append(tuple(int(round(c * 255)) for c in rgb))
    # Every column is the lerp of the two source texels at that world x, not a hard switch.
    lerp_error = 0
    for x in range(blend):
        t = x / (blend - 1)
        world_x = boundary - half + x + 0.5
        a = sample(im1, left1, width1, height1, world_x, y_ground)
        b = sample(im2, left2, width2, height2, world_x, y_ground)
        alpha = a[3] * (1 - t) + b[3] * t
        expect = tuple(int(round((a[i] * (1 - t) + b[i] * t) * alpha * 255)) for i in range(3))
        lerp_error = max(lerp_error, sum(abs(row[x][c] - expect[c]) for c in range(3)))
    hard = sum(abs(row[blend // 2 - 1][c] - row[blend // 2][c]) for c in range(3))
    # A butt joint would swap the full source colours in one column.
    a = sample(im1, left1, width1, height1, boundary, y_ground)
    b = sample(im2, left2, width2, height2, boundary, y_ground)
    butt = sum(abs(int(round(a[i] * a[3] * 255)) - int(round(b[i] * b[3] * 255))) for i in range(3))
    sheet = Image.new('RGB', (blend, 80))
    for y in range(80):
        for x, px in enumerate(row):
            sheet.putpixel((x, y), px)
    out = Path('/opt/cursor/artifacts/chapter-join-road.png')
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return {'edge_error': lerp_error, 'max_step': hard, 'raw_jump': butt}


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
    def test_chapter_join_is_baked_into_pixels_not_a_mask_gradient(self):
        # fe17f04 widened the crop and faded the mask. On device the edge stayed a hard rectangle.
        self.assertNotIn('u_fade0', SCENE)
        self.assertNotIn('chapterMaskSprite', SCENE)
        self.assertNotIn('fadeLeft ? rawLeft', SCENE)
        self.assertIn('SKSpriteNode(color: .white, size: CGSize(width: right - left', SCENE)
        self.assertIn('installBakedJoins()', SCENE)
        self.assertIn('chapterJoinRoad', SCENE)
        self.assertIn('chapterJoinUnderground', SCENE)
        self.assertIn('private static let chapterBlend: CGFloat = 640', SCENE)
        sheet = baked_boundary_sheet()
        # Ends match the source chapters. The middle is between them, not a second hard step.
        self.assertLess(sheet['edge_error'], 3)
        self.assertGreater(sheet['raw_jump'], 30)
        self.assertLess(sheet['max_step'], sheet['raw_jump'] * 0.25)

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
