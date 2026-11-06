import Foundation

// Порт postman_fal/cutout/rig_walk.py (эталон цикла ходьбы, 8 кадров, 12 fps).
// Вся математика — в координатах исходника рига (Y вниз), как в numpy-версии.
// PAD из Python опущен: это общий сдвиг, на результат не влияет.
// Для каждого кадра считается аффинная матрица каждой части; PostmanRigNode
// раскладывает её на позицию + поворот SKSpriteNode.

/// Матрица [[a b c] [d e f] [0 0 1]] — как 3×3 в rig_walk.py.
struct Affine2D: Equatable {
    var a: Double, b: Double, c: Double
    var d: Double, e: Double, f: Double

    static let identity = Affine2D(a: 1, b: 0, c: 0, d: 0, e: 1, f: 0)

    static func * (l: Affine2D, r: Affine2D) -> Affine2D {
        Affine2D(
            a: l.a * r.a + l.b * r.d,
            b: l.a * r.b + l.b * r.e,
            c: l.a * r.c + l.b * r.f + l.c,
            d: l.d * r.a + l.e * r.d,
            e: l.d * r.b + l.e * r.e,
            f: l.d * r.c + l.e * r.f + l.f
        )
    }

    func apply(_ p: Double2) -> Double2 {
        Double2(a * p.x + b * p.y + c, d * p.x + e * p.y + f)
    }

    /// Угол поворота в системе Y-вниз (в радианах; + = по часовой на экране).
    var angle: Double { atan2(d, a) }

    /// T(dx,dy)
    static func translate(_ dx: Double, _ dy: Double) -> Affine2D {
        Affine2D(a: 1, b: 0, c: dx, d: 0, e: 1, f: dy)
    }

    /// Rot(deg, c) = T(c) · R(deg) · T(−c)
    static func rotate(_ deg: Double, around p: Double2) -> Affine2D {
        let r = deg * .pi / 180
        let cs = cos(r), sn = sin(r)
        let rot = Affine2D(a: cs, b: -sn, c: 0, d: sn, e: cs, f: 0)
        return translate(p.x, p.y) * rot * translate(-p.x, -p.y)
    }
}

/// Порядок отрисовки частей — точно как в rig_walk.py (снизу вверх).
enum RigPart: Int, CaseIterable {
    case farShin, farFoot, farThigh, farArmUpper, farArmLower
    case nearShin, nearFoot, nearThigh
    case torso, head, staff
    case nearArmUpper, nearArmLower

    /// Имя PNG в GameAssets/Rig/parts.
    var imageName: String {
        switch self {
        case .farShin, .nearShin: return "shin"
        case .farFoot, .nearFoot: return "foot"
        case .farThigh, .nearThigh: return "thigh"
        case .farArmUpper, .nearArmUpper: return "arm_upper"
        case .farArmLower, .nearArmLower: return "arm_lower"
        case .torso: return "torso"
        case .head: return "head"
        case .staff: return "staff"
        }
    }

    /// Дальние конечности затемнены ×0.62 (DK в rig_walk.py).
    var isDark: Bool {
        switch self {
        case .farShin, .farFoot, .farThigh, .farArmUpper, .farArmLower: return true
        default: return false
        }
    }
}

struct RigWalk {
    static let frameCount = 8
    static let fps: Double = 12
    static let frameNames = ["01_contact_R", "02_down_R", "03_passing_R", "04_up_R",
                             "05_contact_L", "06_down_L", "07_passing_L", "08_up_L"]

    // Ключи на 8 кадров (+град = мах вперёд) — копия из rig_walk.py.
    static let thigh: [Double] = [19, 14, 2, -12, -19, -22, 6, 20]
    static let knee: [Double] = [4, 40, 8, 2, 10, 46, 58, 26]
    static let support: [Bool] = [true, true, true, true, false, false, false, false]
    static let staffTipX: [Double] = [40, 25, 10, -5, -20, -35, 0, 30]
    static let staffLift: [Double] = [0, 0, 0, 0, 0, 0, -30, -12]

