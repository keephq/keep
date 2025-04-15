"use client";

import { Editor, EditorProps, loader } from "@monaco-editor/react";
import { KeepLoader } from "../KeepLoader/KeepLoader";
import { useEffect, useRef, useState } from "react";
import { ErrorComponent } from "../ErrorComponent/ErrorComponent";
import { setupCustomCellanguage } from "./cel-support";
import type { editor } from "monaco-editor";

const Loader = <KeepLoader loadingText="Loading Code Editor ..." />;

export function MonacoCelCDN(props: EditorProps) {
  const [error, setError] = useState<Error | null>(null);
  const [isLoaded, setIsLoaded] = useState(false);
  const monacoRef = useRef<typeof import("monaco-editor") | null>(null);
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const [isEditorMounted, setIsEditorMounted] = useState(false);

  useEffect(() => {
    loader
      .init()
      .then((monacoInstance) => {
        setupCustomCellanguage(monacoInstance);
        setIsLoaded(true);
      })
      .catch((error: Error) => {
        setError(error);
      });
  }, []);

  const handleEditorDidMount = (
    editor: editor.IStandaloneCodeEditor,
    monaco: typeof import("monaco-editor")
  ) => {
    editorRef.current = editor;
    monacoRef.current = monaco;
    // editor.onDidChangeModelContent(() => {
    //   const model = editor.getModel();
    //   if (!model) return;

    //   const tokens = monacoInstance.editor.tokenize(model.getValue(), "cel");
    //   console.log("Ihor TOKENS:", tokens);
    // });

    editor.onKeyDown((e) => {
      if (e.keyCode === monaco.KeyCode.Enter) {
        e.preventDefault();
      }
    });

    setIsEditorMounted(true);
  };

  const handleEditorBeforeMount = (monaco: typeof import("monaco-editor")) => {
    console.log("Ihor Registered languages:", monaco.languages.getLanguages());
  };

  if (!isLoaded) {
    return null;
  }

  if (error) {
    return (
      <ErrorComponent
        error={error}
        defaultMessage={`Error loading Monaco Editor from CDN`}
        description="Check your internet connection and try again"
      />
    );
  }

  return (
    <Editor
      beforeMount={handleEditorBeforeMount}
      className="h-20"
      language="cel"
      defaultLanguage="cel"
      theme="cel-dark"
      loading={Loader}
      onMount={handleEditorDidMount}
      options={{
        readOnly: false,
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
        fontSize: 12,
        lineNumbers: "off",
        folding: false,
        wordWrap: "off",
      }}
    />
  );
}
