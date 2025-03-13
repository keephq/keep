"use client";

import { useEffect } from "react";
import { Editor, EditorProps, type Monaco } from "@monaco-editor/react";
import { configureMonacoYaml, MonacoYaml } from "monaco-yaml";
import { loader } from "@monaco-editor/react";
import * as monaco from "monaco-editor";

// Loading these workers only works with webpack. Turbopack does not support it.
self.MonacoEnvironment = {
  getWorker(_, label) {
    switch (label) {
      case "yaml":
        return new Worker(new URL("monaco-yaml/yaml.worker", import.meta.url));
      default:
        return new Worker(
          new URL("monaco-editor/esm/vs/editor/editor.worker", import.meta.url)
        );
    }
  },
};

loader.config({ monaco });

// In the docs, it is stated that there should only be one monaco yaml instance configured at a time
let monacoYamlInstance: MonacoYaml | undefined;

type YamlEditorProps = {
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
export function YamlEditor({ schemas, ...props }: YamlEditorProps) {
  useEffect(() => {
    if (schemas) {
      monacoYamlInstance?.update({
        enableSchemaRequest: false,
        schemas,
      });
    }
  }, [schemas]);

  const handleEditorBeforeMount = (monaco: Monaco) => {
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
  };

  return (
    <Editor
      defaultLanguage="yaml"
      beforeMount={handleEditorBeforeMount}
      {...props}
    />
  );
}
