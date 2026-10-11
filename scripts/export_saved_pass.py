"""Re-render the saved scene unchanged and save raw PNG plus linear PFM/EXR."""
import bpy,sys,argparse,struct,time,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--out',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
s=bpy.context.scene;s.render.image_settings.file_format='PNG';s.render.filepath=str(out/'hero.png');t=time.monotonic();bpy.ops.render.render(write_still=True)
s.render.image_settings.file_format='OPEN_EXR';s.render.image_settings.color_depth='32';bpy.data.images['Render Result'].save_render(str(out/'hero_linear.exr'),scene=s)
im=bpy.data.images.load(str(out/'hero_linear.exr'));width,height=im.size;px=list(im.pixels[:]);rgb=[px[i+c] for i in range(0,len(px),4) for c in range(3)]
with open(out/'hero_linear.pfm','wb') as f:f.write(('PF\n%d %d\n-1.0\n'%(width,height)).encode());f.write(struct.pack('<%sf'%len(rgb),*rgb))
(out/'replay_manifest.json').write_text(json.dumps({'source_blend':bpy.data.filepath,'purpose':'unchanged baseline replay to obtain linear HDR pass for matched OIDN treatment','samples':s.cycles.samples,'frame':s.frame_current,'camera':s.camera.name,'elapsed_seconds':time.monotonic()-t},indent=2))
