import * as monaco from "monaco-editor";
import {
  Editor,
  EditorProps,
  loader as monacoLoader,
} from "@monaco-editor/react";

// Monaco Editor - imported as an npm package instead of loading from the CDN to support air-gapped environments
// https://github.com/suren-atoyan/monaco-react?tab=readme-ov-file#use-monaco-editor-as-an-npm-package
monacoLoader.config({ monaco });

export function MonacoEditorWithNpm(props: EditorProps) {
  return <Editor {...props} />;
}
