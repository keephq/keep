import { EditorProps } from "@monaco-editor/react";

export type MonacoYamlEditorProps = {
  schemas: {
    fileMatch: string[];
    schema: object;
    uri: string;
  }[];
  original?: string;
  modified?: string;
} & EditorProps;
