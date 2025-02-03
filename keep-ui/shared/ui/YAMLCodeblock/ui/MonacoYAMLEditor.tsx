import React, { useRef, useState, useEffect } from "react";
import { Download, Copy, Check, Save } from "lucide-react";
import { Card } from "@tremor/react";
import { Button } from "@tremor/react";
import Editor, { type EditorProps } from "@monaco-editor/react";
import { type editor } from "monaco-editor";
import yaml from "js-yaml";
import { useWorkflowActions } from "@/entities/workflows/model/useWorkflowActions";

const MonacoYAMLEditor = ({
  yamlString,
  filename,
  workflowId,
}: {
  yamlString: string;
  filename: string;
  workflowId: string;
}) => {
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const [isCopied, setIsCopied] = React.useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const [originalContent, setOriginalContent] = useState("");
  const { updateWorkflow } = useWorkflowActions();

  // Sort YAML keys in desired order
  const sortYamlKeys = (yamlStr: string) => {
    try {
      const parsed = yaml.load(yamlStr) as Record<string, unknown>;
      const keyOrder = ["workflow"];
      const workflowKeyOrder = [
        "id",
        "name",
        "debug",
        "description",
        "triggers",
        "steps",
        "actions",
      ];

      const sorted: Record<string, unknown> = {};

      if ("workflow" in parsed) {
        const workflowObj = parsed.workflow as Record<string, unknown>;
        const sortedWorkflow: Record<string, unknown> = {};

        workflowKeyOrder.forEach((key) => {
          if (key in workflowObj) {
            sortedWorkflow[key] = workflowObj[key];
          }
        });

        Object.keys(workflowObj).forEach((key) => {
          if (!workflowKeyOrder.includes(key)) {
            sortedWorkflow[key] = workflowObj[key];
          }
        });

        sorted.workflow = sortedWorkflow;
      }

      Object.keys(parsed).forEach((key) => {
        if (!keyOrder.includes(key)) {
          sorted[key] = parsed[key];
        }
      });

      return yaml.dump(sorted, { indent: 2, lineWidth: 9999 });
    } catch (err) {
      console.error("Failed to sort YAML:", err);
      return yamlStr;
    }
  };

  const sortedYaml = sortYamlKeys(yamlString);

  useEffect(() => {
    setOriginalContent(sortedYaml);
  }, []);

  const handleEditorDidMount = (editor: editor.IStandaloneCodeEditor) => {
    editorRef.current = editor;
    editor.onDidChangeModelContent(() => {
      const currentContent = editor.getValue();
      setHasChanges(currentContent !== originalContent);
    });
  };

  const handleSaveWorkflow = async () => {
    if (!editorRef.current) return;

    const content = editorRef.current.getValue();
    try {
      const parsedYaml = yaml.load(content) as {
        workflow: Record<string, unknown>;
      };
      // update workflow
      await updateWorkflow(workflowId!, parsedYaml);

      setOriginalContent(content);
      setHasChanges(false);
    } catch (err) {
      console.error("Failed to save workflow:", err);
    }
  };

  const downloadYaml = () => {
    if (!editorRef.current) return;
    const content = editorRef.current.getValue();
    const blob = new Blob([content], { type: "text/yaml" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${filename}.yaml`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const copyToClipboard = async () => {
    if (!editorRef.current) return;
    const content = editorRef.current.getValue();
    try {
      await navigator.clipboard.writeText(content);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy text:", err);
    }
  };

  const getLineCount = () => {
    if (editorRef.current) {
      return editorRef.current.getModel()?.getLineCount() ?? 0;
    }
    return 0;
  };

  const getCharacterCount = () => {
    if (editorRef.current) {
      return editorRef.current.getModel()?.getValue().length ?? 0;
    }
    return 0;
  };

  const editorOptions: editor.IStandaloneEditorConstructionOptions = {
    minimap: { enabled: false },
    lineNumbers: "on" as const,
    scrollBeyondLastLine: false,
    automaticLayout: true,
    tabSize: 2,
    insertSpaces: true,
    fontSize: 14,
    renderWhitespace: "all",
    wordWrap: "off",
    // : 120,
    theme: "vs-light",
  };

  return (
    <div className="w-full h-full flex flex-col">
      <div className="relative flex-1 min-h-0">
        <div className="absolute right-2 top-2 z-10 flex gap-2">
          <Button
            color="orange"
            size="sm"
            className="h-8 px-2 bg-white"
            onClick={handleSaveWorkflow}
            variant="secondary"
            disabled={!hasChanges}
          >
            <Save className="h-4 w-4" />
          </Button>
          <Button
            color="orange"
            size="sm"
            className="h-8 px-2 bg-white"
            onClick={copyToClipboard}
            variant="secondary"
          >
            {isCopied ? (
              <Check className="h-4 w-4 text-green-500" />
            ) : (
              <Copy className="h-4 w-4" />
            )}
          </Button>
          <Button
            color="orange"
            size="sm"
            className="h-8 px-2 bg-white"
            onClick={downloadYaml}
            variant="secondary"
          >
            <Download className="h-4 w-4" />
          </Button>
        </div>
        <Editor
          height="100%"
          defaultLanguage="yaml"
          defaultValue={sortedYaml}
          onMount={handleEditorDidMount}
          options={editorOptions}
        />
      </div>
      <div className="flex items-center justify-between px-4 py-2 border-t border-gray-200">
        <span className="text-sm text-gray-500">{filename}.yaml</span>
        <div className="flex gap-2">
          <span className="text-sm text-gray-500">{getLineCount()} lines</span>
          <span className="text-sm text-gray-500">·</span>
          <span className="text-sm text-gray-500">
            {getCharacterCount()} characters
          </span>
        </div>
      </div>
    </div>
  );
};

export default MonacoYAMLEditor;
