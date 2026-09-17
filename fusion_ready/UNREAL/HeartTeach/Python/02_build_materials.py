# -*- coding: utf-8 -*-
"""Runs INSIDE the Unreal editor.  Builds MPC_HeartClip and M_HeartPart entirely in code.

Why a Custom (HLSL) node instead of a scripted node graph: the shading here is ~25 maths nodes, and every
one of them is a chance to get a pin name wrong from outside the editor.  Two Custom nodes carry all of it,
so the only scripted connections left are single-output nodes (world position, vertex colour, two-sided
sign, collection parameters) whose default output is addressed as "".  The HLSL is plain text, diffable,
and is the real specification of how the cut face looks.

M_HeartPart:
  Blend Mode        Masked           -- the clip plane discards pixels
  Two Sided         true             -- so the inside of the shell is drawn where the plane cuts it
  Tangent Space Normal  false        -- the cut face is flat-shaded with the plane's own normal
"""
import unreal

DEST = "/Game/Heart"
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
ML = unreal.MaterialEditingLibrary


def log(m): unreal.log(f"[HeartTeach] {m}")


# ------------------------------------------------------------------ MPC
def build_collection():
    path = f"{DEST}/MPC_HeartClip"
    mpc = unreal.EditorAssetLibrary.load_asset(path)
    if not mpc:
        mpc = TOOLS.create_asset("MPC_HeartClip", DEST, unreal.MaterialParameterCollection, unreal.MaterialParameterCollectionFactoryNew())
    mpc.set_editor_property("scalar_parameters", [unreal.CollectionScalarParameter(parameter_name="ClipEnabled", default_value=0.0)])
    mpc.set_editor_property("vector_parameters", [
        unreal.CollectionVectorParameter(parameter_name="ClipOrigin", default_value=unreal.LinearColor(0, 0, 0, 0)),
        unreal.CollectionVectorParameter(parameter_name="ClipNormal", default_value=unreal.LinearColor(0, 0, 1, 0)),
    ])
    unreal.EditorAssetLibrary.save_asset(path)
    log("MPC_HeartClip: ClipEnabled, ClipOrigin, ClipNormal")
    return mpc


# ------------------------------------------------------------------ helpers
def ex(mat, cls, x, y):
    return ML.create_material_expression(mat, cls, x, y)


def link(frm, frm_out, to, to_in):
    ML.connect_material_expressions(frm, frm_out, to, to_in)


def custom(mat, x, y, name, code, out_type, inputs):
    """A Custom HLSL node with named inputs, returned together with its input names."""
    n = ex(mat, unreal.MaterialExpressionCustom, x, y)
    n.set_editor_property("description", name)
    n.set_editor_property("code", code)
    n.set_editor_property("output_type", out_type)
    n.set_editor_property("inputs", [unreal.CustomInput(input_name=i) for i in inputs])
    return n


def collection_param(mat, mpc, pname, x, y):
    n = ex(mat, unreal.MaterialExpressionCollectionParameter, x, y)
    n.set_editor_property("collection", mpc)
    n.set_editor_property("parameter_name", pname)
    return n


def vec_param(mat, pname, default, x, y):
    n = ex(mat, unreal.MaterialExpressionVectorParameter, x, y)
    n.set_editor_property("parameter_name", pname)
    n.set_editor_property("default_value", default)
    return n


def scalar_param(mat, pname, default, x, y):
    n = ex(mat, unreal.MaterialExpressionScalarParameter, x, y)
    n.set_editor_property("parameter_name", pname)
    n.set_editor_property("default_value", default)
    return n


# ------------------------------------------------------------------ HLSL
# Keep the pixel if it is on the +ClipNormal side of the plane.  Opacity is dithered rather than
# translucent so that "isolate a part" costs nothing and still sorts correctly against the cut face.
MASK_HLSL = """
float keep = 1.0f;
if (ClipEnabled > 0.5f)
{
    keep = (dot(WorldPos - ClipOrigin, normalize(ClipNormal)) >= 0.0f) ? 1.0f : 0.0f;
}
return keep * (Opacity >= 0.999f ? 1.0f : (Dither < Opacity ? 1.0f : 0.0f));
"""

# Base colour.  Order matters: territory greying happens on the raw colour, the cut-face lift is applied
# last so the section reads as one polished surface whatever is underneath it.
#   0.82 / 0.18 is the same lift used in the matplotlib renders, so screen and figures agree.
SHADE_HLSL = """
float3 c = lerp(Tint, VC, saturate(UseVC));

if (DeadCol.a > 0.5f)
{
    float dA = 1.0f - saturate(length(VC - DeadA) * 12.0f);
    float dB = 1.0f - saturate(length(VC - DeadB) * 12.0f);
    c = lerp(c, DeadCol.rgb, saturate(dA + dB));
}

float back = saturate(-TwoSided);
c = lerp(c, c * 0.82f + 0.18f, back);
c += Highlight * 0.22f;
return c;
"""

