# Third-party components

The procedural scene, scripts and QA orchestration in this repository were authored for this project. No company-film, PCB, Adafruit, stock scene, paid model, private chat transcript or production asset has been copied into it.

Runtime dependencies are not vendored:

- Blender: official application; GPL family license, https://www.blender.org/about/license/
- Three.js 0.180.0: MIT, https://github.com/mrdoob/three.js/blob/r180/LICENSE
- playwright-core 1.55.1: Apache-2.0, https://github.com/microsoft/playwright/blob/v1.55.1/LICENSE
- Intel Open Image Denoise 2.5.1 (optional): Apache-2.0, official release https://github.com/RenderKit/oidn/releases/tag/v2.5.1
- Pillow (optional metrics/contact sheets): HPND license, https://python-pillow.github.io/
- FFmpeg (optional MP4 encoding): license depends on the installed build; https://ffmpeg.org/legal.html

The optional OIDN Linux archive was obtained from the official RenderKit release and checksum-verified in this environment. It is outside the repository and is not automatically installed. No downloaded third-party add-on or GitHub project code is executed by the base pipeline.
