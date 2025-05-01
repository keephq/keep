"use client";

import { KeepLoader } from "../KeepLoader/KeepLoader";
import { useEffect, useRef, useState } from "react";
import { ErrorComponent } from "../ErrorComponent/ErrorComponent";
import { setupCustomCellanguage } from "./cel-support";
import { MonacoCelBase } from "./MonacoCel";
import { editor, Token } from "monaco-editor";
import "./editor.scss";
import { useCelValidation } from "./validation-hook";

const Loader = <KeepLoader loadingText="Loading Code Editor ..." />;

interface MonacoCelProps {
  editorId?: string;
  className: string;
  value: string;
  fieldsForSuggestions?: string[];
  readOnly?: boolean;
  onIsValidChange?: (isValid: boolean) => void;
  onValueChange: (value: string) => void;
  onKeyDown?: (e: KeyboardEvent) => void;
  onFocus?: () => void;
}

export function MonacoCelEditor(props: MonacoCelProps) {
  const [error, setError] = useState<Error | null>(null);
  const [isEditorMounted, setIsEditorMounted] = useState(false);
  const monacoInstanceRef = useRef<typeof import("monaco-editor") | null>(null);
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const modelRef = useRef<editor.ITextModel | null>(null);
  const onKeyDownRef = useRef<MonacoCelProps["onKeyDown"]>(props.onKeyDown);
  onKeyDownRef.current = props.onKeyDown;
  const onIsValidChangeRef = useRef<MonacoCelProps["onIsValidChange"]>(
    props.onIsValidChange
  );
  onIsValidChangeRef.current = props.onIsValidChange;
  const onFocusRef = useRef<MonacoCelProps["onFocus"]>(props.onFocus);
  onFocusRef.current = props.onFocus;
  const fieldsForSuggestionsRef =
    useRef<MonacoCelProps["fieldsForSuggestions"]>();
  fieldsForSuggestionsRef.current = props.fieldsForSuggestions;
  const enteredTokensRef = useRef<Token[]>([]);
  const suggestionsShownRef = useRef<boolean>();
  const [value, setValue] = useState<string>(props.value);

  const validationErrors = useCelValidation(value);

  useEffect(() => {
    if (!isEditorMounted) {
      return;
    }

    monacoInstanceRef.current?.editor.setModelMarkers(
      editorRef.current?.getModel()!,
      "cel",
      validationErrors
    );
    onIsValidChangeRef.current?.(validationErrors.length === 0);
  }, [isEditorMounted, validationErrors]);

  function monacoLoadedCallback(
    monacoInstance: typeof import("monaco-editor")
  ) {
    monacoInstanceRef.current = monacoInstance;
    setupCustomCellanguage(monacoInstance);
  }

  useEffect(() => {
    if (!isEditorMounted) return;

    (modelRef.current as any).___fieldsForSuggestions___ =
      props.fieldsForSuggestions;
    if (props.editorId) {
      (modelRef.current as any).editorId = props.editorId;
    }
  }, [props.fieldsForSuggestions, props.editorId, isEditorMounted]);

  const handleEditorDidMount = (
    editor: editor.IStandaloneCodeEditor,
    monaco: typeof import("monaco-editor")
  ) => {
    editorRef.current = editor;
    modelRef.current = editor.getModel();
    setIsEditorMounted(true);
    editor.onKeyDown((e) => {
      if (e.keyCode === monaco.KeyCode.Enter) {
        e.preventDefault(); // block typing Enter

        if (suggestionsShownRef.current) {
          return;
        }
      }

      onKeyDownRef.current?.(e.browserEvent);
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

    const suggestController = editorRef.current.getContribution(
      "editor.contrib.suggestController"
    );

    const suggestionWidget = (suggestController as any)?.widget;
    // NOTE: This is left commented on purpose. This snippet allows to disable
    // the suggestion widget from hiding up when the user clicks outside of the input.
    // Super useful for debugging to inspect suggestions.
    // if ((suggestController as any)?.widget?.value) {
    //   (suggestController as any).widget.value.hideWidget = () => {}; // NO-OP
    // }

    if (suggestionWidget) {
      suggestionWidget.value.onDidShow(() => {
        suggestionsShownRef.current = true;
      });
      suggestionWidget.value.onDidHide(() => {
        suggestionsShownRef.current = false;
      });
    }
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
    <MonacoCelBase
      onMonacoLoaded={monacoLoadedCallback}
      onMonacoLoadFailure={setError}
      onMount={handleEditorDidMount}
      onChange={(val) => {
        val = val || "";
        setValue(val);
        props.onValueChange(val);
      }}
      className={`${props.editorId ? props.editorId + " " : ""}monaco-cel-editor ${props.className}`}
      language="cel"
      defaultLanguage="cel"
      theme="vs"
      loading={Loader}
      value={value}
      wrapperProps={{
        style: {
          backgroundColor: "transparent", // ✅ wrapper transparency
          height: "60px",
          overflow: "visible", // 👈 allow suggestions to overflow
          position: "relative",
        },
      }}
      options={{
        readOnly: props.readOnly,
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
        glyphMargin: false,
      }}
    />
  );
}
