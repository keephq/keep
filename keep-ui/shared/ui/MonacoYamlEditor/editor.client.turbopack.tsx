"use client";

// NOTE: this file is only used for turbopack, so it uses the CDN version of monaco-editor and pre-built monaco-yaml workers

import { useEffect, useState } from "react";
import { configureMonacoYaml, MonacoYaml } from "monaco-yaml";
import { Editor, loader, type EditorProps } from "@monaco-editor/react";
import { KeepLoader, ErrorComponent } from "@/shared/ui";

const Loader = <KeepLoader loadingText="Loading Code Editor ..." />;

loader.config({
  paths: {
    vs: "https://cdn.jsdelivr.net/npm/monaco-editor@0.52.2/min/vs",
  },
});

// In the docs, it is stated that there should only be one monaco yaml instance configured at a time
let monacoYamlInstance: MonacoYaml | undefined;

self.MonacoEnvironment = {
  getWorker(_, label) {
    switch (label) {
      case "yaml":
        return new window.Worker(
          window.location.origin + "/monaco-workers/yaml.worker.js"
        );
      case "json":
        return new window.Worker(
          window.location.origin + "/monaco-workers/json.worker.js"
        );
      case "editorWorkerService":
        return new window.Worker(
          window.location.origin + "/monaco-workers/editor.worker.js"
        );
      default:
        throw new Error(`Unknown label ${label}`);
    }
  },
};

type MonacoYamlEditorProps = {
  schemas: {
    fileMatch: string[];
    schema: object;
    uri: string;
  }[];
} & EditorProps;

/**
 * This is a custom editor component that uses 'monaco-yaml' to provide YAML language support.
 * It is used to edit YAML files.
 */
export function MonacoYAMLEditorTurbopack({
  schemas,
  ...props
}: MonacoYamlEditorProps) {
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (schemas) {
      monacoYamlInstance?.update({
        enableSchemaRequest: false,
        schemas,
      });
    }
  }, [schemas]);

  useEffect(() => {
    loader
      .init()
      .then((monaco) => {
        if (!monacoYamlInstance) {
          monacoYamlInstance = configureMonacoYaml(monaco, {
            hover: true,
            completion: true,
            validate: true,
            format: true,
            enableSchemaRequest: false,
            schemas: schemas ?? undefined,
          });
        }
      })
      .catch((error: Error) => {
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

  return <Editor defaultLanguage="yaml" loading={Loader} {...props} />;
}
