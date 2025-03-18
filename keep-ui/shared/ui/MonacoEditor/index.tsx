"use client";

import dynamic from "next/dynamic";
import { EditorProps } from "@monaco-editor/react";

const MonacoEditorDynamic = dynamic(
  () => {
    if (process.env.NEXT_PUBLIC_KEEP_MONACO_AS_NPM === "true") {
      // importing the Monaco Editor as an npm package to support air-gapped environments
      // IMPORTANT: breaks in dev mode with turbopack
      return import("./MonacoEditorWithNpm").then(
        (mod) => mod.MonacoEditorWithNpm
      );
    } else {
      // Default implementation with the Monaco Editor loaded from the CDN
      return import("./MonacoEditorDefault").then(
        (mod) => mod.MonacoEditorDefault
      );
    }
  },
  {
    ssr: false, // Important: Disable server-side rendering for Monaco
  }
);

export function MonacoEditor(props: EditorProps) {
  return <MonacoEditorDynamic {...props} />;
}
