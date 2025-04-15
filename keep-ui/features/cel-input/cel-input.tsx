import React, { ChangeEvent, FC, useRef, useState } from "react";
import type { editor } from "monaco-editor";
import { MonacoCelCDN } from "@/shared/ui/MonacoCELEditor/MonacoCelCDN";

interface CelInputProps {
  value?: string;
  onChange?: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
}

const CelInput: FC<CelInputProps> = ({
  value = "",
  onChange,
  placeholder = "Enter value",
  disabled = false,
}) => {
  const monacoRef = useRef<typeof import("monaco-editor") | null>(null);
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const [inputValue, setInputValue] = useState(value);
  const [isEditorMounted, setIsEditorMounted] = useState(false);

  const handleEditorDidMount = (
    editor: editor.IStandaloneCodeEditor,
    monacoInstance: typeof import("monaco-editor")
  ) => {
    editorRef.current = editor;
    monacoRef.current = monacoInstance;
    editor.onDidChangeModelContent(() => {
      const model = editor.getModel();
      if (!model) return;

      const tokens = monacoInstance.editor.tokenize(model.getValue(), "cel");
      console.log("Ihor TOKENS:", tokens);
    });

    setIsEditorMounted(true);
  };

  const handleChange = (event: ChangeEvent<HTMLInputElement>) => {
    const newValue = event.target.value;
    setInputValue(newValue);
    if (onChange) {
      onChange(newValue);
    }
  };

  return (
    // <input
    //   type="text"
    //   value={inputValue}
    //   onChange={handleChange}
    //   placeholder={placeholder}
    //   disabled={disabled}
    //   className="cel-input"
    // />

    <MonacoCelCDN
      // value={JSON.stringify(eventData, null, 2)}
      //   language="celavito"
      //   defaultLanguage="celavito"
      //   theme="cel-dark"
      className="h-20"
      //   onMount={handleEditorDidMount}
      //   options={{
      //     readOnly: false,
      //     minimap: { enabled: false },
      //     scrollBeyondLastLine: false,
      //     fontSize: 12,
      //     lineNumbers: "off",
      //     folding: false,
      //     wordWrap: "off",
      //   }}
    />
  );
};

export default CelInput;
