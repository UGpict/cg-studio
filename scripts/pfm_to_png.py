"""Read scene-linear RGB PFM and write PNG through the scene's display transform.

Run inside Blender: blender -b scene.blend -P scripts/pfm_to_png.py --
  --input image.pfm --output image.png
PFM and Blender pixels both run bottom-to-top. No flip or sRGB pre-conversion.
"""
import argparse
from pathlib import Path
import sys


def read_pfm(path):
    import numpy as np
    with open(path, 'rb') as handle:
        def line():
            value = handle.readline()
            while value.startswith(b'#') or not value.strip():
                if not value:
                    raise ValueError('Truncated PFM header')
                value = handle.readline()
            return value.strip()
        if line() != b'PF':
            raise ValueError('Expected a three-channel RGB PFM')
        width, height = map(int, line().split())
        scale = float(line())
        if width <= 0 or height <= 0 or not scale:
            raise ValueError('Invalid PFM dimensions or scale')
        data = np.frombuffer(handle.read(), dtype='<f4' if scale < 0 else '>f4')
        if data.size != width * height * 3:
            raise ValueError('PFM pixel count does not match header')
        data = data.reshape(height, width, 3).astype(np.float32) * abs(scale)
        if not np.isfinite(data).all():
            raise ValueError('PFM contains NaN or infinite pixels')
    return data


def write_pfm(path, rgb):
    import numpy as np
    height, width, channels = rgb.shape
    if channels != 3 or not np.isfinite(rgb).all():
        raise ValueError('Expected finite RGB pixels')
    with open(path, 'wb') as handle:
        handle.write(f'PF\n{width} {height}\n-1.0\n'.encode())
        handle.write(rgb.astype('<f4').tobytes())


def render_result_to_pfm(scene, path):
    """Save an EXR alongside PFM; use the EXR to obtain linear float pixels."""
    import bpy
    import numpy as np
    path = Path(path)
    settings = scene.render.image_settings
    previous = settings.file_format, settings.color_depth, settings.color_mode
    settings.file_format = 'OPEN_EXR'
    settings.color_depth = '32'
    settings.color_mode = 'RGBA'
    exr = path.with_suffix('.exr')
    bpy.data.images['Render Result'].save_render(str(exr), scene=scene)
    image = bpy.data.images.load(str(exr), check_existing=False)
    width, height = image.size
    pixels = np.empty(width * height * 4, dtype=np.float32)
    image.pixels.foreach_get(pixels)
    write_pfm(path, pixels.reshape(height, width, 4)[:, :, :3])
    bpy.data.images.remove(image)
    settings.file_format, settings.color_depth, settings.color_mode = previous


def pfm_to_png(source, destination, scene):
    import bpy
    import numpy as np
    rgb = read_pfm(source)
    height, width, _ = rgb.shape
    rgba = np.ones((height, width, 4), dtype=np.float32)
    rgba[:, :, :3] = rgb
    image = bpy.data.images.new('Linear PFM display conversion', width=width,
                                height=height, alpha=False, float_buffer=True)
    # PFM values are already scene-linear. Assigning an sRGB input color space
    # would decode them a second time and make the comparison invalid.
    image.colorspace_settings.name = 'Linear Rec.709'
    image.pixels.foreach_set(rgba.ravel())
    image.update()
    settings = scene.render.image_settings
    previous = settings.file_format, settings.color_depth, settings.color_mode
    settings.file_format = 'PNG'
    settings.color_depth = '8'
    settings.color_mode = 'RGB'
    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    image.save_render(str(destination), scene=scene)
    bpy.data.images.remove(image)
    settings.file_format, settings.color_depth, settings.color_mode = previous


def main():
    import bpy
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--compare-input')
    parser.add_argument('--compare-output')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    if bool(args.compare_input) != bool(args.compare_output):
        parser.error('Supply both comparison paths')
    scene = bpy.context.scene
    pfm_to_png(args.input, args.output, scene)
    if args.compare_input:
        pfm_to_png(args.compare_input, args.compare_output, scene)
    print('PFM_DISPLAY_COMPLETE', scene.view_settings.view_transform,
          scene.view_settings.look, scene.view_settings.exposure)


if __name__ == '__main__':
    main()
