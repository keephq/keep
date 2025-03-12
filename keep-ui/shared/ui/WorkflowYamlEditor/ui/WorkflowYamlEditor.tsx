import { getYamlWorkflowDefinitionSchema } from "@/entities/workflows/model/yaml.schema";
import * as monaco from "monaco-editor";
import { zodToJsonSchema } from "zod-to-json-schema";
import { configureMonacoYaml } from "monaco-yaml";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Provider } from "@/shared/api/providers";
import { getOrCreateModel, Monaco } from "../lib/monaco-utils";
import clsx from "clsx";

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

const schemaUri = "file:///workflow-schema.json";

const noop = () => {};

export function WorkflowYamlEditor({
  providers,
  defaultValue = "",
  onMount = noop,
  options,
  theme = "light",
  wrapperProps,
}: {
  providers: Provider[] | undefined;
  defaultValue: string;
  onMount?: (
    editor: monaco.editor.IStandaloneCodeEditor,
    monaco: Monaco
  ) => void;
  options?: monaco.editor.IEditorOptions;
  theme?: string;
  wrapperProps?: React.HTMLAttributes<HTMLDivElement>;
}) {
  const [isEditorReady, setIsEditorReady] = useState(false);
  const editorRef = useRef<monaco.editor.IStandaloneCodeEditor | null>(null);
  const monacoRef = useRef<Monaco | null>(null);
  const onMountRef =
    useRef<
      (editor: monaco.editor.IStandaloneCodeEditor, monaco: Monaco) => void
    >(onMount);

  const globalSchema = useMemo(() => {
    if (!providers) return undefined;
    return zodToJsonSchema(
      // todo: is it efficient to generate the schema for each provider?
      getYamlWorkflowDefinitionSchema(providers),
      {
        name: "WorkflowSchema",
        $refStrategy: "none",
      }
    );
  }, [providers]);

  useEffect(() => {
    if (!globalSchema) return;

    configureMonacoYaml(monaco, {
      enableSchemaRequest: false,
      schemas: [
        {
          fileMatch: ["*"],
          schema: globalSchema,
          uri: schemaUri,
        },
      ],
    });

    monacoRef.current = monaco;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const setupEditor = useCallback((div: HTMLDivElement) => {
    if (!div || editorRef.current) {
      return;
    }
    const model = getOrCreateModel(monaco, defaultValue, "yaml", schemaUri);
    editorRef.current = monaco.editor.create(div, {
      model,
      quickSuggestions: {
        other: true,
        comments: false,
        strings: true,
      },
      ...options,
    });
    monacoRef.current?.editor.setTheme(theme);
    setIsEditorReady(true);
  }, []);

  useEffect(() => {
    if (isEditorReady) {
      onMountRef.current(editorRef.current!, monacoRef.current!);
    }
  }, [isEditorReady]);

  const { className, ...restWrapperProps } = wrapperProps || {};

  return (
    <div
      id="editor"
      className={clsx(
        "worfklow-yaml-editor-container w-full h-full rounded-[inherit] [&_.monaco-editor]:outline-none",
        className
      )}
      {...restWrapperProps}
      ref={setupEditor}
    ></div>
  );
}
