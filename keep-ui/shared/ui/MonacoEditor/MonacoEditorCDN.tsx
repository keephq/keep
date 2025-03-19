"use client";

import { Editor, EditorProps, loader } from "@monaco-editor/react";
import { KeepLoader } from "../KeepLoader/KeepLoader";
import { useEffect, useState } from "react";
import { ErrorComponent } from "../ErrorComponent/ErrorComponent";

const Loader = <KeepLoader loadingText="Loading Code Editor ..." />;

loader.config({
  paths: {
    vs: window.location.origin + "/monaco-editor/vs",
  },
});

// window.MonacoEnvironment = {
//   getWorkerUrl: function (moduleId, label) {
//     if (label === "json") {
//       return "/monaco-editor/json.worker.js";
//     }
//     if (label === "css" || label === "scss" || label === "less") {
//       return "/monaco-editor/css.worker.js";
//     }
//     if (label === "html" || label === "handlebars" || label === "razor") {
//       return "/monaco-editor/html.worker.js";
//     }
//     if (label === "typescript" || label === "javascript") {
//       return "/monaco-editor/ts.worker.js";
//     }
//     return "/monaco-editor/editor.worker.js";
//   },
// };

export function MonacoEditorCDN(props: EditorProps) {
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    loader.init().catch((error: Error) => {
      setError(error);
    });
  }, []);

  if (error) {
    return (
      <ErrorComponent
        error={error}
        defaultMessage={`Error loading Monaco Editor from CDN`}
        description="Check your internet connection and try again"
      />
    );
  }

  return <Editor {...props} loading={Loader} />;
}
