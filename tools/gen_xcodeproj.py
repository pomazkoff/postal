#!/usr/bin/env python3
"""Генерирует Postman.xcodeproj (project.pbxproj + общая схема) без Xcode/XcodeGen.

Сканирует Postman/**/*.swift, поэтому после добавления файлов достаточно перезапустить:
    python3 tools/gen_xcodeproj.py
ID объектов детерминированы (md5 от ключа), 24 hex-символа.
Альтернатива — XcodeGen: `xcodegen generate` по project.yml (результат эквивалентен).
"""
import hashlib, os, re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = "Postman"
TARGET = "Postman"
PROJ = os.path.join(ROOT, "Postman.xcodeproj")

# База Info.plist = английский (development region). Русский текст — в ru.lproj/InfoPlist.strings.
HEALTH_SHARE = ("The postman walks when you do. The game reads your step count from Health "
                "so it can move him along the road. The data stays on this device.")
LOCATION_WHEN_IN_USE = ("A rough location is only for the weather in the Valley: if it is raining or snowing "
                        "where you are, it rains or snows on the postman too. Precise coordinates are not used "
                        "and are not stored.")
HEALTH_UPDATE = "The game does not write anything to Health."

def oid(key):
    return hashlib.md5(key.encode("utf-8")).hexdigest()[:24].upper()

SAFE = re.compile(r"^[A-Za-z0-9_./]+$")
def q(v):
    if isinstance(v, (list, tuple)):
        return "(\n" + "".join(f"\t\t\t\t\t{q(x)},\n" for x in v) + "\t\t\t\t)"
    s = str(v)
    if SAFE.match(s):
        return s
    s = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{s}"'

# ---------- collect files ----------
GROUP_ORDER = ["App", "Services", "Model", "Scene", "UI", "Config"]
swift = {}   # group -> [file]
for g in GROUP_ORDER:
    d = os.path.join(ROOT, SRC, g)
    if os.path.isdir(d):
        swift[g] = sorted(f for f in os.listdir(d) if f.endswith(".swift"))
config_files = sorted(f for f in os.listdir(os.path.join(ROOT, SRC, "Config")) if f.endswith(".xcconfig"))
assert config_files == ["App.xcconfig"], config_files

objs = {}    # id -> (isa, body-lines, comment)
def add(key, isa, fields, comment):
    i = oid(key)
    assert i not in objs, f"duplicate id for {key}"
    objs[i] = (isa, fields, comment)
    return i

# file references + build files
src_build_files = []
group_children = {g: [] for g in GROUP_ORDER}
for g, files in swift.items():
    for f in files:
        fr = add(f"fileref:{g}/{f}", "PBXFileReference",
                 [("lastKnownFileType", "sourcecode.swift"), ("path", f), ("sourceTree", "<group>")], f)
        bf = add(f"buildfile:{g}/{f}", "PBXBuildFile", [("fileRef", (fr, f))], f"{f} in Sources")
        group_children[g].append((fr, f))
        src_build_files.append((bf, f"{f} in Sources"))

xcconfig_ref = add("fileref:Config/App.xcconfig", "PBXFileReference",
                   [("lastKnownFileType", "text.xcconfig"), ("path", "App.xcconfig"), ("sourceTree", "<group>")], "App.xcconfig")
group_children["Config"].append((xcconfig_ref, "App.xcconfig"))

assets_ref = add("fileref:Assets.xcassets", "PBXFileReference",
                 [("lastKnownFileType", "folder.assetcatalog"), ("path", "Assets.xcassets"), ("sourceTree", "<group>")], "Assets.xcassets")
game_ref = add("fileref:GameAssets", "PBXFileReference",
               [("lastKnownFileType", "folder"), ("path", "GameAssets"), ("sourceTree", "<group>")], "GameAssets")
plist_ref = add("fileref:Info.plist", "PBXFileReference",
                [("lastKnownFileType", "text.plist.xml"), ("path", "Info.plist"), ("sourceTree", "<group>")], "Info.plist")
ent_ref = add("fileref:Postman.entitlements", "PBXFileReference",
              [("lastKnownFileType", "text.plist.entitlements"), ("path", "Postman.entitlements"), ("sourceTree", "<group>")], "Postman.entitlements")
product_ref = add("fileref:product", "PBXFileReference",
                  [("explicitFileType", "wrapper.application"), ("includeInIndex", "0"), ("path", "Postman.app"), ("sourceTree", "BUILT_PRODUCTS_DIR")], "Postman.app")

