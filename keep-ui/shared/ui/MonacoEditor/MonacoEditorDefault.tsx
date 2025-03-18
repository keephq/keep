"use client";

import { Editor, EditorProps, loader } from "@monaco-editor/react";
import { KeepLoader } from "../KeepLoader/KeepLoader";
import { useEffect, useState } from "react";
import { ErrorComponent } from "../ErrorComponent/ErrorComponent";

const Loader = <KeepLoader loadingText="Loading Code Editor ..." />;

export function MonacoEditorDefault(props: EditorProps) {
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    const loadMonaco = async () => {
      loader.init().catch((error: any) => {
        setError(error);
      });
    };
    loadMonaco();
  }, []);

  if (error) {
    return (
      <ErrorComponent
        error={error}
        defaultMessage={`Error loading Monaco Editor from CDN`}
        description={
          <>
            Check internet connection. If you are using Keep in an air-gapped
            environment, set
            <code className="text-gray-600 text-left bg-gray-100 px-2 py-1 mx-2 rounded-md">
              MONACO_EDITOR_NPM=true
            </code>
            in keep-frontend environment variables.
          </>
        }
      />
    );
  }

  return <Editor {...props} loading={Loader} />;
}
