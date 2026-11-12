#!/usr/bin/env python3
"""Export-compliance key for the Postman app target. Not an ASC client.

Source check (always):
- Postman/Info.plist stores ITSAppUsesNonExemptEncryption as a Boolean false,
  not the string "false" or "NO".
- Debug and Release of the application target set
  INFOPLIST_KEY_ITSAppUsesNonExemptEncryption = NO (unquoted build setting).
- PRODUCT_BUNDLE_IDENTIFIER in Postman/Config/App.xcconfig is games.mazkof.postman.

Archive check (optional path to the built Info.plist inside the .app or archive):
  python3 tools/check_export_compliance.py path/to/Info.plist
  The built key must be a Boolean false, and CFBundleIdentifier must match.

Release gate, after a Mac archive, before telling anyone a build is testable:
  ASC processing state VALID does not mean TestFlight availability.
  Also confirm that build's export compliance is cleared, that the tester is
  already in the existing internal group, and that the build's beta state
  allows testing. This script does not call ASC, does not create groups,
  and does not submit a review.
"""
import plistlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INFO = ROOT / "Postman/Info.plist"
PBX = ROOT / "Postman.xcodeproj/project.pbxproj"
XCCONFIG = ROOT / "Postman/Config/App.xcconfig"
YML = ROOT / "project.yml"
BUNDLE_ID = "games.mazkof.postman"

fails = []

def check(ok, msg):
    if not ok:
        fails.append(msg)

with INFO.open("rb") as fh:
    src = plistlib.load(fh)
value = src.get("ITSAppUsesNonExemptEncryption", None)
check(value is False, f"Info.plist ITSAppUsesNonExemptEncryption is {value!r}, expected Boolean false")
check(not isinstance(value, str), "Info.plist export key must not be a string")

text = PBX.read_text(encoding="utf-8")
unquoted = re.findall(r"INFOPLIST_KEY_ITSAppUsesNonExemptEncryption = NO;", text)
quoted = re.findall(r'INFOPLIST_KEY_ITSAppUsesNonExemptEncryption = "(?:NO|false|YES|true)";', text)
check(len(unquoted) == 2, f"expected unquoted NO on Debug and Release, found {len(unquoted)}")
check(not quoted, f"export key is a quoted string in the project: {quoted}")

yml = YML.read_text(encoding="utf-8")
check("INFOPLIST_KEY_ITSAppUsesNonExemptEncryption: NO" in yml, "project.yml is missing the Boolean NO setting")

xc = XCCONFIG.read_text(encoding="utf-8")
found = re.search(r"^PRODUCT_BUNDLE_IDENTIFIER\s*=\s*(\S+)\s*$", xc, re.M)
check(found and found.group(1) == BUNDLE_ID, f"bundle id in App.xcconfig is {found.group(1) if found else None}")

if len(sys.argv) > 1:
    built_path = Path(sys.argv[1])
    with built_path.open("rb") as fh:
        built = plistlib.load(fh)
    built_flag = built.get("ITSAppUsesNonExemptEncryption", None)
    built_id = built.get("CFBundleIdentifier")
    check(built_flag is False, f"archive ITSAppUsesNonExemptEncryption is {built_flag!r}, expected Boolean false")
    check(not isinstance(built_flag, str), "archive export key must not be a string")
    check(built_id == BUNDLE_ID, f"archive CFBundleIdentifier is {built_id!r}")

if fails:
    print("export compliance check failed:")
    for msg in fails:
        print(" -", msg)
    sys.exit(1)

print("export compliance source check passed")
print(f"  ITSAppUsesNonExemptEncryption Boolean false, bundle id {BUNDLE_ID}")
if len(sys.argv) > 1:
    print(f"  archive Info.plist checked: {sys.argv[1]}")
else:
    print("  archive Info.plist not passed; on Mac, re-run with the built plist before calling a build testable")
print("  ASC VALID is not TestFlight availability: also check export compliance, the existing internal group, and beta state")
