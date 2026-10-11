#!/usr/bin/env python3
"""Budgeted short preview from an existing animated scene, with honest QA.
One Blender process renders all frames. No fluid simulation is performed.
"""
import argparse
import json
import math
import os
import signal
from pathlib import Path
import subprocess
import sys
import threading
import time


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--blend', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--width', type=int, default=384)
    parser.add_argument('--height', type=int, default=384)
    parser.add_argument('--samples', type=int, default=16)
    parser.add_argument('--frames', type=int, default=36)
    parser.add_argument('--fps', type=int, default=12)
    parser.add_argument('--budget-seconds', type=float, default=400)
    parser.add_argument('--frame-timeout', type=float, default=180)
    parser.add_argument('--blender', default='blender')
    parser.add_argument('--oidn', help='Enable optional color-only OIDN with this official binary')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    args = parser.parse_args(argv)
    if min(args.width, args.height, args.samples, args.frames, args.fps) < 1 or args.width % 2 or args.height % 2:
        parser.error('Dimensions must be positive and even; counts must be positive')
    if not math.isfinite(args.budget_seconds) or not 0 < args.budget_seconds <= 400:
        parser.error('Total budget must be finite, positive, and at most 400 seconds')
    if not math.isfinite(args.frame_timeout) or not 0 < args.frame_timeout <= 180:
        parser.error('Per-frame timeout must be finite, positive, and at most 180 seconds')
    return args


def worker(args):
    import bpy
    sys.path.insert(0, str(Path(__file__).parent))
    from pfm_to_png import render_result_to_pfm, pfm_to_png
    from denoise import run_oidn, locate_oidn
    out = Path(args.out).resolve()
    raw = out / 'raw'
    raw.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    if scene.frame_start > 1 or scene.frame_end < args.frames:
        raise ValueError('Requested frames fall outside the saved scene animation')
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = False
    scene.render.resolution_x, scene.render.resolution_y = args.width, args.height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_depth = '8'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.fps = args.fps
    binary = locate_oidn(args.oidn) if args.oidn else None
    if binary:
        (out / 'linear').mkdir(exist_ok=True)
        (out / 'color_only_oidn').mkdir(exist_ok=True)
        (out / 'raw_display').mkdir(exist_ok=True)
    report = {'frames': [], 'animation_mode': 'art-directed fixed-topology shape-key fill and continuous stream',
              'fluid_simulation': False, 'temporal_denoising': False,
              'denoising': 'color-only OIDN HDR' if binary else 'none',
              'display_transform': scene.view_settings.view_transform,
              'look': scene.view_settings.look, 'exposure': scene.view_settings.exposure,
              'width': args.width, 'height': args.height, 'samples': args.samples, 'fps': args.fps}
    def frame_deadline():
        # The outer launcher owns a new POSIX session. Kill its complete group
        # so an in-flight OIDN process cannot survive a stuck frame.
        if os.name == 'posix' and os.getpgrp() == os.getpid():
            os.killpg(os.getpgrp(), signal.SIGKILL)
        os._exit(124)

    for number in range(1, args.frames + 1):
        timer = threading.Timer(args.frame_timeout, frame_deadline)
        timer.daemon = True
        timer.start()
        start = time.monotonic()
        scene.frame_set(number)
        scene.render.filepath = str(raw / f'{number:04d}.png')
        bpy.ops.render.render(write_still=True)
        if binary:
            pfm = out / 'linear' / f'{number:04d}.pfm'
            denoised = out / 'linear' / f'{number:04d}_color_only_oidn.pfm'
            render_result_to_pfm(scene, pfm)
            run_oidn(pfm, denoised, binary, timeout=args.frame_timeout)
            pfm_to_png(pfm, out / 'raw_display' / f'{number:04d}.png', scene)
            pfm_to_png(denoised, out / 'color_only_oidn' / f'{number:04d}.png', scene)
        timer.cancel()
        report['frames'].append({'frame': number, 'seconds': time.monotonic() - start})
        (out / 'render_report.json').write_text(json.dumps(report, indent=2))
        print(f'MOTION_FRAME_COMPLETE {number}', flush=True)
    print('MOTION_RENDER_COMPLETE', flush=True)


