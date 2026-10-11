import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {RoomEnvironment} from 'three/addons/environments/RoomEnvironment.js';
import {RectAreaLightUniformsLib} from 'three/addons/lights/RectAreaLightUniformsLib.js';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
const query=new URLSearchParams(location.search), mode=query.get('mode')||'A';
if(query.get('capture'))document.body.classList.add('capture');
window.__BENCHMARK__={status:'loading',mode,errors:[],threeRevision:THREE.REVISION};const bench=window.__BENCHMARK__;
try{
const response=await fetch(query.get('spec')||'../specs/clear_resin_final.json');if(!response.ok)throw Error('Scene spec could not be loaded');const spec=await response.json();bench.spec=spec;
const width=Number(query.get('width'))||spec.render.width,height=Number(query.get('height'))||spec.render.height;bench.width=width;bench.height=height;
const renderer=new THREE.WebGLRenderer({antialias:true,preserveDrawingBuffer:true,alpha:false,powerPreference:'high-performance'});
renderer.setSize(width,height);renderer.setPixelRatio(1);renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.AgXToneMapping;renderer.toneMappingExposure=2**spec.lighting.exposure;renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;document.body.appendChild(renderer.domElement);
const gl=renderer.getContext(),debug=gl.getExtension('WEBGL_debug_renderer_info');
bench.webgl={version:gl.getParameter(gl.VERSION),vendor:debug?gl.getParameter(debug.UNMASKED_VENDOR_WEBGL):gl.getParameter(gl.VENDOR),renderer:debug?gl.getParameter(debug.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER)};
bench.softwareRenderer=/swiftshader|llvmpipe|software/i.test(bench.webgl.renderer);bench.hardwareStatus=bench.softwareRenderer?'software rasterizer observed':'not independently verified';
const scene=new THREE.Scene();scene.background=new THREE.Color(.72,.8,.88);const pmrem=new THREE.PMREMGenerator(renderer);scene.environment=pmrem.fromScene(new RoomEnvironment(),.035).texture;scene.environmentIntensity=spec.lighting.world_strength;
const group=new THREE.Group();scene.add(group);
function material(name,color,roughness,metalness=0,transmission=0,ior=1.5,thickness=0){const m=new THREE.MeshPhysicalMaterial({color:new THREE.Color(...color),roughness,metalness,transmission,ior,thickness});m.name=name;return m;}
function mesh(name,geometry,mat,position=[0,0,0]){const m=new THREE.Mesh(geometry,mat);m.name=name;m.position.fromArray(position);m.castShadow=true;m.receiveShadow=true;group.add(m);return m;}
function lathe(name,profile,mat,segments=128){const geo=new THREE.LatheGeometry(profile.map(([r,z])=>new THREE.Vector2(r,z)),segments);geo.rotateX(Math.PI/2);return mesh(name,geo,mat);}
function box(name,loc,size,mat){return mesh(name,new THREE.BoxGeometry(...size),mat,loc);}
if(mode==='A'){
const c=spec.cup,l=spec.liquid,frame=spec.animation.hero_frame,r=c.outer_radius,h=c.height,w=c.wall_thickness,b=c.base_thickness;
const glass=material('Vessel | polished borosilicate',[.97,.99,1],c.roughness,0,1,c.ior,w);
const resin=material('Resin | clear optical medium',[1,1,1],l.roughness,0,l.transmission,l.ior,1.6);resin.attenuationColor=new THREE.Color(...l.absorption_color);resin.attenuationDistance=l.absorption_density>0?1/l.absorption_density:Infinity;
const steel=material('Metal witness | brushed steel',[.48,.54,.6],.18,1),floorMat=material('Studio | blue-grey satin',[.19,.245,.29].map(v=>v*(spec.stage?.ground_value??1)),.27),dark=material('Refraction witness | dark blue',[.025,.07,.11],.3),pale=material('Refraction witness | white',[.65,.72,.76].map(v=>v*(spec.stage?.card_value??1)),.32);
lathe('Cup | closed wall and base',[[0,.02],[.86*r,.02],[.92*r,.035],[.954*r,.085],[r,h-.035],[r-.007,h-.008],[r-.028,h+.005],[r-w+.015,h-.003],[r-w,h-.035],[.9*r-w,b+.025],[.86*r-w,b],[0,b],[0,.02]],glass);
const z=l.fill_height,radius=.9*r-w+(z-b)/(h-b)*(.1*r)-.004,profile=[[0,b+.004],[.86*r-w-.004,b+.004],[.9*r-w-.004,b+.026],[radius,z+l.meniscus_height]];
for(let i=1;i<=20;i++){const rr=radius*(1-i/20),men=l.meniscus_height*Math.exp(-(((radius-rr)/.045)**2)),ripple=.007*Math.sin(rr*24+frame*.5)*Math.exp(-rr*2);profile.push([rr,z+men+ripple]);}profile.push([0,b+.004]);lathe('Resin | closed fill volume and meniscus',profile,resin);
const seg=96,n=24,positions=[],indices=[],bottom=z-.025,top=l.stream_top;
for(let j=0;j<=seg;j++){const t=j/seg,zz=bottom+(top-bottom)*t,cx=-.21+.025*Math.sin(t*8+frame*.21)*(1-t),cy=.03+.014*Math.cos(t*9+frame*.13)*(1-t),rad=l.stream_radius*(.8+.22*t)+.046*Math.exp(-t*22);for(let i=0;i<n;i++){const a=i/n*2*Math.PI;positions.push(cx+rad*Math.cos(a),cy+rad*Math.sin(a),zz);}}
for(let j=0;j<seg;j++)for(let i=0;i<n;i++){const k=(i+1)%n,a=j*n,bb=(j+1)*n;indices.push(a+i,a+k,bb+k,a+i,bb+k,bb+i);}for(let i=1;i<n-1;i++){indices.push(0,i+1,i,seg*n,seg*n+i,seg*n+i+1);}const stream=new THREE.BufferGeometry();stream.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));stream.setIndex(indices);stream.computeVertexNormals();const streamMat=resin.clone();streamMat.name='Resin stream | web thickness approximation';streamMat.thickness=2*l.stream_radius;mesh('Resin | continuous art-directed stream',stream,streamMat);
const bore=l.stream_radius*1.02+.006;const nozzle=lathe('Feed nozzle | real hollow steel',[[bore,top-.01],[bore+.04,top-.01],[bore+.058,top+.06],[bore+.058,top+.34],[bore+.018,top+.34],[bore+.018,top+.055],[bore,top-.01]],steel,96);nozzle.position.set(-.21,.03,0);
const cyl=new THREE.CylinderGeometry(.33,.33,.62,96);cyl.rotateX(Math.PI/2);mesh('Metal witness | cylinder',cyl,steel,[1.55,.28,.33]);
mesh('Studio ground',new THREE.PlaneGeometry(200,200),floorMat);
const cw=spec.stage?.card_width??2.1;box('Refraction card',[0,1.23,.82],[cw,.045,1.45],pale);for(const x of[-cw*.55/2.1,0,cw*.55/2.1])box('Refraction marker',[x,1.195,.82],[Math.min(.065,cw*.12),.025,1.4],dark);
bench.source='procedural Three.js implementation of common spec';bench.geometryDifferences=['A uses un-beveled witness cylinder and witness cards; C contains Blender modifier output.','Lathe ring phase / triangulation / normals may differ between engines.'];
}else if(mode==='C'){
const url=query.get('glb')||'../samples/resin_scene.glb',loaded=await new GLTFLoader().loadAsync(url);loaded.scene.rotation.x=Math.PI/2;
// Exported tracks retain Blender's absolute frame/fps timestamps (frame 18 is 1.5s at 12fps).
// The GLB's default [1,0] morph weights are the initial fill pose, not the hero pose.
const mixer=new THREE.AnimationMixer(loaded.scene);
for(const clip of loaded.animations){const action=mixer.clipAction(clip);action.setLoop(THREE.LoopOnce,1);action.clampWhenFinished=true;action.play();}
const sampleTimeSeconds=spec.animation.hero_frame/spec.animation.fps;mixer.setTime(sampleTimeSeconds);loaded.scene.updateMatrixWorld(true);
bench.gltfAnimationSample={frame:spec.animation.hero_frame,fps:spec.animation.fps,timeSeconds:sampleTimeSeconds,clips:loaded.animations.map(clip=>clip.name),timeline:'Blender absolute frame / fps',morphWeights:[]};
loaded.scene.traverse(o=>{if(o.isMesh&&o.morphTargetInfluences)bench.gltfAnimationSample.morphWeights.push({object:o.name,weights:o.morphTargetInfluences.slice()});});
group.add(loaded.scene);loaded.scene.traverse(o=>{if(o.isMesh){o.castShadow=true;o.receiveShadow=true;}});bench.source=url;bench.gltfAsset=loaded.asset;bench.gltfExtensions=loaded.parser.json.extensionsUsed||[];
}else throw new Error(`Unknown mode ${mode}`);
RectAreaLightUniformsLib.init();const l=spec.lighting;
for(const [name,pos,color,energy,w,h]of [['Key softbox',[-3,-4,6],[1,.91,.81],l.key_energy,3,4],['Cool fill',[4,-1,3],[.72,.85,1],l.fill_energy,2,3],['Rim strip',[1,3,5],[1,1,1],l.rim_energy,2,4]]){const light=new THREE.RectAreaLight(new THREE.Color(...color),energy/(w*h*Math.PI),w,h);light.name=name;light.position.fromArray(pos);light.up.set(0,0,1);light.lookAt(0,0,1);scene.add(light);}
if(l.stream_energy>0){const w=l.stream_size??.16,h=3.6,light=new THREE.RectAreaLight(0xffffff,l.stream_energy/(w*h*Math.PI),w,h);light.name='Stream reflection strip';light.position.set(-1.4,-3,2.7);light.up.set(0,0,1);light.lookAt(-.21,0,1.7);scene.add(light);}
// Three.js RectAreaLight shadows are unsupported. This explicitly logged shared shadow approximation is used in A/C only.
const shadowLight=new THREE.DirectionalLight(0xffffff,.5);shadowLight.position.set(-3,-4,6);shadowLight.castShadow=true;shadowLight.shadow.mapSize.set(1024,1024);Object.assign(shadowLight.shadow.camera,{left:-4,right:4,top:4,bottom:-4});scene.add(shadowLight);
const cameraName=query.get('camera')||'hero',camCfg=spec.cameras[cameraName];if(!camCfg)throw Error(`Missing camera ${cameraName}`);const scale=camCfg.ortho_scale,aspect=width/height;const camera=new THREE.OrthographicCamera(-scale*aspect/2,scale*aspect/2,scale/2,-scale/2,.01,200);camera.up.set(0,0,1);camera.position.fromArray(camCfg.position);camera.lookAt(new THREE.Vector3(...camCfg.target));bench.camera={name:cameraName,...camCfg};
const controls=new OrbitControls(camera,renderer.domElement);controls.target.fromArray(camCfg.target);controls.update();bench.materials=[];let vertices=0,triangles=0;
group.traverse(o=>{if(o.isMesh){vertices+=o.geometry.attributes.position.count;triangles+=(o.geometry.index?.count||o.geometry.attributes.position.count)/3;for(const m of Array.isArray(o.material)?o.material:[o.material])bench.materials.push({object:o.name,name:m.name,type:m.type,transmission:m.transmission??0,ior:m.ior??null,thickness:m.thickness??null,attenuationDistance:Number.isFinite(m.attenuationDistance)?m.attenuationDistance:null,roughness:m.roughness,metalness:m.metalness});}});
bench.geometry={vertices,triangles};bench.limitations=['Rasterized transmission is an approximation; no path-traced caustics.','Frame times use synchronous WebGL finish and are this environment only.','Art-directed fixed-topology stream, not simulated fluid.','Three.js PMREM room environment and directional shadow approximation do not match the Cycles lighting exactly.','Three.js AgX and Blender AgX are not claimed colorimetric equivalents.','Blender volumetric scattering does not transfer through GLB.'];
const compileStart=performance.now();await renderer.compileAsync(scene,camera);renderer.render(scene,camera);gl.finish();bench.compileAndFirstFrameMs=performance.now()-compileStart;
window.__renderBenchmark=async(frames=12)=>{const values=[];for(let i=0;i<3;i++){renderer.render(scene,camera);gl.finish();}for(let i=0;i<frames;i++){const t=performance.now();renderer.render(scene,camera);gl.finish();values.push(performance.now()-t);await new Promise(r=>setTimeout(r,0));}values.sort((a,b)=>a-b);bench.timing={frames,meanMs:values.reduce((a,b)=>a+b,0)/frames,medianMs:values[Math.floor(frames/2)],p95Ms:values[Math.min(frames-1,Math.floor(frames*.95))],samplesMs:values,measurement:'Wall clock renderer.render + gl.finish; CPU/driver/GPU completion, not GPU timer query'};bench.renderInfo={calls:renderer.info.render.calls,triangles:renderer.info.render.triangles,geometries:renderer.info.memory.geometries,textures:renderer.info.memory.textures};return bench;};
renderer.render(scene,camera);gl.finish();bench.status='ready';document.querySelector('#status').textContent=`${mode} · ${bench.source}\n${bench.webgl.renderer}\n${bench.geometry.triangles.toLocaleString()} object triangles`;controls.addEventListener('change',()=>renderer.render(scene,camera));
}catch(err){bench.status='failed';bench.errors.push(err.stack||String(err));document.querySelector('#status').textContent=bench.errors.join('\n');console.error(err);}
