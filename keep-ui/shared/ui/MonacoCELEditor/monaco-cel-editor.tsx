"use client";

import { KeepLoader } from "../KeepLoader/KeepLoader";
import { useEffect, useRef, useState } from "react";
import { ErrorComponent } from "../ErrorComponent/ErrorComponent";
import { setupCustomCellanguage } from "./cel-support";
import { MonacoCel } from "./monaco-cel-base.turbopack";
import { editor, Token } from "monaco-editor";
import { handleCompletions } from "./handle-completions";

const Loader = <KeepLoader loadingText="Loading Code Editor ..." />;

interface MonacoCelProps {
  className: string;
  value: string;
  fieldsForSuggestions?: string[];
  onValueChange: (value: string) => void;
  onKeyDown?: (e: KeyboardEvent) => void;
  onFocus?: () => void;
}

export function MonacoCelEditor(props: MonacoCelProps) {
  const [error, setError] = useState<Error | null>(null);
  const [isEditorMounted, setIsEditorMounted] = useState(false);
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const modelRef = useRef<editor.ITextModel | null>(null);
  const onKeyDownRef = useRef<MonacoCelProps["onKeyDown"]>(props.onKeyDown);
  onKeyDownRef.current = props.onKeyDown;
  const onFocusRef = useRef<MonacoCelProps["onFocus"]>(props.onFocus);
  onFocusRef.current = props.onFocus;
  const fieldsForSuggestionsRef =
    useRef<MonacoCelProps["fieldsForSuggestions"]>();
  fieldsForSuggestionsRef.current = props.fieldsForSuggestions;
  const enteredTokensRef = useRef<Token[]>([]);

  function monacoLoadedCallback(
    monacoInstance: typeof import("monaco-editor")
  ) {
    monacoInstance.languages.registerCompletionItemProvider("cel", {
      triggerCharacters: ["."], // or "" if you want auto-trigger on any char

      provideCompletionItems: (model, position, context, cancellationToken) =>
        handleCompletions(model, position, context, cancellationToken),
    });
    setupCustomCellanguage(monacoInstance);
  }

  useEffect(() => {
    if (!isEditorMounted) return;

    (modelRef.current as any).___fieldsForSuggestions___ =
      props.fieldsForSuggestions;
  }, [props.fieldsForSuggestions, isEditorMounted]);

  const handleEditorDidMount = (
    editor: editor.IStandaloneCodeEditor,
    monaco: typeof import("monaco-editor")
  ) => {
    editorRef.current = editor;
    modelRef.current = editor.getModel();
    setIsEditorMounted(true);
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
      enteredTokensRef.current = monaco.editor.tokenize(value, "cel")[0];
    });
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
