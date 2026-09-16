# -*- coding: utf-8 -*-
"""Headless visual verification of the frame-A print. Renders the fused parts from three
angles plus a clipped view showing the myocardium wall around the blood pool."""
import bpy, os, math
from mathutils import Vector
HERE=os.path.dirname(os.path.abspath(__file__)); OUT=os.path.join(HERE,"BLENDER_OUT")
PARTS=[("LV_bloodpool.stl",(0.80,0.20,0.20,1),1.0),
       ("mitral_valve.stl",(0.15,0.55,0.95,1),1.0),
       ("aortic_valve.stl",(0.95,0.80,0.10,1),1.0),
       ("LV_myocardium_frameA.stl",(0.55,0.55,0.60,1),0.28)]
bpy.ops.wm.read_factory_settings(use_empty=True)
sc=bpy.context.scene
sc.unit_settings.system='METRIC'; sc.unit_settings.length_unit='MILLIMETERS'
sc.unit_settings.scale_length=0.001
for eng in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE', 'BLENDER_WORKBENCH'):
    try:
        sc.render.engine = eng; break
    except TypeError:
        continue
print("render engine:", sc.render.engine)
sc.render.film_transparent=False
sc.render.resolution_x=1400; sc.render.resolution_y=1000
objs=[]
for fn,col,alpha in PARTS:
    p=os.path.join(OUT,fn)
    if not os.path.exists(p): print("skip",fn); continue
    before=set(bpy.data.objects)
    bpy.ops.wm.stl_import(filepath=p, global_scale=1.0)
    o=(set(bpy.data.objects)-before).pop(); o.name=fn[:-4]
    m=bpy.data.materials.new(fn); m.use_nodes=True
    b=m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value=col
    b.inputs["Roughness"].default_value=0.45
    if alpha<1.0:
        b.inputs["Alpha"].default_value=alpha; m.blend_method='BLEND'
    o.data.materials.append(m); objs.append(o)
# lights + camera
for v,e in [((1,1,1),3.5e6),((-1,-0.6,0.7),1.8e6),((0.2,-1,-0.5),1.2e6)]:
    l=bpy.data.lights.new("L",'SUN'); l.energy=3.0
    ob=bpy.data.objects.new("L",l); sc.collection.objects.link(ob)
    ob.rotation_euler=Vector(v).to_track_quat('-Z','Y').to_euler()
cam_d=bpy.data.cameras.new("C"); cam=bpy.data.objects.new("C",cam_d)
sc.collection.objects.link(cam); sc.camera=cam
w=bpy.data.worlds.new("W"); w.use_nodes=True
w.node_tree.nodes["Background"].inputs[0].default_value=(0.05,0.05,0.06,1); sc.world=w
views={"front":(0,-260,40),"left":(-260,0,40),"apex":(150,-150,-180)}
for name,pos in views.items():
    cam.location=Vector(pos)
    cam.rotation_euler=(Vector((0,0,0))-Vector(pos)).to_track_quat('-Z','Y').to_euler()
    sc.render.filepath=os.path.join(OUT,f"render_{name}.png")
    bpy.ops.render.render(write_still=True)
    print("rendered",name)
