"use client";
import dynamic from "next/dynamic";

export const MonacoYAMLEditor = dynamic(
  () =>
    import("./editor.client.turbopack").then(
      (mod) => mod.MonacoYAMLEditorTurbopack
    ),
  { ssr: false }
);
