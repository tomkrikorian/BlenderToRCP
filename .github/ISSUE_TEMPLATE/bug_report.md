---
name: Bug report
about: Report a problem with BlenderToRCP export, materials, animation, or baking
title: "[Bug] "
labels: bug
assignees: ""
---

## Summary
<!-- What happened? One sentence. -->

## Environment
- Blender version:
- BlenderToRCP version:
- OS:
- Export format: `.usda` / `.usdc` / `.usdz`
- Workflow: Export / Bake & Export (background)

## Steps to reproduce
1.
2.
3.

## Expected result
<!-- What you expected to happen. -->

## Actual result
<!-- What actually happened (include exact error messages). -->

## Attachments (highly recommended)
Please attach as many of the following as you can:
- The minimal `.blend` file (or a minimal repro file).
- The exported `.usda/.usdc/.usdz`.
- The `*.diagnostics.json` generated next to the exported file (enable "Diagnostics" in the add-on preferences).
- Screenshots of the Blender shader graph and the resulting ShaderGraph in Reality Composer Pro.

If this was a Bake & Export (background) run, also attach:
- `<export_dir>/.blendertorcp_jobs/<job_id>/status.json`
- `<export_dir>/.blendertorcp_jobs/<job_id>/log.txt`

## Notes
<!-- Anything else that might help: which material/mesh name, which node types, whether the file was imported, etc. -->

