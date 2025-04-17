"use client";

import { KeepLoader } from "../KeepLoader/KeepLoader";
import { useRef, useState } from "react";
import { ErrorComponent } from "../ErrorComponent/ErrorComponent";
import { setupCustomCellanguage } from "./cel-support";
import { MonacoCel } from "./monaco-cel-base.turbopack";
import { editor } from "monaco-editor";

const Loader = <KeepLoader loadingText="Loading Code Editor ..." />;

interface MonacoCelProps {
  className: string;
  value: string;
  onValueChange: (value: string) => void;
  onKeyDown?: (e: KeyboardEvent) => void;
  onFocus?: () => void;
}

export function MonacoCelEditor(props: MonacoCelProps) {
  const [error, setError] = useState<Error | null>(null);
  const [editor, setEditor] = useState<editor.IStandaloneCodeEditor | null>(
    null
  );
  const onKeyDownRef = useRef<MonacoCelProps["onKeyDown"]>(props.onKeyDown);
  onKeyDownRef.current = props.onKeyDown;
  const onFocusRef = useRef<MonacoCelProps["onFocus"]>(props.onFocus);
  onFocusRef.current = props.onFocus;

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
      onKeyDownRef.current?.(e.browserEvent);

      if (e.keyCode === monaco.KeyCode.Enter) {
        e.preventDefault(); // block typing Enter
      }
    });
    editor.onDidFocusEditorText(() => onFocusRef.current?.());
    editor.onDidChangeModelContent(() => {
      const model = editor.getModel();
      if (!model) return;

      const value = model.getValue();
      if (value.includes("\n")) {
        model.setValue(value.replace(/\n/g, " "));
      }
      const tokens = monaco.editor.tokenize(value, "cel");
      console.log("Ihor CEL Tokens:", tokens);
    });

    const model = editor.getModel();

    if (!model) {
      return;
    }

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
      onChange={(val) => props.onValueChange(val || "")}
      className={props.className}
      language="cel"
      defaultLanguage="cel"
      theme="cel-dark"
      loading={Loader}
      value={props.value}
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
