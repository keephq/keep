const esbuild = require("esbuild");
const path = require("path");
const fs = require("fs");

// Create output directory if it doesn't exist
const outdir = path.join(__dirname, "./monaco-editor");
if (!fs.existsSync(outdir)) {
  fs.mkdirSync(outdir, { recursive: true });
}

// Build the main Monaco bundle
esbuild
  .build({
    entryPoints: ["./monaco-entry.js"],
    bundle: true,
    minify: true,
    format: "iife",
    outfile: path.join(outdir, "loader.js"),
    loader: {
      ".ttf": "file",
      ".css": "text",
    },
  })
  .catch(() => process.exit(1));

// Build the worker bundles
const workerEntryPoints = [
  ["monaco-editor/esm/vs/editor/editor.worker.js", "editor.worker.js"],
  ["monaco-editor/esm/vs/language/json/json.worker", "json.worker.js"],
  ["monaco-editor/esm/vs/language/css/css.worker", "css.worker.js"],
  ["monaco-editor/esm/vs/language/html/html.worker", "html.worker.js"],
  ["monaco-editor/esm/vs/language/typescript/ts.worker", "ts.worker.js"],
];

workerEntryPoints.forEach(([entry, output]) => {
  esbuild
    .build({
      entryPoints: [entry],
      bundle: true,
      minify: true,
      format: "iife",
      outfile: path.join(outdir, output),
      define: {
        "process.env.NODE_ENV": '"production"',
        global: "self",
      },
    })
    .catch(() => process.exit(1));
});
