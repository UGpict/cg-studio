"""Deterministic resin-pour scene. Run inside Blender 4.3+; no add-ons required."""
import argparse, json, math, os, sys, time
from pathlib import Path
import bpy
from mathutils import Vector


def argv():
    p = argparse.ArgumentParser()
    p.add_argument('--spec', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--camera', choices=['hero', 'side', 'top'], default='hero')
    p.add_argument('--frame', type=int, default=18)
    p.add_argument('--render', action='store_true')
    p.add_argument('--linear-pass', action='store_true')
    p.add_argument('--no-export', action='store_true')
    return p.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])


def material(name, color, roughness=.2, metallic=0., transmission=0., ior=1.5):
    m=bpy.data.materials.new(name); m.use_nodes=True
    n=m.node_tree.nodes.get('Principled BSDF')
    n.inputs['Base Color'].default_value=(*color,1)
    n.inputs['Roughness'].default_value=roughness
    n.inputs['Metallic'].default_value=metallic
    n.inputs['Transmission Weight'].default_value=transmission
    n.inputs['IOR'].default_value=ior
    m.diffuse_color=(*color,1)
    return m


def smooth(obj):
    for p in obj.data.polygons: p.use_smooth=True


def mesh(name, vertices, faces, mat):
    m=bpy.data.meshes.new(name); m.from_pydata(vertices, [], faces); m.update()
    o=bpy.data.objects.new(name,m); bpy.context.collection.objects.link(o)
    if mat: m.materials.append(mat)
    smooth(o); return o


def lathe(name, profile, mat, segments=128):
    vertices=[(r*math.cos(2*math.pi*i/segments), r*math.sin(2*math.pi*i/segments),z) for r,z in profile for i in range(segments)]
    faces=[]
    for j in range(len(profile)-1):
        for i in range(segments):
            k=(i+1)%segments; a=j*segments; b=(j+1)*segments
            faces.append((a+i,a+k,b+k,b+i))
    o=mesh(name,vertices,faces,mat)
    # Weld poles, recalculate normals: real closed volumes, not double-sided sheets.
    bpy.context.view_layer.objects.active=o; o.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.00001); bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT'); o.select_set(False)
    # Collapsed center-pole quads can leave one zero-face axis edge; remove it.
    import bmesh
    bm=bmesh.new(); bm.from_mesh(o.data)
    loose=[e for e in bm.edges if not e.link_faces]
    if loose: bmesh.ops.delete(bm,geom=loose,context='EDGES')
    bm.to_mesh(o.data); bm.free(); o.data.update()
    return o


def cube(name, loc, scale, mat, bevel=.03):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc); o=bpy.context.object; o.name=name
    o.dimensions=scale; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    o.data.materials.append(mat)
    if bevel:
        mod=o.modifiers.new('Machined edge radii','BEVEL'); mod.width=bevel; mod.segments=3
        o.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
    return o


def area(name, loc, target, energy, size, color=(1,1,1), size_y=None):
    d=bpy.data.lights.new(name,'AREA'); d.energy=energy; d.shape='RECTANGLE'
    d.size=size; d.size_y=size_y or size; d.color=color
    o=bpy.data.objects.new(name,d); bpy.context.collection.objects.link(o); o.location=loc
    o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler(); return o


def export_thickness(mat,thickness):
    group=bpy.data.node_groups.get('glTF Material Output') or bpy.data.node_groups.new('glTF Material Output','ShaderNodeTree')
    if not group.interface.items_tree: group.interface.new_socket(name='Thickness',in_out='INPUT',socket_type='NodeSocketFloat')
    g=mat.node_tree.nodes.new('ShaderNodeGroup'); g.node_tree=group; g.inputs['Thickness'].default_value=thickness


