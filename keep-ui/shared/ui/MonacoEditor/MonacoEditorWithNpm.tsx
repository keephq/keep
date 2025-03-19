"use client";

import { Editor, EditorProps, loader } from "@monaco-editor/react";
import * as monaco from "monaco-editor";
import { KeepLoader } from "../KeepLoader/KeepLoader";
import { useConfig } from "@/utils/hooks/useConfig";
import { useEffect, useState } from "react";
import { ErrorComponent } from "../ErrorComponent/ErrorComponent";

// Monaco Editor - imported as an npm package instead of loading from the CDN to support air-gapped environments
// https://github.com/suren-atoyan/monaco-react?tab=readme-ov-file#use-monaco-editor-as-an-npm-package
loader.config({ monaco });

const Loader = <KeepLoader loadingText="Loading Code Editor ..." />;

export function MonacoEditorWithNpm(props: EditorProps) {
  const { data: config } = useConfig();
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
        defaultMessage={`Error loading Monaco Editor from ${config.BUILD_MONACO_EDITOR_NPM ? "NPM" : "CDN"}`}
        description={
          <>
            Check internet connection. If you are using Keep in an air-gapped
            environment, set
            <code className="text-gray-600 text-left bg-gray-100 px-2 py-1 mx-2 rounded-md">
              BUILD_MONACO_EDITOR_NPM=true
            </code>
            in keep-frontend environment variables.
          </>
        }
      />
    );
  }

  return <Editor {...props} loading={Loader} />;
}
