# Humation runtime

Bundled from the read-only Deva checkout's @humation/core 1.0.3 and
@humation/assets-humation-1 1.0.3 (MIT licenses alongside).
The wrapper uses the repository's existing SVG composition adapter and the
original components/humation.tsx shape paths, spec parser and selection validation.

Rebuild from the ai_upper repository root:

    node scripts/parity/build_humation.mjs /path/to/deva

The build uses Deva's existing esbuild installation. Application runtime uses
QJSEngine, with a flatMap compatibility shim; no Node or Deva path is needed
by the application. No dependency pins are changed.

Generated SVGs resolve CSS color variables before QtSvg rendering. This is a
static avatar renderer; animated busy morphing is not used in extension settings.