def animate_fill(liquid,stream,s,base,height,radius):
    # Fixed-topology two-key morphs: liquid surface rises and stream shortens continuously.
    first=s['animation']['fill_start']; last=s['animation']['fill_end']; frames=s['animation']['frames']
    for obj in (liquid,stream):
        obj.shape_key_add(name='Basis')
        for name,target in [('Fill start',first),('Fill end',last)]:
            key=obj.shape_key_add(name=name); delta=target-height
            for v in key.data:
                if obj==liquid:
                    if v.co.z>base+.035:
                        rr=math.hypot(v.co.x,v.co.y)
                        if rr>1e-8:
                            change=.1*s['cup']['outer_radius']/(s['cup']['height']-.035-(base+.025))*delta*(rr/radius)
                            v.co.x*=1+change/rr; v.co.y*=1+change/rr
                        v.co.z+=delta
                else:
                    t=(v.co.z-(height-.025))/(s['liquid']['stream_top']-(height-.025))
                    v.co.z+=delta*(1-t)
            key.value=1.0 if name=='Fill start' else 0.0; key.keyframe_insert('value',frame=1)
            key.value=0.0 if name=='Fill start' else 1.0; key.keyframe_insert('value',frame=frames)
        action=obj.data.shape_keys.animation_data.action
        for curve in action.fcurves:
            for point in curve.keyframe_points: point.interpolation='LINEAR'


def add_volume(mat,spec):
    nt=mat.node_tree; out=nt.nodes.get('Material Output')
    absorption=nt.nodes.new('ShaderNodeVolumeAbsorption'); absorption.inputs['Color'].default_value=(*spec['absorption_color'],1)
    absorption.inputs['Density'].default_value=spec['absorption_density']
    if spec['cloudiness']>0:
        scatter=nt.nodes.new('ShaderNodeVolumeScatter'); scatter.inputs['Density'].default_value=spec['cloudiness']
        scatter.inputs['Anisotropy'].default_value=.1
        add=nt.nodes.new('ShaderNodeAddShader'); nt.links.new(absorption.outputs[0],add.inputs[0]); nt.links.new(scatter.outputs[0],add.inputs[1]); nt.links.new(add.outputs[0],out.inputs['Volume'])
    else: nt.links.new(absorption.outputs[0],out.inputs['Volume'])
    # Exporter-recognized thickness hook. Volume scattering is intentionally not claimed as glTF parity.
    group=bpy.data.node_groups.get('glTF Material Output') or bpy.data.node_groups.new('glTF Material Output','ShaderNodeTree')
    if not group.interface.items_tree: group.interface.new_socket(name='Thickness',in_out='INPUT',socket_type='NodeSocketFloat')
    g=nt.nodes.new('ShaderNodeGroup'); g.node_tree=group; g.inputs['Thickness'].default_value=1.6


