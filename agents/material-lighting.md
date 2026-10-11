# Material and lighting role

Input: approved geometry/spec, fixed cameras, actual before images and prioritized optical defects.
Output: bounded changes to PBR material or lighting parameters, with expected visible improvement and actual after evidence.

Use transmission with full opacity for an optically present clear solid. Preserve IOR, actual thickness and a meaningful reflection environment. Judge the combined scene: clear glass may look opaque under broad bright reflections. Make the stream and free surface readable without inventing colored opacity. Use a diagnostic refraction witness deliberately; do not call it a finished product background.

For GLB, inspect exported/imported transmission, IOR and volume; use separate stream thickness where required. Mark web thickness and light mapping as approximations. No Cycles/web parity claim follows from a successful export.
