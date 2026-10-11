"""Inspect the actual saved Blender scene. Read-only except JSON output."""
import argparse,json,sys,math
from pathlib import Path
import bpy,bmesh
p=argparse.ArgumentParser();p.add_argument('--out',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
sc=bpy.context.scene;original=sc.frame_current; report={'blender_version':bpy.app.version_string,'source':bpy.data.filepath,'objects':{},'frames':{},'limitations':['Does not establish optical appearance, self-intersection freedom, or fluid physical accuracy.']}
for name in ['Cup | closed wall and base','Resin | closed fill volume and meniscus','Resin | continuous art-directed stream']:
 o=bpy.data.objects[name];bm=bmesh.new();bm.from_mesh(o.data)
 report['objects'][name]={'vertices':len(bm.verts),'faces':len(bm.faces),'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'signed_volume':bm.calc_volume(signed=True),'finite_coordinates':all(math.isfinite(c) for v in bm.verts for c in v.co),'morph_targets':len(o.data.shape_keys.key_blocks)-1 if o.data.shape_keys else 0};bm.free()
for frame in [sc.frame_start,18,sc.frame_end]:
 sc.frame_set(frame);dg=bpy.context.evaluated_depsgraph_get(); bounds={}
 for name in ['Resin | closed fill volume and meniscus','Resin | continuous art-directed stream']:
  o=bpy.data.objects[name].evaluated_get(dg);m=o.to_mesh();zs=[v.co.z for v in m.vertices];bounds[name]={'min_z':min(zs),'max_z':max(zs)};o.to_mesh_clear()
 bounds['stream_overlaps_receiving_surface']=bounds['Resin | continuous art-directed stream']['min_z']<bounds['Resin | closed fill volume and meniscus']['max_z']
 report['frames'][str(frame)]=bounds
sc.frame_set(original)
nozzle=bpy.data.objects['Feed nozzle | real hollow steel']
report['nozzle_clearance']={'exit_bore_radius':nozzle.get('exit_bore_radius'),'stream_top_radius':nozzle.get('stream_top_radius')}
if report['nozzle_clearance']['exit_bore_radius'] is not None: report['nozzle_clearance']['pass']=report['nozzle_clearance']['exit_bore_radius']>report['nozzle_clearance']['stream_top_radius']
report['checks_pass']=all(o['nonmanifold_edges']==0 and o['signed_volume']>0 and o['finite_coordinates'] for o in report['objects'].values()) and all(f['stream_overlaps_receiving_surface'] for f in report['frames'].values()) and report['nozzle_clearance'].get('pass',False)
Path(a.out).write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if not report['checks_pass']: sys.exit(2)