def run(args):
    from PIL import Image, ImageDraw
    sys.path.insert(0, str(Path(__file__).parent))
    from denoise import image_difference
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from cgstudio.budget import run_renderer
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    # A fresh output directory is required: stale frames must never pass validation.
    if any((out / folder).exists() for folder in ('raw', 'color_only_oidn')):
        raise FileExistsError('Use a fresh output directory; existing raw frames are preserved')
    started = time.monotonic()
    command = [args.blender, '-b', str(Path(args.blend).resolve()), '-t', '2', '-P', str(Path(__file__).resolve()), '--',
               '--worker', '--blend', str(Path(args.blend).resolve()), '--out', str(out),
               '--width', str(args.width), '--height', str(args.height), '--samples', str(args.samples),
               '--frames', str(args.frames), '--fps', str(args.fps), '--frame-timeout', str(args.frame_timeout)]
    if args.oidn:
        command += ['--oidn', args.oidn]
    def remaining():
        seconds = args.budget_seconds - (time.monotonic() - started)
        if seconds <= 0:
            raise TimeoutError('Total motion render and validation budget exhausted')
        return seconds
    try:
        result = run_renderer(command, out / 'blender.log', remaining())
        if result['returncode'] != 0:
            raise subprocess.CalledProcessError(result['returncode'], command)
        selected = out / ('color_only_oidn' if args.oidn else 'raw')
        frames = sorted(selected.glob('*.png'))
        if len(frames) != args.frames:
            raise ValueError(f'Expected {args.frames} PNGs, found {len(frames)}')
        for frame in frames:
            with Image.open(frame) as im:
                im.load()
                if im.size != (args.width, args.height):
                    raise ValueError(f'Unexpected dimensions in {frame}')
        video = out / 'preview.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-framerate', str(args.fps), '-start_number', '1',
                        '-i', str(selected / '%04d.png'), '-frames:v', str(args.frames), '-c:v', 'libx264',
                        '-threads', '2', '-crf', '18', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(video)],
                       check=True, timeout=remaining())
        probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                        '-show_entries', 'stream=codec_name,width,height,nb_read_frames,r_frame_rate,duration',
                        '-of', 'json', str(video)], timeout=remaining()))['streams'][0]
        subprocess.run(['ffmpeg', '-v', 'error', '-i', str(video), '-f', 'null', '-'],
                       check=True, timeout=remaining())
        if int(probe['nb_read_frames']) != args.frames or abs(float(probe['duration']) - args.frames / args.fps) > .02:
            raise ValueError('Decoded frame count or duration does not match the requested preview')
        rate_num, rate_den = map(int, probe['r_frame_rate'].split('/'))
        if (int(probe['width']), int(probe['height'])) != (args.width, args.height) or rate_num / rate_den != args.fps:
            raise ValueError('Encoded dimensions or frame rate do not match the requested preview')
        indices = sorted(set([0, (args.frames - 1) // 2, args.frames - 1]))
        sheet = Image.new('RGB', (args.width * len(indices), args.height + 30), '#15202b')
        draw = ImageDraw.Draw(sheet)
        for column, index in enumerate(indices):
            with Image.open(frames[index]) as frame:
                sheet.paste(frame.convert('RGB'), (column * args.width, 30))
            draw.text((column * args.width + 8, 9), f'Frame {index + 1} / {args.frames}', fill='white')
        sheet.save(out / 'contact_sheet.png')
        report = json.loads((out / 'render_report.json').read_text())
        report.update({'validation': 'passed', 'video_decode': 'passed', 'png_decode_count': len(frames),
                       'video': str(video), 'ffprobe': probe, 'contact_sheet': str(out / 'contact_sheet.png'),
                       'first_last_display_difference': image_difference(frames[0], frames[-1]),
                       'elapsed_seconds': time.monotonic() - started,
                       'limitations': ['Shape-key demonstration, not a fluid simulation.',
                                       'Low-sample preview is not a final-quality render.',
                                       'Color-only OIDN, when enabled, can soften details or flicker over time.',
                                       'Successful decode and frame differences do not establish visual or physical quality.']})
        (out / 'validation.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
    except Exception as error:
        (out / 'validation.json').write_text(json.dumps({'validation': 'failed', 'error': str(error),
            'elapsed_seconds': time.monotonic() - started, 'partial_raw_frames_preserved': True}, indent=2))
        raise


if __name__ == '__main__':
    args = arguments()
    worker(args) if args.worker else run(args)
