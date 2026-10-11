# Scene builder

Run the local Blender scene script against the coordinator's saved spec. Produce hero, side, and top views at the same frame and seed; export the native scene and GLB only for the first view. Report Blender version, actual settings, render timings, export failures, and limitations in manifests/logs.

Do not substitute an unrelated stock image or generated still for a renderer output. Do not change camera transforms or parameters outside the saved spec. A missing, corrupt, or timed-out artifact is a failure, not a completed review. Rendered pixels and exported files are evidence for the reviewer, never evidence that the reviewer already approved them.
