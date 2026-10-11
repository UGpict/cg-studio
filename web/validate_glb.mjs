import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {GLTFLoader} from './node_modules/three/examples/jsm/loaders/GLTFLoader.js';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'), file=process.argv[2]||path.join(root,'samples/resin_scene.glb');
const buf=await fs.readFile(file);const bytes=buf.buffer.slice(buf.byteOffset,buf.byteOffset+buf.byteLength);const loaded=await new GLTFLoader().parseAsync(bytes,'');
const objects=[];loaded.scene.traverse(o=>{if(o.isMesh)objects.push({name:o.name,vertices:o.geometry.attributes.position.count,triangles:(o.geometry.index?.count||o.geometry.attributes.position.count)/3,materials:(Array.isArray(o.material)?o.material:[o.material]).map(m=>({name:m.name,type:m.type,transmission:m.transmission??0,ior:m.ior??null,thickness:m.thickness??null,roughness:m.roughness,metalness:m.metalness}))});});
const result={validatedAt:new Date().toISOString(),path:file,stage:'GLTFLoader parse only, no WebGL rendering',status:'passed',asset:loaded.asset,extensions:loaded.parser.json.extensionsUsed||[],objects};
await fs.mkdir(path.join(root,'web/results'),{recursive:true});await fs.writeFile(path.join(root,'web/results/glb_validation.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
