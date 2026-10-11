import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import * as THREE from '../../web/node_modules/three/build/three.module.js';
import {GLTFLoader} from '../../web/node_modules/three/examples/jsm/loaders/GLTFLoader.js';
const file='samples/resin_scene.glb',b=await fs.readFile(file),spec=JSON.parse(await fs.readFile('specs/clear_resin_final.json'));
const imported=await new GLTFLoader().parseAsync(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),'');
imported.scene.rotation.x=Math.PI/2;imported.scene.updateMatrixWorld(true);
const info={stage:'Static GLTFLoader geometry/material audit only; no WebGL pixels',glb:file,glbSHA256:crypto.createHash('sha256').update(b).digest('hex'),threeRevision:THREE.REVISION,specSHA256:crypto.createHash('sha256').update(await fs.readFile('specs/clear_resin_final.json')).digest('hex'),cameraInputs:spec.cameras,frames:{hero:spec.animation.hero_frame,fps:spec.animation.fps,fillHeight:spec.liquid.fill_height,fillStart:spec.animation.fill_start,fillEnd:spec.animation.fill_end},objects:[],animations:imported.animations.map(a=>({name:a.name,duration:a.duration,tracks:a.tracks.map(t=>({name:t.name,times:Array.from(t.times),values:Array.from(t.values)}))}))};
function bounds(o){const v=new THREE.Vector3(),mi=new THREE.Vector3(Infinity,Infinity,Infinity),ma=new THREE.Vector3(-Infinity,-Infinity,-Infinity);for(let i=0;i<o.geometry.attributes.position.count;i++){o.getVertexPosition(i,v).applyMatrix4(o.matrixWorld);mi.min(v);ma.max(v);}return {min:mi.toArray(),max:ma.toArray()};}
imported.scene.traverse(o=>{if(o.isMesh)info.objects.push({name:o.name,morphDictionary:o.morphTargetDictionary,morphWeights:o.morphTargetInfluences?.slice(),evaluatedBounds:bounds(o),materials:(Array.isArray(o.material)?o.material:[o.material]).map(m=>({name:m.name,type:m.type,side:m.side,transmission:m.transmission??0,ior:m.ior??null,thickness:m.thickness??null,attenuationDistance:Number.isFinite(m.attenuationDistance)?m.attenuationDistance:null,attenuationColor:m.attenuationColor?.toArray(),color:m.color.toArray(),roughness:m.roughness,metalness:m.metalness}))});});
// Inspect the hero-frame correction separately; preserve untouched import evidence above.
const mixer=new THREE.AnimationMixer(imported.scene);
for(const clip of imported.animations){const action=mixer.clipAction(clip);action.setLoop(THREE.LoopOnce,1);action.clampWhenFinished=true;action.play();}
const sampleTime=spec.animation.hero_frame/spec.animation.fps;
mixer.setTime(sampleTime);imported.scene.updateMatrixWorld(true);
info.heroFrameCorrection={sampleTimeSeconds:sampleTime,objects:[]};
imported.scene.traverse(o=>{if(o.isMesh&&o.morphTargetInfluences)info.heroFrameCorrection.objects.push({name:o.name,morphWeights:o.morphTargetInfluences.slice(),evaluatedBounds:bounds(o)});});
info.importedCameras=imported.cameras.map(c=>({name:c.name,position:c.getWorldPosition(new THREE.Vector3()).toArray(),direction:c.getWorldDirection(new THREE.Vector3()).toArray(),left:c.left,right:c.right,top:c.top,bottom:c.bottom,near:c.near,far:c.far}));
info.comparisonStatus='Static evidence only. A/C browser render, renderer provenance, pixel capture and frame timing remain not run.';
console.log(JSON.stringify(info,null,2));