assets_bf = add("buildfile:Assets.xcassets", "PBXBuildFile", [("fileRef", (assets_ref, "Assets.xcassets"))], "Assets.xcassets in Resources")
game_bf = add("buildfile:GameAssets", "PBXBuildFile", [("fileRef", (game_ref, "GameAssets"))], "GameAssets in Resources")

def variant_group(name, file_type):
    """en.lproj + ru.lproj одного файла → PBXVariantGroup."""
    children = []
    for lang in ("en", "ru"):
        rel = f"Resources/{lang}.lproj/{name}"
        fr = add(f"fileref:{rel}", "PBXFileReference",
                 [("lastKnownFileType", file_type), ("name", lang), ("path", f"{lang}.lproj/{name}"), ("sourceTree", "<group>")],
                 lang)
        children.append((fr, lang))
    return add(f"variant:{name}", "PBXVariantGroup",
               [("children", children), ("name", name), ("sourceTree", "<group>")], name)

loc_strings = variant_group("Localizable.strings", "text.plist.strings")
loc_dict = variant_group("Localizable.stringsdict", "text.plist.stringsdict")
info_strings = variant_group("InfoPlist.strings", "text.plist.strings")
resources_group = add("group:Resources", "PBXGroup",
                      [("children", [(loc_strings, "Localizable.strings"), (loc_dict, "Localizable.stringsdict"),
                                     (info_strings, "InfoPlist.strings")]),
                       ("path", "Resources"), ("sourceTree", "<group>")], "Resources")
loc_strings_bf = add("buildfile:Localizable.strings", "PBXBuildFile", [("fileRef", (loc_strings, "Localizable.strings"))], "Localizable.strings in Resources")
loc_dict_bf = add("buildfile:Localizable.stringsdict", "PBXBuildFile", [("fileRef", (loc_dict, "Localizable.stringsdict"))], "Localizable.stringsdict in Resources")
info_strings_bf = add("buildfile:InfoPlist.strings", "PBXBuildFile", [("fileRef", (info_strings, "InfoPlist.strings"))], "InfoPlist.strings in Resources")

# groups
sub_groups = []
for g in GROUP_ORDER:
    if not group_children[g]:
        continue
    gid = add(f"group:{g}", "PBXGroup", [("children", group_children[g]), ("path", g), ("sourceTree", "<group>")], g)
    sub_groups.append((gid, g))
products_group = add("group:Products", "PBXGroup", [("children", [(product_ref, "Postman.app")]), ("name", "Products"), ("sourceTree", "<group>")], "Products")
src_group = add("group:Postman", "PBXGroup",
                [("children", sub_groups + [(resources_group, "Resources"), (assets_ref, "Assets.xcassets"), (game_ref, "GameAssets"), (ent_ref, "Postman.entitlements"), (plist_ref, "Info.plist")]),
                 ("path", SRC), ("sourceTree", "<group>")], SRC)
main_group = add("group:main", "PBXGroup", [("children", [(src_group, SRC), (products_group, "Products")]), ("sourceTree", "<group>")], None)

# build phases
sources_phase = add("phase:sources", "PBXSourcesBuildPhase",
                    [("buildActionMask", "2147483647"), ("files", src_build_files), ("runOnlyForDeploymentPostprocessing", "0")], "Sources")
frameworks_phase = add("phase:frameworks", "PBXFrameworksBuildPhase",
                       [("buildActionMask", "2147483647"), ("files", []), ("runOnlyForDeploymentPostprocessing", "0")], "Frameworks")
resources_phase = add("phase:resources", "PBXResourcesBuildPhase",
                      [("buildActionMask", "2147483647"),
                       ("files", [(assets_bf, "Assets.xcassets in Resources"), (game_bf, "GameAssets in Resources"),
                                  (loc_strings_bf, "Localizable.strings in Resources"),
                                  (loc_dict_bf, "Localizable.stringsdict in Resources"),
                                  (info_strings_bf, "InfoPlist.strings in Resources")]),
                       ("runOnlyForDeploymentPostprocessing", "0")], "Resources")

