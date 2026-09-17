# -*- coding: utf-8 -*-
"""Runs INSIDE the Unreal editor.  Builds the level: heart actor wired to the DataTables, lighting, and the
input bindings, then writes the four-chamber plane from the pipeline manifest into the actor.

The plane is the one the printed halves are cut on, so the slider's zero position and the physical model
agree -- a student can hold the print and match it to the screen.
"""
import json, os
import unreal

PACK = os.environ.get("HEART_PACK", r"C:\work\Cardiac\fusion_ready\UNREAL\1009")
DEST = "/Game/Heart"
LEVEL = f"{DEST}/L_Heart"
UE_PER_METRE = 100.0                       # the glTF is in metres; Unreal is in centimetres


def log(m): unreal.log(f"[HeartTeach] {m}")


def load(p):
    a = unreal.EditorAssetLibrary.load_asset(p)
    if not a: log(f"MISSING asset {p}")
    return a


def gltf_to_unreal(v):
    """glTF (right-handed, Y-up, m) -> Unreal (left-handed, Z-up, cm), matching what the importer does to the
    meshes themselves: X stays, Y and Z swap, and the new Y is negated."""
    x, y, z = v
    return unreal.Vector(x * UE_PER_METRE, -z * UE_PER_METRE, y * UE_PER_METRE)


def build_level(man):
    unreal.EditorLevelLibrary.new_level(LEVEL)
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

    cls = unreal.load_class(None, "/Script/HeartTeach.HeartAssembly")
    heart = sub.spawn_actor_from_class(cls, unreal.Vector(0, 0, 0))
    heart.set_actor_label("Heart")
    heart.set_editor_property("PartsTable", load(f"{DEST}/DT_HeartParts"))
    heart.set_editor_property("TerritoryTable", load(f"{DEST}/DT_HeartTerritories"))
    heart.set_editor_property("TerritoryColourTable", load(f"{DEST}/DT_HeartTerritoryColours"))
    heart.set_editor_property("PartMaterial", load(f"{DEST}/M_HeartPart"))
    heart.set_editor_property("ClipCollection", load(f"{DEST}/MPC_HeartClip"))
    heart.set_editor_property("TerritoryMesh", load(f"{DEST}/Assemblies/perfusion_territories"))

    plane = man["four_chamber_plane"]
    o, n = gltf_to_unreal(plane["origin_m"]), gltf_to_unreal(plane["normal"])
    heart.set_editor_property("DefaultClipOrigin", o)
    heart.set_editor_property("DefaultClipNormal", n)
    log(f"four-chamber plane -> Unreal: origin {o} cm, normal {n} (slider zero = the printed halves' plane)")

    sky = sub.spawn_actor_from_class(unreal.SkyLight.static_class(), unreal.Vector(0, 0, 200))
    sun = sub.spawn_actor_from_class(unreal.DirectionalLight.static_class(), unreal.Vector(0, 0, 300))
    sun.set_actor_rotation(unreal.Rotator(-45, 30, 0), False)
    sub.spawn_actor_from_class(unreal.SkyAtmosphere.static_class(), unreal.Vector(0, 0, 0))

    pawn_cls = unreal.load_class(None, "/Script/HeartTeach.HeartPawn")
    pawn = sub.spawn_actor_from_class(pawn_cls, unreal.Vector(0, 0, 0))
    pawn.set_actor_label("HeartPawn")
    pawn.set_editor_property("Heart", heart)
    pawn.set_editor_property("auto_possess_player", unreal.AutoReceiveInput.PLAYER0)

    unreal.EditorLevelLibrary.save_current_level()
    log(f"level saved: {LEVEL}")


INPUT_INI = """
[/Script/Engine.InputSettings]
-ActionMappings=(ActionName="Orbit")
-ActionMappings=(ActionName="Pan")
-ActionMappings=(ActionName="Pick")
-AxisMappings=(AxisName="Zoom")
+ActionMappings=(ActionName="Orbit",bShift=False,bCtrl=False,bAlt=False,bCmd=False,Key=RightMouseButton)
+ActionMappings=(ActionName="Pan",bShift=False,bCtrl=False,bAlt=False,bCmd=False,Key=MiddleMouseButton)
+ActionMappings=(ActionName="Pick",bShift=False,bCtrl=False,bAlt=False,bCmd=False,Key=LeftMouseButton)
+AxisMappings=(AxisName="Zoom",Key=MouseWheelAxis,Scale=1.0)
"""


def write_input_ini():
    """Legacy action/axis mappings so no Enhanced Input .uasset is needed -- the project stays text-only."""
    proj = unreal.Paths.project_dir()
    p = os.path.join(proj, "Config", "DefaultInput.ini")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    existing = open(p, encoding="utf-8").read() if os.path.exists(p) else ""
    if "ActionName=\"Orbit\"" not in existing:
        open(p, "a", encoding="utf-8").write(INPUT_INI)
        log(f"input bindings appended to {p} (restart the editor to pick them up)")
    else:
        log("input bindings already present")


def main():
    man = json.load(open(os.path.join(PACK, "unreal_manifest.json"), encoding="utf-8"))
    write_input_ini()
    build_level(man)
    log("done. Play the level: right-drag orbits, wheel zooms, middle-drag pans, left click identifies.")
    log(man["licence"])


main()