def make_scene(s,frame):
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
    sc=bpy.context.scene; sc.render.engine='CYCLES'; sc.cycles.device='CPU'
    sc.cycles.samples=s['render']['samples']; sc.cycles.seed=s['render']['seed']; sc.cycles.use_denoising=s['render']['denoise']
    sc.cycles.max_bounces=16; sc.cycles.transmission_bounces=12; sc.cycles.transparent_max_bounces=12
    sc.cycles.glossy_bounces=8; sc.cycles.diffuse_bounces=4
    sc.cycles.sample_clamp_indirect=4
    sc.render.resolution_x=s['render']['width']; sc.render.resolution_y=s['render']['height']; sc.render.resolution_percentage=100
    sc.render.image_settings.file_format='PNG'; sc.render.film_transparent=s['render']['transparent']
    sc.view_settings.view_transform='AgX'; sc.view_settings.exposure=s['lighting']['exposure']
    sc.world.use_nodes=True; sc.world.node_tree.nodes['Background'].inputs[0].default_value=(.72,.8,.88,1)
    sc.world.node_tree.nodes['Background'].inputs[1].default_value=s['lighting']['world_strength']
    sc.render.fps=s['animation']['fps']; sc.frame_start=1; sc.frame_end=s['animation']['frames']
    glass=material('Vessel | polished borosilicate',(.97,.99,1),s['cup']['roughness'],transmission=1,ior=s['cup']['ior'])
    export_thickness(glass,s['cup']['wall_thickness'])
    resin=material('Resin | clear optical medium',(1,1,1),s['liquid']['roughness'],transmission=s['liquid']['transmission'],ior=s['liquid']['ior']); add_volume(resin,s['liquid'])
    # Explicit three-medium boundary model for Cycles. The submerged inner glass
    # boundary carries the glass/resin relative IOR; liquid side faces do not add
    # another artificial resin/air boundary. Air-facing free surface keeps IOR 1.49.
    contact=bpy.data.materials.new('Interface | submerged glass to resin relative IOR'); contact.use_nodes=True
    nt=contact.node_tree; nt.nodes.clear()
    output=nt.nodes.new('ShaderNodeOutputMaterial'); bsdf=nt.nodes.new('ShaderNodeBsdfGlass')
    bsdf.inputs['Color'].default_value=(1,1,1,1)
    bsdf.inputs['Roughness'].default_value=s['liquid']['roughness']
    bsdf.inputs['IOR'].default_value=s['cup']['ior']/s['liquid']['ior']
    nt.links.new(bsdf.outputs[0],output.inputs['Surface'])
    boundary=resin.copy(); boundary.name='Resin | absorption boundary with no duplicate surface refraction'
    nt=boundary.node_tree; transparent=nt.nodes.new('ShaderNodeBsdfTransparent')
    nt.links.new(transparent.outputs[0],nt.nodes.get('Material Output').inputs['Surface'])
    steel=material('Metal witness | brushed steel',(.48,.54,.6),.18,metallic=1)
    stage=s.get('stage', {})
    ground_value=stage.get('ground_value',1.0)
    floor=material('Studio | blue-grey satin',tuple(c*ground_value for c in (.19,.245,.29)),.27)
    dark=material('Refraction witness | dark blue',(.025,.07,.11),.3)
    stage=s.get('stage', {})
    card_value=stage.get('card_value',1.0)
    pale=material('Refraction witness | card',tuple(c*card_value for c in (.65,.72,.76)),.32)
    r=s['cup']['outer_radius']; h=s['cup']['height']; w=s['cup']['wall_thickness']; b=s['cup']['base_thickness']
    wet_z=s['liquid']['fill_height']+s['liquid']['meniscus_height']
    wet_r=.9*r-w+(wet_z-(b+.025))/(h-.035-(b+.025))*(.1*r)
    outer_r=lambda zz: .954*r+(r-.954*r)*(zz-.085)/(h-.035-.085)
    inner_r=lambda zz: .9*r-w+(zz-(b+.025))/(h-.035-(b+.025))*(.1*r)
    profile=[(0,.02),(.86*r,.02),(.92*r,.035),(.954*r,.085),(outer_r(.14),.14),(outer_r(h-.09),h-.09),(r,h-.035),(r-.007,h-.008),(r-.028,h+.005),(r-w+.015,h-.003),(r-w,h-.035),(inner_r(h-.075),h-.075),(wet_r,wet_z),(inner_r(b+.065),b+.065),(.9*r-w,b+.025),(.86*r-w,b),(0,b),(0,.02)]
    cup=lathe('Cup | closed wall and base',profile,glass)
    cup.data.materials.append(contact)
    for polygon in cup.data.polygons:
        center=polygon.center
        # Inner normals point into the cavity; bottom inner face points upward.
        radial_dot=polygon.normal.x*center.x+polygon.normal.y*center.y
        if center.z<=wet_z+1e-5 and ((radial_dot<-.1 and center.z>b+.001) or (polygon.normal.z>.5 and center.z>=b-.001)):
            polygon.material_index=1
    # The material partition moves with the wet line, without changing the taper.
    cup.shape_key_add(name='Basis')
    for name,target in [('Fill start',s['animation']['fill_start']),('Fill end',s['animation']['fill_end'])]:
        key=cup.shape_key_add(name=name)
        for v in key.data:
            if abs(v.co.z-wet_z)<1e-5:
                target_z=target+s['liquid']['meniscus_height']
                target_r=.9*r-w+(target_z-(b+.025))/(h-.035-(b+.025))*(.1*r)
                v.co.x*=target_r/wet_r;v.co.y*=target_r/wet_r;v.co.z=target_z
        key.value=1.0 if name=='Fill start' else 0.0;key.keyframe_insert('value',frame=1)
        key.value=0.0 if name=='Fill start' else 1.0;key.keyframe_insert('value',frame=s['animation']['frames'])
    for curve in cup.data.shape_keys.animation_data.action.fcurves:
        for point in curve.keyframe_points:point.interpolation='LINEAR'
    cup['physical_wall_thickness']=w; cup['physical_base_thickness']=b
    z=s['liquid']['fill_height']; radius=.9*r-w+(z-(b+.025))/(h-.035-(b+.025))*(.1*r)+.0015
    liquid_profile=[(0,b-.0015),(.86*r-w+.0015,b-.0015),(.9*r-w+.0015,b+.0235),(radius+.001,z+s['liquid']['meniscus_height'])]
    for i in range(1,21):
        rr=radius*(1-i/20); men=s['liquid']['meniscus_height']*math.exp(-((radius-rr)/.045)**2)
        ripple=.007*math.sin(rr*24+frame*.5)*math.exp(-rr*2)
        liquid_profile.append((rr,z+men+ripple))
    liquid_profile += [(0,b-.0015)]
    liquid=lathe('Resin | closed fill volume and meniscus',liquid_profile,resin)
    liquid.data.materials.append(boundary)
    for polygon in liquid.data.polygons:
        if polygon.normal.z<.5: polygon.material_index=1
    # A mild art-directed helical variation, continuous at the receiving surface. No fluid-solver claim.
    seg=96; n=24; vertices=[]; faces=[]; top=s['liquid']['stream_top']; bottom=z-.025
    for j in range(seg+1):
        t=j/seg; zz=bottom+(top-bottom)*t
        cx=-.21+.009*math.sin(t*5+frame*.13)*(1-t); cy=.03+.006*math.cos(t*6+frame*.11)*(1-t)
        rad=s['liquid']['stream_radius']*(.72+.30*t)+.036*math.exp(-t*32)
        for i in range(n):
            a=i/n*2*math.pi; vertices.append((cx+rad*math.cos(a),cy+rad*math.sin(a),zz))
    for j in range(seg):
        for i in range(n):
            k=(i+1)%n; a=j*n; bb=(j+1)*n; faces.append((a+i,a+k,bb+k,bb+i))
    faces.append(tuple(reversed(range(n)))); faces.append(tuple(seg*n+i for i in range(n)))
    stream_mat=resin.copy(); stream_mat.name='Resin stream | web thickness approximation'
    for node in stream_mat.node_tree.nodes:
        if node.type=='GROUP' and node.node_tree.name=='glTF Material Output': node.inputs['Thickness'].default_value=2*s['liquid']['stream_radius']
    stream=mesh('Resin | continuous art-directed stream',vertices,faces,stream_mat)
    animate_fill(liquid,stream,s,b,z,radius)
    # Evaluated union removes the stream cap and overlapping free-surface boundary.
    # Input shapes are procedural; this is not a fluid simulation. The evaluated
    # topology is permitted to change, so native shape-key GLB parity is not claimed.
    union=liquid.modifiers.new('Continuous resin volume | live union','BOOLEAN')
    union.operation='UNION'; union.solver='EXACT'; union.object=stream
    stream.hide_render=True

    # Visible feed nozzle gives the stream a physical source; exact alignment is deliberate.
    bore=s['liquid']['stream_radius']*1.02+.006
    nozzle=lathe('Feed nozzle | real hollow steel',[(bore,top-.01),(bore+.04,top-.01),(bore+.058,top+.06),(bore+.058,top+.34),(bore+.018,top+.34),(bore+.018,top+.055),(bore,top-.01)],steel,96); nozzle.location=(-.21,.03,0)
    feed=lathe('Feed tube | extends outside frame',[(bore+.02,top+.32),(bore+.046,top+.32),(bore+.046,8),(bore+.02,8),(bore+.02,top+.32)],steel,96); feed.location=(-.21,.03,0)
    nozzle['exit_bore_radius']=bore; nozzle['stream_top_radius']=s['liquid']['stream_radius']*1.02
    bpy.ops.mesh.primitive_cylinder_add(vertices=96,radius=.33,depth=.62,location=(1.55,.28,.33)); witness=bpy.context.object; witness.name='Metal witness | cylinder'
    witness.data.materials.append(steel); smooth(witness)
    bevel=witness.modifiers.new('Edge roll','BEVEL'); bevel.width=.055; bevel.segments=4; witness.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
    bpy.ops.mesh.primitive_plane_add(size=200); ground=bpy.context.object; ground.name='Studio ground'; ground.data.materials.append(floor)
    # Product-style studio: narrow, truly vertical reflection sources cover full pour.
    # The prior freestanding diagnostic card is removed for an unobstructed clear volume.
    l=s['lighting']
    area('Key softbox',(-3,-4,6),(0,0,1),l['key_energy'],2.5,(1,.97,.92),3)
    area('Cool fill',(4,-1,4),(0,0,1),l['fill_energy'],2,(.86,.92,1),3)
    area('Left vertical reflection strip',(-3,-2,3.8),(-.21,.03,3.8),l['stream_energy'],l['stream_size'],(1,1,1),7.0)
    area('Right vertical reflection strip',(3,2.5,3.8),(-.21,.03,3.8),l['rim_energy'],.5,(.92,.97,1),7.0)
    for name,c in s['cameras'].items():
        d=bpy.data.cameras.new(name); d.type='ORTHO'; d.ortho_scale=c['ortho_scale']; o=bpy.data.objects.new('Camera_'+name,d); bpy.context.collection.objects.link(o)
        o.location=c['position']; o.rotation_euler=(Vector(c['target'])-o.location).to_track_quat('-Z','Y').to_euler()
    sc.frame_set(frame)
    return sc


