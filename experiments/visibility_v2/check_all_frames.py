import bpy,bmesh,json,sys,math
from pathlib import Path
report={'scene':bpy.data.filepath,'frames':{},'fluid_simulation':False,'input_geometry':'shape keys','evaluated_geometry':'live Boolean union with potentially changing topology'}
sc=bpy.context.scene
for frame in range(1,37):
 sc.frame_set(frame);dg=bpy.context.evaluated_depsgraph_get();r={}
 for name in ['Cup | closed wall and base','Resin | closed fill volume and meniscus']:
  obj=bpy.data.objects[name].evaluated_get(dg);me=obj.to_mesh();bm=bmesh.new();bm.from_mesh(me)
  seen=set();components=0
  for v in bm.verts:
   if v in seen:continue
   components+=1;queue=[v];seen.add(v)
   while queue:
    vv=queue.pop()
    for e in vv.link_edges:
     other=e.other_vert(vv)
     if other not in seen:seen.add(other);queue.append(other)
  r[name]={'vertices':len(bm.verts),'faces':len(bm.faces),'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'signed_volume':bm.calc_volume(signed=True),'connected_components':components,'bounds_z':[min(v.co.z for v in bm.verts),max(v.co.z for v in bm.verts)]}
  bm.free();obj.to_mesh_clear()
 report['frames'][str(frame)]=r
report['checks_pass']=all(o['nonmanifold_edges']==0 and o['signed_volume']>0 and o['connected_components']==1 for r in report['frames'].values() for o in r.values())
volumes=[r['Resin | closed fill volume and meniscus']['signed_volume'] for r in report['frames'].values()]
report['volume_strictly_increases']=all(b>a for a,b in zip(volumes,volumes[1:]))
report['checks_pass']=report['checks_pass'] and report['volume_strictly_increases']
Path(sys.argv[sys.argv.index('--')+1]).write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if not report['checks_pass']:sys.exit(2)