# build settings
proj_common = {
    "ALWAYS_SEARCH_USER_PATHS": "NO",
    "ASSETCATALOG_COMPILER_GENERATE_SWIFT_ASSET_SYMBOL_EXTENSIONS": "YES",
    "CLANG_ANALYZER_NONNULL": "YES",
    "CLANG_CXX_LANGUAGE_STANDARD": "gnu++20",
    "CLANG_ENABLE_MODULES": "YES",
    "CLANG_ENABLE_OBJC_ARC": "YES",
    "CLANG_ENABLE_OBJC_WEAK": "YES",
    "COPY_PHASE_STRIP": "NO",
    "ENABLE_STRICT_OBJC_MSGSEND": "YES",
    "ENABLE_USER_SCRIPT_SANDBOXING": "YES",
    "GCC_C_LANGUAGE_STANDARD": "gnu17",
    "GCC_NO_COMMON_BLOCKS": "YES",
    "IPHONEOS_DEPLOYMENT_TARGET": "17.0",
    "LOCALIZATION_PREFERS_STRING_CATALOGS": "YES",
    "MTL_FAST_MATH": "YES",
    "SDKROOT": "iphoneos",
}
proj_debug = dict(proj_common, **{
    "DEBUG_INFORMATION_FORMAT": "dwarf",
    "ENABLE_TESTABILITY": "YES",
    "GCC_DYNAMIC_NO_PIC": "NO",
    "GCC_OPTIMIZATION_LEVEL": "0",
    "GCC_PREPROCESSOR_DEFINITIONS": ["DEBUG=1", "$(inherited)"],
    "MTL_ENABLE_DEBUG_INFO": "INCLUDE_SOURCE",
    "ONLY_ACTIVE_ARCH": "YES",
    "SWIFT_ACTIVE_COMPILATION_CONDITIONS": "DEBUG $(inherited)",
    "SWIFT_OPTIMIZATION_LEVEL": "-Onone",
})
proj_release = dict(proj_common, **{
    "DEBUG_INFORMATION_FORMAT": "dwarf-with-dsym",
    "ENABLE_NS_ASSERTIONS": "NO",
    "MTL_ENABLE_DEBUG_INFO": "NO",
    "SWIFT_COMPILATION_MODE": "wholemodule",
    "VALIDATE_PRODUCT": "YES",
})
target_common = {
    "ASSETCATALOG_COMPILER_APPICON_NAME": "AppIcon",
    "ASSETCATALOG_COMPILER_GLOBAL_ACCENT_COLOR_NAME": "AccentColor",
    "CODE_SIGN_ENTITLEMENTS": "Postman/Postman.entitlements",
    "CODE_SIGN_STYLE": "Automatic",
    "DEVELOPMENT_TEAM": "",
    "ENABLE_PREVIEWS": "YES",
    "GENERATE_INFOPLIST_FILE": "YES",
    "INFOPLIST_FILE": "Postman/Info.plist",
    "INFOPLIST_KEY_CFBundleDisplayName": "$(APP_DISPLAY_NAME)",
    "INFOPLIST_KEY_LSApplicationCategoryType": "public.app-category.games",
    "INFOPLIST_KEY_NSHealthShareUsageDescription": HEALTH_SHARE,
    "INFOPLIST_KEY_NSHealthUpdateUsageDescription": HEALTH_UPDATE,
    "INFOPLIST_KEY_NSLocationWhenInUseUsageDescription": LOCATION_WHEN_IN_USE,
    "INFOPLIST_KEY_UIApplicationSceneManifest_Generation": "YES",
    "INFOPLIST_KEY_UIApplicationSupportsIndirectInputEvents": "YES",
    "INFOPLIST_KEY_UILaunchScreen_Generation": "YES",
    "INFOPLIST_KEY_UIRequiresFullScreen": "YES",
    "INFOPLIST_KEY_UIStatusBarHidden": "YES",
    "INFOPLIST_KEY_UISupportedInterfaceOrientations": "UIInterfaceOrientationPortrait",
    "IPHONEOS_DEPLOYMENT_TARGET": "17.0",
    "LD_RUNPATH_SEARCH_PATHS": ["$(inherited)", "@executable_path/Frameworks"],
    "PRODUCT_NAME": "$(TARGET_NAME)",
    "SUPPORTED_PLATFORMS": "iphoneos iphonesimulator",
    "SUPPORTS_MACCATALYST": "NO",
    "SUPPORTS_MAC_DESIGNED_FOR_IPHONE_IPAD": "NO",
    "SUPPORTS_XR_DESIGNED_FOR_IPHONE_IPAD": "NO",
    "SWIFT_EMIT_LOC_STRINGS": "YES",
    "SWIFT_VERSION": "5.0",
    "TARGETED_DEVICE_FAMILY": "1",
}
# PRODUCT_BUNDLE_IDENTIFIER, MARKETING_VERSION, CURRENT_PROJECT_VERSION, APP_DISPLAY_NAME — из Config/App.xcconfig

def cfg(key, name, settings, base=None):
    fields = []
    if base:
        fields.append(("baseConfigurationReference", base))
    fields.append(("buildSettings", settings))
    fields.append(("name", name))
    return add(key, "XCBuildConfiguration", fields, name)

