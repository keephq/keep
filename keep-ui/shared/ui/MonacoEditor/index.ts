"use client";

import dynamic from "next/dynamic";

const MonacoEditor = dynamic(
  () => import("./MonacoEditorNPM").then((mod) => mod.MonacoEditorNPM),
  {
    ssr: false,
  }
);

export { MonacoEditor };
