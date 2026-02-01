"use client";

import { Editor, EditorProps, loader } from "@monaco-editor/react";
import { KeepLoader } from "../KeepLoader/KeepLoader";
import { useEffect, useState } from "react";
import { ErrorComponent } from "../ErrorComponent/ErrorComponent";

const Loader = <KeepLoader loadingText="Loading Code Editor ..." />;

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