pd = cfg("cfg:proj:Debug", "Debug", proj_debug)
pr = cfg("cfg:proj:Release", "Release", proj_release)
td = cfg("cfg:target:Debug", "Debug", target_common, (xcconfig_ref, "App.xcconfig"))
tr = cfg("cfg:target:Release", "Release", target_common, (xcconfig_ref, "App.xcconfig"))
proj_cl = add("cl:proj", "XCConfigurationList",
              [("buildConfigurations", [(pd, "Debug"), (pr, "Release")]), ("defaultConfigurationIsVisible", "0"), ("defaultConfigurationName", "Release")],
              f'Build configuration list for PBXProject "{TARGET}"')
target_cl = add("cl:target", "XCConfigurationList",
                [("buildConfigurations", [(td, "Debug"), (tr, "Release")]), ("defaultConfigurationIsVisible", "0"), ("defaultConfigurationName", "Release")],
                f'Build configuration list for PBXNativeTarget "{TARGET}"')

target = add("target:Postman", "PBXNativeTarget",
             [("buildConfigurationList", (target_cl, f'Build configuration list for PBXNativeTarget "{TARGET}"')),
              ("buildPhases", [(sources_phase, "Sources"), (frameworks_phase, "Frameworks"), (resources_phase, "Resources")]),
              ("buildRules", []), ("dependencies", []), ("name", TARGET), ("productName", TARGET),
              ("productReference", (product_ref, "Postman.app")), ("productType", "com.apple.product-type.application")],
             TARGET)
project = add("project", "PBXProject",
              [("attributes", "RAW:{\n\t\t\t\tBuildIndependentTargetsInParallel = 1;\n\t\t\t\tLastSwiftUpdateCheck = 1500;\n\t\t\t\tLastUpgradeCheck = 1500;\n\t\t\t\tTargetAttributes = {\n\t\t\t\t\t"
                + target + " = {\n\t\t\t\t\t\tCreatedOnToolsVersion = 15.0;\n\t\t\t\t\t\tSystemCapabilities = {\n\t\t\t\t\t\t\tcom.apple.HealthKit = {\n\t\t\t\t\t\t\t\tenabled = 1;\n\t\t\t\t\t\t\t};\n\t\t\t\t\t\t};\n\t\t\t\t\t};\n\t\t\t\t};\n\t\t\t}"),
               ("buildConfigurationList", (proj_cl, f'Build configuration list for PBXProject "{TARGET}"')),
               ("compatibilityVersion", "Xcode 14.0"), ("developmentRegion", "en"), ("hasScannedForEncodings", "0"),
               ("knownRegions", "RAW:(\n\t\t\t\tru,\n\t\t\t\ten,\n\t\t\t\tBase,\n\t\t\t)"),
               ("mainGroup", main_group), ("productRefGroup", (products_group, "Products")),
               ("projectDirPath", ""), ("projectRoot", ""), ("targets", [(target, TARGET)])],
              "Project object")

# ---------- serialize ----------
def ref(v):
    if isinstance(v, tuple):
        i, c = v
        return f"{i} /* {c} */" if c else i
    return v

def val(v, indent):
    t = "\t" * indent
    if isinstance(v, str) and v.startswith("RAW:"):
        return v[4:]
    if isinstance(v, tuple):
        return ref(v)
    if isinstance(v, dict):
        lines = ["{"]
        for k in sorted(v):
            x = v[k]
            if isinstance(x, list):
                inner = "".join(f"{t}\t\t{q(e)},\n" for e in x)
                lines.append(f"{t}\t{k} = (\n{inner}{t}\t);")
            else:
                lines.append(f"{t}\t{q(k)} = {q(x)};")
        lines.append(f"{t}}}")
        return "\n".join(lines)
    if isinstance(v, list):
        inner = "".join(f"{t}\t{ref(e) if isinstance(e, tuple) else q(e)},\n" for e in v)
        return f"(\n{inner}{t})"
    if v in objs:
        return v
    return q(v)

SECTIONS = ["PBXBuildFile", "PBXFileReference", "PBXFrameworksBuildPhase", "PBXGroup", "PBXNativeTarget",
            "PBXProject", "PBXResourcesBuildPhase", "PBXSourcesBuildPhase", "PBXVariantGroup",
            "XCBuildConfiguration", "XCConfigurationList"]
