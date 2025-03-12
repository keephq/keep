import { getYamlWorkflowDefinitionSchema } from "@/entities/workflows/model/yaml.schema";
import * as monaco from "monaco-editor";
import { zodToJsonSchema } from "zod-to-json-schema";
import { configureMonacoYaml } from "monaco-yaml";
import { useCallback, useEffect, useRef, useState } from "react";
import { Provider } from "@/shared/api/providers";
import { Monaco } from "../lib/monaco-utils";
import clsx from "clsx";
import Editor, { EditorProps, loader, useMonaco } from "@monaco-editor/react";
import { KeepSchemaPath } from "../lib/constants";

// todo: setup with dispose like in monaco-editor/react lib
self.MonacoEnvironment = {
  getWorker(moduleId, label) {
    console.log("monaco-yaml: Loading worker for:", label);
    switch (label) {
      case "yaml":
        return new Worker(new URL("monaco-yaml/yaml.worker", import.meta.url));
      case "editorWorkerService":
        return new Worker(
          new URL("monaco-editor/esm/vs/editor/editor.worker", import.meta.url)
        );
      default:
        throw new Error(`Unknown label ${label}`);
    }
  },
};

const noop = () => {};

export function EditorExtended({
  providers,
  beforeMount,
  ...rest
}: {
  providers: Provider[];
} & EditorProps) {
  const [isConfigured, setConfigured] = useState(false);

  const configureYamlSchema = useCallback((monaco: Monaco) => {
    const globalSchema = zodToJsonSchema(
      // todo: is it efficient to generate the schema for each provider?
      getYamlWorkflowDefinitionSchema(providers),
      {
        name: "WorkflowSchema",
        $refStrategy: "none",
      }
    );

    configureMonacoYaml(monaco, {
      enableSchemaRequest: false,
      schemas: [
        {
          fileMatch: ["*"],
          schema: globalSchema,
          uri: KeepSchemaPath,
        },
      ],
    });

    setConfigured(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    loader.init().then((monaco) => configureYamlSchema(monaco));
  }, []);

  // function handleEditorWillMount(monaco: Monaco) {
  //   if (!configuredRef.current) {
  //     configureYamlSchema(monaco);
  //   }
  //   beforeMount?.(monaco);
  // }

  if (!isConfigured) {
    return "Configuring Monaco";
  }

  return <Editor beforeMount={beforeMount} {...rest} />;
}
