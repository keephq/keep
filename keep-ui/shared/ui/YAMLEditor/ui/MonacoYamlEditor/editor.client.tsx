"use client";

import { useEffect } from "react";
import { configureMonacoYaml, MonacoYaml } from "monaco-yaml";
import type { EditorProps, Monaco } from "@monaco-editor/react";
import { MonacoEditor } from "@/shared/ui";

// Loading these workers from NPM only works with webpack. Turbopack does not support import(`${url}`), which is used in monaco-editor and monaco-yaml.
// For development, we can use the workers from the local dist folder or CDN. TODO: figure out how to do this in Turbopack.
self.MonacoEnvironment = {
  getWorker(_, label) {
    console.log("getWorker", label);
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
export function MonacoYAMLEditor({ schemas, ...props }: YamlEditorProps) {
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
    <MonacoEditor
      defaultLanguage="yaml"
      beforeMount={handleEditorBeforeMount}
      {...props}
    />
  );
}
