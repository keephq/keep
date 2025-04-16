"use client";

import { KeepLoader } from "../KeepLoader/KeepLoader";
import { useState } from "react";
import { ErrorComponent } from "../ErrorComponent/ErrorComponent";
import { setupCustomCellanguage } from "./cel-support";
import { MonacoCel } from "./monaco-cel-base.turbopack";
import { editor } from "monaco-editor";

const Loader = <KeepLoader loadingText="Loading Code Editor ..." />;

interface MonacoCelProps {
  className: string;
}

export function MonacoCelEditor(props: MonacoCelProps) {
  const [error, setError] = useState<Error | null>(null);
  const [editor, setEditor] = useState<editor.IStandaloneCodeEditor | null>(
    null
  );

  function monacoLoadedCallback(
    monacoInstance: typeof import("monaco-editor")
  ) {
    setupCustomCellanguage(monacoInstance);
  }

  const handleEditorDidMount = (
    editor: editor.IStandaloneCodeEditor,
    monaco: typeof import("monaco-editor")
  ) => {
    editor.onKeyDown((e) => {
      if (e.keyCode === monaco.KeyCode.Enter) {
        e.preventDefault(); // block typing Enter
      }
    });
    editor.onDidChangeModelContent(() => {
      const model = editor.getModel();
      if (!model) return;

      const value = model.getValue();
      if (value.includes("\n")) {
        model.setValue(value.replace(/\n/g, " "));
      }
    });
    setEditor(editor);
  };

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
    <MonacoCel
      onMonacoLoaded={monacoLoadedCallback}
      onMonacoLoadFailure={setError}
      onMount={handleEditorDidMount}
      className={props.className}
      language="cel"
      defaultLanguage="cel"
      theme="cel-dark"
      loading={Loader}
      wrapperProps={{
        style: {
          backgroundColor: "transparent", // ✅ wrapper transparency
        },
      }}
      height="30px" // 👈 small height
      options={{
        lineNumbers: "off",
        minimap: { enabled: false },
        scrollbar: {
          vertical: "hidden",
          horizontal: "hidden",
        },
        wordWrap: "off",
        scrollBeyondLastLine: false,
        overviewRulerLanes: 0,
        folding: false,
        lineDecorationsWidth: 0,
        lineNumbersMinChars: 0,
        renderLineHighlight: "none",
        fontSize: 14,
        padding: { top: 0, bottom: 0 },
      }}
    />
  );
}
