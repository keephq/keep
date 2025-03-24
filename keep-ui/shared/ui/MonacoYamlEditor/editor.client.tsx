"use client";

import { useEffect, useState } from "react";
import { configureMonacoYaml, MonacoYaml } from "monaco-yaml";
import { Editor, loader, type EditorProps } from "@monaco-editor/react";
import { useConfig } from "@/utils/hooks/useConfig";
import { KeepLoader, ErrorComponent } from "@/shared/ui";
import * as monaco from "monaco-editor";

// Loading these workers from NPM only works with webpack. For turbopack, we use 'editor.client.turbopack.tsx'
self.MonacoEnvironment = {
  getWorker(_, label) {
    switch (label) {
      case "yaml":
        return new Worker(new URL("monaco-yaml/yaml.worker", import.meta.url));
      case "json":
        return new Worker(
          new URL(
            "monaco-editor/esm/vs/language/json/json.worker",
            import.meta.url
          )
        );
      case "editorWorkerService":
        return new Worker(
          new URL("monaco-editor/esm/vs/editor/editor.worker", import.meta.url)
        );
      default:
        throw new Error(`Unknown label ${label}`);
    }
  },
};

loader.config({
  monaco,
});

const Loader = <KeepLoader loadingText="Loading Code Editor ..." />;

// In the docs, it is stated that there should only be one monaco yaml instance configured at a time
let monacoYamlInstance: MonacoYaml | undefined;

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
export function MonacoYAMLEditor({ schemas, ...props }: MonacoYamlEditorProps) {
  useEffect(() => {
    if (schemas) {
      monacoYamlInstance?.update({
        enableSchemaRequest: false,
        schemas,
      });
    }
  }, [schemas]);

  const { data: config } = useConfig();
  const [error, setError] = useState<Error | null>(null);

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

  return <Editor defaultLanguage="yaml" loading={Loader} {...props} />;
}
