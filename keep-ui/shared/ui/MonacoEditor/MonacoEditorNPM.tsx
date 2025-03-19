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

export function MonacoEditorNPM(props: EditorProps) {
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
        defaultMessage="Error loading Monaco Editor from NPM"
        description={
          <>
            This should not happen. Please contact us on Slack
            <a href={config.KEEP_CONTACT_US_URL} target="_blank">
              {config.KEEP_CONTACT_US_URL}
            </a>
          </>
        }
      />
    );
  }

  return <Editor {...props} loading={Loader} />;
}
