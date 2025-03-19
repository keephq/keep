// This file is used to replace the default export for the MonacoEditor component
// when using Turbopack in development mode
// export { MonacoEditorCDN as MonacoEditor } from "./MonacoEditorCDN";

"use client";

import dynamic from "next/dynamic";

const MonacoEditor = dynamic(
  () => import("./MonacoEditorCDN").then((mod) => mod.MonacoEditorCDN),
  {
    ssr: false,
  }
);

export { MonacoEditor };
