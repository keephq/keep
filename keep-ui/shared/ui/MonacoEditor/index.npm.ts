"use client";

import dynamic from "next/dynamic";

// this export is used to replace default export in index.ts if KEEP_MONACO_EDITOR_NPM=true
const MonacoEditor = dynamic(
  () => import("./MonacoEditorWithNpm").then((mod) => mod.MonacoEditorWithNpm),
  {
    ssr: false,
  }
);

export { MonacoEditor };