    /// Джиттер торса+головы: точная последовательность random.seed(4) из rig_walk.py
    /// (random.choice([-1,0,1]) для dx, затем dy, на каждый кадр).
    static let referenceJitter: [(Double, Double)] = [
        (-1, 0), (-1, 1), (0, 0), (-1, -1), (-1, -1), (0, 1), (0, -1), (-1, 1)
    ]

    let rig: RigConfig

    private struct Leg {
        let thigh: Affine2D
        let shin: Affine2D
        let foot: Affine2D
        let lowestY: Double
    }

    private func p(_ name: String) -> Double2 { rig.pivot(name) }

    private func leg(_ mb: Affine2D, _ f: Int) -> Leg {
        let k = ((f % 8) + 8) % 8
        let mt = mb * Affine2D.rotate(-RigWalk.thigh[k], around: p("hip"))
        let ms = mt * Affine2D.rotate(RigWalk.knee[k], around: p("knee"))
        let sh = -RigWalk.thigh[k] + RigWalk.knee[k]
        var fa = RigWalk.support[k] ? -sh : -0.4 * sh
        if k == 0 { fa -= 8 }
        if k == 3 { fa += 10 }
        let mf = ms * Affine2D.rotate(fa, around: p("ankle"))
        // нижняя точка стопы: max y из (340,1112) и (480,1112)
        let low = max(mf.apply(Double2(340, 1112)).y, mf.apply(Double2(480, 1112)).y)
        return Leg(thigh: mt, shin: ms, foot: mf, lowestY: low)
    }

    /// Вертикальный сдвиг тела на кадр, чтобы опорная стопа стояла на земле (dys).
    func bodyDrop() -> [Double] {
        (0..<RigWalk.frameCount).map { f in
            rig.groundY - max(leg(.identity, f).lowestY, leg(.identity, f + 4).lowestY)
        }
    }

    /// Матрицы всех частей для кадра f (0…7) с заданным джиттером торса/головы.
    func pose(frame f: Int, jitter: (Double, Double)) -> [RigPart: Affine2D] {
        let f = ((f % 8) + 8) % 8
        let dys = bodyDrop()
        let ground = rig.groundY
        let mb = Affine2D.translate(0, dys[f])
        let sw = -0.3 * RigWalk.thigh[f]
        var out: [RigPart: Affine2D] = [:]

        // дальняя нога (фаза f+4), затемнённая
        let far = leg(mb, f + 4)
        out[.farShin] = far.shin
        out[.farFoot] = far.foot
        out[.farThigh] = far.thigh
        // дальняя рука
        let ma = mb * Affine2D.rotate(-sw * 0.8, around: p("shoulder"))
        out[.farArmUpper] = ma
        out[.farArmLower] = ma * Affine2D.rotate(-8, around: p("elbow"))
        // ближняя нога (бедро поверх колена)
        let near = leg(mb, f)
        out[.nearShin] = near.shin
        out[.nearFoot] = near.foot
        out[.nearThigh] = near.thigh
        // торс и голова — общий джиттер; голова жёсткая ±0.5°
        let j = Affine2D.translate(jitter.0, jitter.1) * mb
        out[.torso] = j
        out[.head] = j * Affine2D.rotate(0.5 * sin(Double(f) * .pi / 4), around: p("neck"))
        // ближняя рука и посох, упирающийся в землю
        let mu = mb * Affine2D.rotate(-sw, around: p("shoulder"))
        let ml = mu * Affine2D.rotate(-sw * 0.2, around: p("elbow"))
        let grip = ml.apply(Double2(500, 675))
        let tip = Double2(p("staff_tip").x + RigWalk.staffTipX[f] - 10, ground + RigWalk.staffLift[f])
        let g0 = p("staff_grip"), t0 = p("staff_tip")
        let v0 = t0 - g0, v1 = tip - grip
        let ang = (atan2(v1.y, v1.x) - atan2(v0.y, v0.x)) * 180 / .pi
        out[.staff] = Affine2D.translate(grip.x - g0.x, grip.y - g0.y) * Affine2D.rotate(ang, around: g0)
        out[.nearArmUpper] = mu
        out[.nearArmLower] = ml
        return out
    }
}
