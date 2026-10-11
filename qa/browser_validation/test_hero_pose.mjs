// Executes the actual viewer's self-contained animation-sampling block in Node.
// This verifies imported geometry pose only; it creates no WebGL context.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import * as THREE from '../../web/node_modules/three/build/three.module.js';
import {GLTFLoader} from '../../web/node_modules/three/examples/jsm/loaders/GLTFLoader.js';
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const source=await fs.readFile('web/viewer.js','utf8');
const start=source.indexOf('const mixer=new THREE.AnimationMixer(loaded.scene);');
const end=source.indexOf('bench.gltfAnimationSample=',start);
assert.ok(start>=0&&end>start,'Viewer animation-sampling block must be present');
const block=source.slice(start,end);
const sample=new Function('THREE','loaded','spec',block+'return {mixer,sampleTimeSeconds};');
const bytes=await fs.readFile('samples/resin_scene.glb');
const specBytes=await fs.readFile('specs/clear_resin_final.json');
const spec=JSON.parse(specBytes);
const loaded=await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),'');
loaded.scene.rotation.x=Math.PI/2;loaded.scene.updateMatrixWorld(true);
const meshes=[];loaded.scene.traverse(o=>{if(o.isMesh)meshes.push(o);});
const liquid=meshes.find(o=>o.name==='Resin_|_closed_fill_volume_and_meniscus');
const stream=meshes.find(o=>o.name==='Resin_|_continuous_art-directed_stream');
assert.ok(liquid&&stream,'Both animated meshes must load');
assert.equal(loaded.animations.length,2,'Frozen MVP has separate liquid and stream clips');
function bounds(o){const v=new THREE.Vector3(),min=new THREE.Vector3(Infinity,Infinity,Infinity),max=new THREE.Vector3(-Infinity,-Infinity,-Infinity);for(let i=0;i<o.geometry.attributes.position.count;i++){o.getVertexPosition(i,v).applyMatrix4(o.matrixWorld);min.min(v);max.max(v);}return {min:min.toArray(),max:max.toArray()};}
function materials(){return JSON.stringify(meshes.map(o=>(Array.isArray(o.material)?o.material:[o.material]).map(m=>m.toJSON())));}
function close(a,b,label,tolerance=2e-6){assert.ok(Math.abs(a-b)<tolerance,`${label}: expected ${b}, observed ${a}`);}
const initial={liquid:bounds(liquid),stream:bounds(stream),weights:liquid.morphTargetInfluences.slice()};
const materialsBefore=materials();
const result=sample(THREE,loaded,spec);
const corrected={liquid:bounds(liquid),stream:bounds(stream),liquidWeights:liquid.morphTargetInfluences.slice(),streamWeights:stream.morphTargetInfluences.slice()};
close(result.sampleTimeSeconds,1.5,'Frozen hero absolute time');
close(corrected.liquid.max[2],spec.liquid.fill_height+spec.liquid.meniscus_height,'Hero liquid top');
close(corrected.stream.min[2],spec.liquid.fill_height-.025,'Hero stream bottom');
close(corrected.stream.max[2],spec.liquid.stream_top,'Hero stream top');
close(corrected.liquid.min[2],spec.cup.base_thickness+.004,'Liquid base stays fixed');
const expectedEndWeight=(spec.animation.hero_frame-1)/(spec.animation.frames-1);
for(const mesh of[liquid,stream]){close(mesh.morphTargetInfluences[0],1-expectedEndWeight,'Hero start weight');close(mesh.morphTargetInfluences[1],expectedEndWeight,'Hero end weight');}
assert.ok(corrected.liquid.max[2]-initial.liquid.max[2]>.3,'Test must distinguish incorrect default pose');
assert.equal(materials(),materialsBefore,'Animation sampling must preserve all imported material JSON');
const cameraChecks=[];
for(const c of loaded.cameras){const name=c.name.replace('Camera_',''),cfg=spec.cameras[name],position=c.getWorldPosition(new THREE.Vector3()),direction=c.getWorldDirection(new THREE.Vector3()),expected=new THREE.Vector3(...cfg.target).sub(new THREE.Vector3(...cfg.position)).normalize();for(let i=0;i<3;i++){close(position.toArray()[i],cfg.position[i],`${name} position[${i}]`);close(direction.toArray()[i],expected.toArray()[i],`${name} direction[${i}]`);}close(c.right-c.left,cfg.ortho_scale,`${name} ortho width`);cameraChecks.push(name);}
// The last frame must clamp at its final pose instead of looping to frame 1.
const finalSpec=structuredClone(spec);finalSpec.animation.hero_frame=spec.animation.frames;
const finalSample=sample(THREE,loaded,finalSpec),finalBounds={liquid:bounds(liquid),stream:bounds(stream)};
close(finalBounds.liquid.max[2],spec.animation.fill_end+spec.liquid.meniscus_height,'Final-frame liquid top');
close(finalBounds.stream.min[2],spec.animation.fill_end-.025,'Final-frame stream bottom');
assert.equal(materials(),materialsBefore,'Final-frame sampling must preserve all imported material JSON');
console.log(JSON.stringify({status:'passed',stage:'Actual viewer sampling block + Node GLTFLoader evaluated geometry; NO browser/WebGL/pixel validation',threeRevision:THREE.REVISION,sourceHashes:{viewer:hash(source),samplingBlock:hash(block),spec:hash(specBytes),glb:hash(bytes)},frame:spec.animation.hero_frame,fps:spec.animation.fps,timeSeconds:result.sampleTimeSeconds,clips:loaded.animations.map(c=>c.name),initial,corrected,materialsUnchanged:true,cameraChecks,finalFrameClamp:{frame:finalSpec.animation.hero_frame,timeSeconds:finalSample.sampleTimeSeconds,bounds:finalBounds},browserValidation:'not_run'},null,2));
