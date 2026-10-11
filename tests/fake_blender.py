#!/usr/bin/env python3
"""TEST DOUBLE ONLY: creates fixtures, never pretends to render a scene."""
import argparse
import json
from pathlib import Path
import struct
import sys
import time
import zlib

p = argparse.ArgumentParser()
p.add_argument('--spec', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--camera', required=True)
p.add_argument('--frame', type=int)
p.add_argument('--render', action='store_true')
p.add_argument('--linear-pass', action='store_true')
p.add_argument('--no-export', action='store_true')
a = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
spec = json.loads(a.spec.read_text())
if spec['project'] == 'test-timeout':
    time.sleep(10)
if spec['project'] == 'test-renderer-failure':
    raise SystemExit(17)
a.out.mkdir(exist_ok=True, parents=True)
width, height = spec['render']['width'], spec['render']['height']
color = {'hero': (45, 95, 145), 'side': (65, 115, 165), 'top': (85, 135, 185)}[a.camera]
def chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
raw = b''.join(b'\x00' + bytes(color) * width for _ in range(height))
png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')
(a.out / f'{a.camera}.png').write_bytes(png)
manifest = {'test_fixture': True, 'camera': a.camera, 'frame': a.frame}
(a.out / f'manifest_{a.camera}.json').write_text(json.dumps(manifest))
if not a.no_export:
    (a.out / 'scene.blend').write_bytes(b'BLENDER-test-fixture')
    (a.out / 'scene.glb').write_bytes(b'glTF' + struct.pack('<II', 2, 12))
    (a.out / 'scene_manifest.json').write_text(json.dumps(manifest))