# The cut face must not be shaded like the curved wall it belongs to, or it reads as a hollow, not a section.
NORMAL_HLSL = """
float back = saturate(-TwoSided);
return normalize(lerp(VertexNormal, -normalize(ClipNormal), back));
"""


def build_material(mpc):
    path = f"{DEST}/M_HeartPart"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        unreal.EditorAssetLibrary.delete_asset(path)                 # rebuild from scratch: this file is the source of truth
    mat = TOOLS.create_asset("M_HeartPart", DEST, unreal.Material, unreal.MaterialFactoryNew())
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
    mat.set_editor_property("two_sided", True)
    mat.set_editor_property("tangent_space_normal", False)

    # --- sources
    wp     = ex(mat, unreal.MaterialExpressionWorldPosition, -900, -200)
    vc     = ex(mat, unreal.MaterialExpressionVertexColor, -900, 120)
    tsign  = ex(mat, unreal.MaterialExpressionTwoSidedSign, -900, 260)
    vnorm  = ex(mat, unreal.MaterialExpressionVertexNormalWS, -900, 380)
    dither = ex(mat, unreal.MaterialExpressionDitherTemporalAA, -900, 20)

    c_org = collection_param(mat, mpc, "ClipOrigin", -900, -120)
    c_nrm = collection_param(mat, mpc, "ClipNormal", -900, -60)
    c_en  = collection_param(mat, mpc, "ClipEnabled", -900, 0)

    p_tint = vec_param(mat, "Tint", unreal.LinearColor(0.72, 0.28, 0.26, 1.0), -900, 460)
    p_usevc = scalar_param(mat, "UseVertexColour", 0.0, -900, 520)
    p_op    = scalar_param(mat, "Opacity", 1.0, -900, 560)
    p_hi    = scalar_param(mat, "Highlight", 0.0, -900, 600)
    p_dA    = vec_param(mat, "DeadMatchA", unreal.LinearColor(0, 0, 0, 1), -900, 660)
    p_dB    = vec_param(mat, "DeadMatchB", unreal.LinearColor(0, 0, 0, 1), -900, 720)
    p_dC    = vec_param(mat, "DeadColour", unreal.LinearColor(0.35, 0.35, 0.35, 0.0), -900, 780)

    # --- opacity mask
    mask = custom(mat, -400, -100, "HeartClipMask", MASK_HLSL, unreal.CustomMaterialOutputType.CMOT_FLOAT1,
                  ["WorldPos", "ClipOrigin", "ClipNormal", "ClipEnabled", "Opacity", "Dither"])
    for src, pin in ((wp, "WorldPos"), (c_org, "ClipOrigin"), (c_nrm, "ClipNormal"),
                     (c_en, "ClipEnabled"), (p_op, "Opacity"), (dither, "Dither")):
        link(src, "", mask, pin)
    ML.connect_material_property(mask, "", unreal.MaterialProperty.MP_OPACITY_MASK)

    # --- base colour
    shade = custom(mat, -400, 200, "HeartShade", SHADE_HLSL, unreal.CustomMaterialOutputType.CMOT_FLOAT3,
                   ["VC", "Tint", "UseVC", "DeadA", "DeadB", "DeadCol", "Highlight", "TwoSided"])
    for src, pin in ((vc, "VC"), (p_tint, "Tint"), (p_usevc, "UseVC"), (p_dA, "DeadA"),
                     (p_dB, "DeadB"), (p_dC, "DeadCol"), (p_hi, "Highlight"), (tsign, "TwoSided")):
        link(src, "", shade, pin)
    ML.connect_material_property(shade, "", unreal.MaterialProperty.MP_BASE_COLOR)

    # --- normal (flat on the cut face)
    nrm = custom(mat, -400, 520, "HeartNormal", NORMAL_HLSL, unreal.CustomMaterialOutputType.CMOT_FLOAT3,
                 ["VertexNormal", "ClipNormal", "TwoSided"])
    for src, pin in ((vnorm, "VertexNormal"), (c_nrm, "ClipNormal"), (tsign, "TwoSided")):
        link(src, "", nrm, pin)
    ML.connect_material_property(nrm, "", unreal.MaterialProperty.MP_NORMAL)

    rough = ex(mat, unreal.MaterialExpressionConstant, -400, 700); rough.set_editor_property("r", 0.55)
    ML.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    spec = ex(mat, unreal.MaterialExpressionConstant, -400, 760); spec.set_editor_property("r", 0.25)
    ML.connect_material_property(spec, "", unreal.MaterialProperty.MP_SPECULAR)

    ML.recompile_material(mat)
    unreal.EditorAssetLibrary.save_asset(path)
    log("M_HeartPart built (masked, two sided, world-space normal)")
    return mat


def main():
    mpc = build_collection()
    build_material(mpc)
    log("done. next: 03_build_level.py")


main()