out = ["// !$*UTF8*$!", "{", "\tarchiveVersion = 1;", "\tclasses = {", "\t};", "\tobjectVersion = 56;", "\tobjects = {"]
for sec in SECTIONS:
    items = sorted((i, o) for i, o in objs.items() if o[0] == sec)
    if not items:
        continue
    out.append("")
    out.append(f"/* Begin {sec} section */")
    for i, (isa, fields, comment) in items:
        head = f"{i} /* {comment} */" if comment else i
        if sec in ("PBXBuildFile", "PBXFileReference"):
            body = " ".join([f"isa = {isa};"] + [f"{k} = {val(v, 0)};" for k, v in fields])
            out.append(f"\t\t{head} = {{{body} }};")
        else:
            out.append(f"\t\t{head} = {{")
            out.append(f"\t\t\tisa = {isa};")
            for k, v in fields:
                out.append(f"\t\t\t{k} = {val(v, 3)};")
            out.append("\t\t};")
    out.append(f"/* End {sec} section */")
out += ["\t};", f"\trootObject = {project} /* Project object */;", "}", ""]

os.makedirs(os.path.join(PROJ, "project.xcworkspace"), exist_ok=True)
with open(os.path.join(PROJ, "project.pbxproj"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(out))
with open(os.path.join(PROJ, "project.xcworkspace", "contents.xcworkspacedata"), "w", encoding="utf-8") as fh:
    fh.write('<?xml version="1.0" encoding="UTF-8"?>\n<Workspace\n   version = "1.0">\n   <FileRef\n      location = "self:">\n   </FileRef>\n</Workspace>\n')

# shared scheme
scheme_dir = os.path.join(PROJ, "xcshareddata", "xcschemes")
os.makedirs(scheme_dir, exist_ok=True)
br = f'''            <BuildableReference
               BuildableIdentifier = "primary"
               BlueprintIdentifier = "{target}"
               BuildableName = "Postman.app"
               BlueprintName = "{TARGET}"
               ReferencedContainer = "container:Postman.xcodeproj">
            </BuildableReference>'''
scheme = f'''<?xml version="1.0" encoding="UTF-8"?>
<Scheme
   LastUpgradeVersion = "1500"
   version = "1.7">
   <BuildAction
      parallelizeBuildables = "YES"
      buildImplicitDependencies = "YES">
      <BuildActionEntries>
         <BuildActionEntry
            buildForTesting = "YES"
            buildForRunning = "YES"
            buildForProfiling = "YES"
            buildForArchiving = "YES"
            buildForAnalyzing = "YES">
{br.replace(chr(10) + "            ", chr(10) + "               ").replace("            <Buildable", "               <Buildable", 1)}
         </BuildActionEntry>
      </BuildActionEntries>
   </BuildAction>
   <TestAction
      buildConfiguration = "Debug"
      selectedDebuggerIdentifier = "Xcode.DebuggerFoundation.Debugger.LLDB"
      selectedLauncherIdentifier = "Xcode.DebuggerFoundation.Launcher.LLDB"
      shouldUseLaunchSchemeArgsEnv = "YES"
      shouldAutocreateTestPlan = "YES">
   </TestAction>
   <LaunchAction
      buildConfiguration = "Debug"
      selectedDebuggerIdentifier = "Xcode.DebuggerFoundation.Debugger.LLDB"
      selectedLauncherIdentifier = "Xcode.DebuggerFoundation.Launcher.LLDB"
      launchStyle = "0"
      useCustomWorkingDirectory = "NO"
      ignoresPersistentStateOnLaunch = "NO"
      debugDocumentVersioning = "YES"
      debugServiceExtension = "internal"
      allowLocationSimulation = "YES">
      <BuildableProductRunnable
         runnableDebuggingMode = "0">
{br}
      </BuildableProductRunnable>
   </LaunchAction>
   <ProfileAction
      buildConfiguration = "Release"
      shouldUseLaunchSchemeArgsEnv = "YES"
      savedToolIdentifier = ""
      useCustomWorkingDirectory = "NO"
      debugDocumentVersioning = "YES">
      <BuildableProductRunnable
         runnableDebuggingMode = "0">
{br}
      </BuildableProductRunnable>
   </ProfileAction>
   <AnalyzeAction
      buildConfiguration = "Debug">
   </AnalyzeAction>
   <ArchiveAction
      buildConfiguration = "Release"
      revealArchiveInOrganizer = "YES">
   </ArchiveAction>
</Scheme>
'''
with open(os.path.join(scheme_dir, "Postman.xcscheme"), "w", encoding="utf-8") as fh:
    fh.write(scheme)
print("objects:", len(objs), "swift files:", sum(len(v) for v in swift.values()))
