#!/usr/bin/env python3
"""project.pbxproj must be a project Xcode can open.

Каждый ID объекта встречается один раз. fileRef у PBXBuildFile ведёт на
PBXFileReference. Локализации — PBXVariantGroup, и каждый её ребёнок тоже
PBXFileReference: иначе Xcode читает build file как file reference и пишет
«The project is damaged» (-[PBXFileReference buildPhase]).
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PBX = ROOT / "Postman.xcodeproj/project.pbxproj"
sys.path.insert(0, str(ROOT / "tools"))

DEF = re.compile(r"^(\t\t)([0-9A-F]{24})(?: /\* .*? \*/)? = \{")
ISA = re.compile(r"\bisa = ([A-Za-z0-9]+);")
FILE_REF = re.compile(r"\bfileRef = ([0-9A-F]{24})\b")
CHILD = re.compile(r"\b([0-9A-F]{24})\b")

FAILS = []


def fail(msg):
    FAILS.append(msg)


def parse_objects(text):
    """ID определения → тело. Повторный ID возвращается отдельно и в объект не затирается."""
    objects = {}
    duplicates = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        match = DEF.match(lines[i])
        if not match:
            i += 1
            continue
        oid = match.group(2)
        if lines[i].rstrip().endswith("};"):
            body = lines[i]
            i += 1
        else:
            buf = [lines[i]]
            i += 1
            while i < len(lines) and lines[i] != "\t\t};":
                buf.append(lines[i])
                i += 1
            if i >= len(lines):
                fail(f"{oid} is not closed")
                break
            buf.append(lines[i])
            body = "\n".join(buf)
            i += 1
        if oid in objects:
            duplicates.append(oid)
        else:
            objects[oid] = body
    return objects, duplicates


def problems(text):
    objects, duplicates = parse_objects(text)
    found = []
    for oid in duplicates:
        found.append(f"{oid} is defined more than once")
    for oid, body in objects.items():
        isa = ISA.search(body)
        if not isa:
            found.append(f"{oid} has no isa")
            continue
        if isa.group(1) != "PBXBuildFile":
            continue
        ref = FILE_REF.search(body)
        if not ref:
            found.append(f"{oid} is a PBXBuildFile without fileRef")
            continue
        target = objects.get(ref.group(1))
        if target is None:
            found.append(f"{oid} fileRef {ref.group(1)} is not an object")
            continue
        kind = ISA.search(target)
        name = kind.group(1) if kind else "unknown"
        if name == "PBXFileReference":
            continue
        if name == "PBXVariantGroup":
            children = CHILD.findall(target)
            # Первый ID в теле — сам объект в строке заголовка не входит: тело начинается с «isa».
            child_ids = [c for c in children if c in objects and c != ref.group(1)]
            if not child_ids or any(ISA.search(objects[c]).group(1) != "PBXFileReference" for c in child_ids):
                found.append(f"{oid} variant group {ref.group(1)} has a child that is not a PBXFileReference")
            continue
        found.append(f"{oid} fileRef {ref.group(1)} is {name}, not a PBXFileReference")
    return found


def expect_problem(text, needle):
    got = problems(text)
    if not any(needle in item for item in got):
        fail(f"the damaged-project sample was not caught ({needle}); got {got}")


MAP = "A1B2C3D4E5F60718293A4B5C"
PED = "B2C3D4E5F60718293A4B5C6D"
# Тот самый конфликт: ID MapAtlas переиспользованы для PedometerStepSource.
BROKEN = f"""
\t\t{MAP} /* MapAtlas.swift in Sources */ = {{isa = PBXBuildFile; fileRef = {PED} /* MapAtlas.swift */; }};
\t\t{PED} /* PedometerStepSource.swift in Sources */ = {{isa = PBXBuildFile; fileRef = {MAP} /* PedometerStepSource.swift */; }};
\t\t{MAP} /* PedometerStepSource.swift */ = {{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = PedometerStepSource.swift; sourceTree = "<group>"; }};
\t\t{PED} /* MapAtlas.swift */ = {{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = MapAtlas.swift; sourceTree = "<group>"; }};
"""
expect_problem(BROKEN, "is defined more than once")

ORPHAN_BUILD = "111111111111111111111111"
ORPHAN_REF = "222222222222222222222222"
expect_problem(
    f"""
\t\t{ORPHAN_BUILD} /* Missing.swift in Sources */ = {{isa = PBXBuildFile; fileRef = {ORPHAN_REF} /* Missing.swift */; }};
\t\t{ORPHAN_REF} /* Missing.swift in Sources */ = {{isa = PBXBuildFile; fileRef = {ORPHAN_BUILD} /* Missing.swift */; }};
""",
    "not a PBXFileReference",
)

import gen_xcodeproj as gx  # noqa: E402

notice = gx.object_id("fileref:App/NoticePlan.swift", set())
salted = gx.object_id("fileref:App/NoticePlan.swift", {notice})
if salted == notice or len(salted) != 24:
    fail("a colliding id must be salted instead of reused")
if gx.object_id("fileref:App/NoticePlan.swift", set()) != notice:
    fail("an uncontested id must stay the md5 prefix")
ped_ref = gx.object_id("fileref:Services/PedometerStepSource.swift", set())
ped_build = gx.object_id("buildfile:Services/PedometerStepSource.swift", set())
plan_build = gx.object_id("buildfile:App/NoticePlan.swift", set())
if len({notice, salted, ped_ref, ped_build, plan_build}) != 5:
    fail("the new file ids are not distinct")

text = PBX.read_text(encoding="utf-8")
for item in problems(text):
    fail(item)
for needed in (ped_ref, ped_build, notice, plan_build):
    if text.count(needed) < 2:
        fail(f"{needed} is missing from the project")

# Apple plutil здесь нет. libplist отклоняет незакавыченные пути Xcode
# (ru.lproj/InfoPlist.strings), поэтому это не ворота. openstep-parser читает
# файл целиком; расхождение числа объектов значит, что повторный ID схлопнулся.
try:
    import openstep_parser
except ImportError:
    openstep_parser = None
if openstep_parser is not None:
    parsed = openstep_parser.OpenStepDecoder.ParseFromString(text)
    declared, dupes = parse_objects(text)
    if dupes or len(parsed["objects"]) != len(declared):
        fail("openstep parse dropped a duplicate object id")

if FAILS:
    print("\n".join(FAILS))
    sys.exit(1)
print("xcodeproj checks ok")
