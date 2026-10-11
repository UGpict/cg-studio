#!/usr/bin/env python3
"""Optional official Intel OIDN color-only HDR denoise. Keeps all raw inputs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time


def locate_oidn(explicit=None):
    candidate = explicit or os.environ.get('OIDN_DENOISE') or shutil.which('oidnDenoise')
    if not candidate:
        local = Path('/workspace/shared/tools/oidn-2.5.1.x86_64.linux/bin/oidnDenoise')
        if local.is_file():
            candidate = str(local)
    if not candidate or not Path(candidate).is_file():
        raise FileNotFoundError('Set OIDN_DENOISE or --oidn to the official oidnDenoise binary. Nothing is downloaded automatically.')
    return str(Path(candidate).resolve())


def run_oidn(source, output, binary, timeout=180):
    if Path(source).resolve() == Path(output).resolve():
        raise ValueError('Refusing to overwrite the raw PFM')
    command = [binary, '--hdr', str(source), '--device', 'cpu', '--threads', '2',
               '--affinity', '0', '-o', str(output)]
    result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=timeout)
    if not Path(output).is_file():
        raise RuntimeError('OIDN did not produce an output PFM')
    return command, result.stdout + result.stderr


def image_difference(before, after):
    from PIL import Image, ImageChops, ImageStat
    a, b = Image.open(before).convert('RGB'), Image.open(after).convert('RGB')
    if a.size != b.size:
        raise ValueError('Comparison image dimensions differ')
    difference = ImageChops.difference(a, b)
    stats = ImageStat.Stat(difference)
    return {'width': a.width, 'height': a.height,
            'mean_absolute_difference_8bit': sum(stats.mean) / 3,
            'maximum_channel_difference_8bit': max(x[1] for x in difference.getextrema())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, help='Scene-linear RGB PFM')
    parser.add_argument('--blend', required=True, help='Scene used for the matching AgX display transform')
    parser.add_argument('--output', help='Denoised PFM, default input_color_only_oidn.pfm')
    parser.add_argument('--oidn')
    parser.add_argument('--blender', default='blender')
    parser.add_argument('--timeout', type=float, default=180)
    args = parser.parse_args()
    source = Path(args.input).resolve()
    output = Path(args.output).resolve() if args.output else source.with_name(source.stem + '_color_only_oidn.pfm')
    output.parent.mkdir(parents=True, exist_ok=True)
    raw_display = output.with_name(output.stem + '_raw_display.png')
    png = output.with_suffix('.png')
    raw_png = source.with_name(source.stem.removesuffix('_linear') + '.png')
    if png == raw_png or raw_display == raw_png:
        raise ValueError('Refusing to overwrite the original raw PNG')
    original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    start = time.monotonic()
    command, log = run_oidn(source, output, locate_oidn(args.oidn), args.timeout)
    script = Path(__file__).with_name('pfm_to_png.py')
    subprocess.run([args.blender, '-b', str(Path(args.blend).resolve()), '-t', '2', '-P', str(script), '--',
                    '--input', str(output), '--output', str(png), '--compare-input', str(source),
                    '--compare-output', str(raw_display)], check=True, timeout=args.timeout)
    report = {'method': 'Intel Open Image Denoise RT, HDR, color-only',
              'auxiliary_passes': [], 'temporal_denoising': False,
              'input': str(source), 'input_sha256': original_hash,
              'raw_preserved': original_hash == hashlib.sha256(source.read_bytes()).hexdigest(),
              'denoised_pfm': str(output), 'denoised_png': str(png), 'raw_display_png': str(raw_display),
              'same_display_transform_for_both': True, 'command': command, 'oidn_log': log,
              'elapsed_seconds': time.monotonic() - start,
              'display_difference': image_difference(raw_display, png),
              'limitations': ['No albedo or normal auxiliary passes; fine transparent details may soften.',
                             'A visual noise-reduction pass is not validation of geometry or physical accuracy.',
                             'Single-frame filtering can cause temporal flicker.']}
    report_path = output.with_suffix('.json')
    report_path.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