def main():
    a=argv(); out=Path(a.out).resolve(); out.mkdir(parents=True,exist_ok=True); s=json.loads(Path(a.spec).read_text()); start=time.monotonic()
    sc=make_scene(s,a.frame); sc.camera=bpy.data.objects['Camera_'+a.camera]
    sc.render.filepath=str(out/(a.camera+'.png'))
    import hashlib
    manifest={'builder_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'spec_file_sha256':hashlib.sha256(Path(a.spec).read_bytes()).hexdigest(),'blender_version':bpy.app.version_string,'engine':'CYCLES','device':'CPU','denoise':sc.cycles.use_denoising,'samples':sc.cycles.samples,'seed':sc.cycles.seed,'camera':a.camera,'frame':a.frame,'animation_mode':s['animation']['mode'],'fluid_simulation':False,'spec':s,'objects':[{'name':o.name,'type':o.type} for o in sc.objects], 'limitations':['Art-directed fixed-topology pour; not a fluid simulation','No denoising by default on this CPU build','GLB optics differ from Cycles; volumetric scattering does not transfer']}
    if not a.no_export:
        bpy.ops.wm.save_as_mainfile(filepath=str(out/'scene.blend'))
        manifest['glb_export']='not_run'
        manifest['glb_limit']='Cycles relative-IOR interfaces and live Boolean evaluated animation are not equivalent to the frozen MVP glTF material/morph route.'
    manifest['animation_mode']='shape-key driven inputs with live Boolean-unified resin volume; not a fluid simulation'
    manifest['limitations'].append('Evaluated Boolean topology may change during animation; no fixed-topology GLB equivalence claim.')
    (out/('manifest_'+a.camera+'.json')).write_text(json.dumps(manifest,indent=2))
    if not a.no_export or not (out/'scene_manifest.json').exists(): (out/'scene_manifest.json').write_text(json.dumps(manifest,indent=2))
    if a.render:
        t=time.monotonic(); bpy.ops.render.render(write_still=True); manifest['render_seconds']=time.monotonic()-t
        if a.linear_pass:
            sc.render.image_settings.file_format='OPEN_EXR'; sc.render.image_settings.color_depth='32'
            bpy.data.images['Render Result'].save_render(str(out/(a.camera+'_linear.exr')),scene=sc)
            linear=bpy.data.images.load(str(out/(a.camera+'_linear.exr')),check_existing=False)
            import struct
            pixels=list(linear.pixels[:]); width,height=linear.size
            with open(out/(a.camera+'_linear.pfm'),'wb') as f:
                f.write(('PF\n%d %d\n-1.0\n'%(width,height)).encode())
                rgb=[pixels[i+c] for i in range(0,len(pixels),4) for c in range(3)]
                f.write(struct.pack('<%sf'%len(rgb),*rgb))
            manifest['linear_color_pass']=str(out/(a.camera+'_linear.pfm'))
            manifest['auxiliary_passes']='not yet exported; external OIDN color-only is explicitly labeled'
            sc.render.image_settings.file_format='PNG'
    manifest['elapsed_seconds']=time.monotonic()-start
    (out/('manifest_'+a.camera+'.json')).write_text(json.dumps(manifest,indent=2))
    if not a.no_export or not (out/'scene_manifest.json').exists(): (out/'scene_manifest.json').write_text(json.dumps(manifest,indent=2)); print('CG_STUDIO_RESULT '+json.dumps({'out':str(out),'camera':a.camera,'elapsed_seconds':manifest['elapsed_seconds']}))

if __name__=='__main__': main()
