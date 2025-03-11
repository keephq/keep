import React, { useCallback, useRef, useState } from "react";
import Editor, { BeforeMount } from "@monaco-editor/react";
import { type editor, type languages, type IRange } from "monaco-editor";
import { useProviders } from "@/utils/hooks/useProviders";
import { parseWorkflowYamlStringToJSON } from "@/entities/workflows/lib/yaml-utils";
import { YamlWorkflowDefinition } from "@/entities/workflows/model/yaml.types";
import { validateYamlString } from "@/entities/workflows/lib/validate-yaml";
import { getYamlWorkflowDefinitionSchema } from "@/entities/workflows/model/yaml.schema";
import { Provider } from "@/shared/api/providers";
import "./MonacoYAMLEditor.css";
import { Document, isPair, isSeq, Pair, visit } from "yaml";

interface Props {
  value: string;
  onChange?: (value: string) => void;
  readOnly?: boolean;
  height?: string;
  "data-testid"?: string;
  providers: Provider[];
  installedProviders: Provider[];
}

// Define the YAML language configuration
const yamlLanguageConfiguration: languages.LanguageConfiguration = {
  comments: {
    lineComment: "#",
  },
  brackets: [
    ["{", "}"],
    ["[", "]"],
    ["(", ")"],
  ],
  autoClosingPairs: [
    { open: "{", close: "}" },
    { open: "[", close: "]" },
    { open: "(", close: ")" },
    { open: '"', close: '"' },
    { open: "'", close: "'" },
  ],
  surroundingPairs: [
    { open: "{", close: "}" },
    { open: "[", close: "]" },
    { open: "(", close: ")" },
    { open: '"', close: '"' },
    { open: "'", close: "'" },
  ],
  folding: {
    offSide: true,
  },
  indentationRules: {
    increaseIndentPattern: /^.*:\s*$/,
    decreaseIndentPattern: /^\s*-\s*$/,
  },
};

// Define common workflow fields for autocompletion
const workflowFields = [
  { label: "name", documentation: "The name of the workflow step" },
  { label: "steps", documentation: "List of workflow steps" },
  { label: "id", documentation: "Unique identifier for the workflow" },
  { label: "description", documentation: "Description of the workflow" },
  { label: "disabled", documentation: "Whether the workflow is disabled" },
  { label: "owners", documentation: "List of workflow owners" },
  {
    label: "services",
    documentation: "List of services associated with the workflow",
  },
  { label: "triggers", documentation: "List of workflow triggers" },
  { label: "consts", documentation: "Constant values for the workflow" },
];

const _MonacoEditorWithValidation: React.FC<Props> = ({
  value,
  providers,
  installedProviders,
  onChange,
  readOnly = false,
  height = "100%",
  "data-testid": dataTestId = "yaml-editor",
}) => {
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const [validationResult, setValidationResult] = useState<any>(null);
  const validationResultRef = useRef<any>(null);
  const [parsedWorkflow, setParsedWorkflow] =
    useState<YamlWorkflowDefinition | null>(null);
  const [isEditorMounted, setIsEditorMounted] = useState(false);
  const [currentContent, setCurrentContent] = useState(value);

  // debug
  const [lastPath, setLastPath] = useState<string[]>([]);
  const lastPathRef = useRef<string[]>([]);

  const validateWorkflowYaml = useCallback(
    (yamlString: string) => {
      // TODO: extend schema with providers
      const schema = getYamlWorkflowDefinitionSchema(providers ?? []);
      return validateYamlString(yamlString, schema);
    },
    [providers]
  );

  const beforeMount: BeforeMount = (monaco) => {
    // Register YAML language configuration
    monaco.languages.setLanguageConfiguration(
      "yaml",
      yamlLanguageConfiguration
    );

    // Set up validation using markers
    const updateDiagnostics = (model: editor.ITextModel) => {
      const content = model.getValue();
      const validationResult = validateWorkflowYaml(content);
      const owner = "yaml-validator";
      setValidationResult(validationResult);
      validationResultRef.current = validationResult;
      setParsedWorkflow(
        parseWorkflowYamlStringToJSON(content)?.workflow ?? null
      );
      if (!validationResult.errors) {
        monaco.editor.setModelMarkers(model, owner, []);
        return;
      }

      const markers = validationResult.errors.map(
        ({ message, line = 1, col = 1 }) => ({
          severity: monaco.MarkerSeverity.Error,
          message,
          startLineNumber: line,
          startColumn: col,
          endLineNumber: line,
          endColumn: model.getLineMaxColumn(line),
          source: "YAML Validator",
        })
      );

      monaco.editor.setModelMarkers(model, owner, markers);
    };

    // Register a content change listener for validation
    monaco.editor.onDidCreateModel((model) => {
      if (model.getLanguageId() === "yaml") {
        updateDiagnostics(model);
        model.onDidChangeContent(() => updateDiagnostics(model));
      }
    });

    // Register completion provider with more sophisticated suggestions
    monaco.languages.registerCompletionItemProvider("yaml", {
      provideCompletionItems: (model, position) => {
        console.log("provideCompletionItems called", position);
        const word = model.getWordUntilPosition(position);
        const range = {
          startLineNumber: position.lineNumber,
          endLineNumber: position.lineNumber,
          startColumn: word.startColumn,
          endColumn: word.endColumn,
        };

        const lineContent = model.getLineContent(position.lineNumber);
        const indentation = lineContent.match(/^\s*/)?.[0] || "";

        // Get the full context up to the current line
        const textUntilLine = model.getValueInRange({
          startLineNumber: 1,
          startColumn: 1,
          endLineNumber: position.lineNumber,
          endColumn: position.column,
        });

        let suggestions: languages.CompletionItem[] = [];

        // Get current document structure from validation result
        const documentStructure = validationResultRef.current?.document;
        const currentPath = getCurrentPath(
          documentStructure,
          textUntilLine.length
        );
        if (currentPath.length > 0) {
          setLastPath(currentPath);
          lastPathRef.current = currentPath;
        }

        // Add contextual suggestions based on document structure
        if (documentStructure) {
          const contextSuggestions = getContextualSuggestions(
            documentStructure,
            currentPath.length > 0 ? currentPath : lastPathRef.current,
            providers || [],
            range,
            monaco.languages.CompletionItemKind,
            indentation
          );
          suggestions = [...suggestions, ...contextSuggestions];
        }

        return { suggestions };
      },
      triggerCharacters: ["-", " ", ":", "."],
    });
  };

  const handleEditorDidMount = (
    editor: editor.IStandaloneCodeEditor,
    monacoInstance: typeof import("monaco-editor")
  ) => {
    editorRef.current = editor;

    // Set up validation on content change
    editor.onDidChangeModelContent(() => {
      const content = editor.getValue();
      setCurrentContent(content);
      onChange?.(content);
    });

    setIsEditorMounted(true);
  };

  return (
    <div className="w-full h-full relative flex flex-col">
      <div
        className="w-full h-full relative flex-1 min-h-0"
        data-testid={dataTestId + "-container"}
      >
        <style jsx global>{`
          .validation-error {
            background-color: rgba(255, 0, 0, 0.1);
          }
          .squiggly-error {
            text-decoration: wavy underline rgb(255, 0, 0);
            text-decoration-skip-ink: none;
          }
        `}</style>
        <Editor
          height={height}
          defaultLanguage="yaml"
          value={value}
          beforeMount={beforeMount}
          onChange={(value) => {
            setCurrentContent(value || "");
            onChange?.(value || "");
          }}
          options={{
            readOnly,
            minimap: { enabled: false },
            lineNumbers: "on",
            scrollBeyondLastLine: false,
            wordWrap: "on",
            wrappingIndent: "indent",
            tabSize: 2,
            insertSpaces: true,
            formatOnPaste: true,
            formatOnType: true,
          }}
          onMount={handleEditorDidMount}
          data-testid={dataTestId}
        />
      </div>
      <div className="bg-slate-200 p-2 text-sm">
        <pre>{lastPath.join(".")}</pre>
      </div>
      <div className="bg-slate-100 p-2 text-sm h-14 overflow-y-auto">
        {validationResult?.errors?.length ? (
          <p className="text-red-500">
            {validationResult?.errors?.length} errors
          </p>
        ) : (
          <p className="text-gray-500">No errors</p>
        )}
        {validationResult?.errors?.map(({ path, message, line, col }) => {
          const isAction = path.join(".").startsWith("workflow.actions.");
          const isStep = path.join(".").startsWith("workflow.steps.");
          if (isAction) {
            const actionIndex = path[2];
            const actionName = parsedWorkflow?.actions?.[actionIndex]?.name;
            return (
              <div key={message}>
                {actionName}: {message} ({line}:{col})
              </div>
            );
          }
          if (isStep) {
            const stepIndex = path[2];
            const stepName = parsedWorkflow?.steps?.[stepIndex]?.name;
            return (
              <div key={message}>
                {stepName}: {message} ({line}:{col})
              </div>
            );
          }
          return (
            <div key={message}>
              {path.join(".")}: {message} ({line}:{col})
            </div>
          );
        })}
      </div>
    </div>
  );
};

export function getCurrentPath(document: Document, absolutePosition: number) {
  let path: string[] = [];
  if (!document.contents) return [];

  visit(document, {
    Scalar(key, node, ancestors) {
      if (!node.range) return;
      if (
        absolutePosition >= node.range[0] &&
        absolutePosition <= node.range[2]
      ) {
        // Create a new array to store path components
        ancestors.forEach((ancestor, index) => {
          if (isPair(ancestor)) {
            path.push(ancestor.key.value as string);
          } else if (isSeq(ancestor)) {
            // If ancestor is a Sequence, we need to find the index of the child item
            const childNode = ancestors[index + 1]; // Get the child node
            const seqIndex = ancestor.items.findIndex(
              (item) => item === childNode
            );
            if (seqIndex !== -1) {
              path.push(String(seqIndex));
            }
          }
        });
        // Path should be reversed as we're traversing from the node up to the root
        return visit.BREAK;
      }
    },
  });

  return path;
}

function getValueByPath(obj: any, path: string[]) {
  return path.reduce((acc, key) => acc && acc[key], obj);
}

// Helper function to get contextual suggestions based on document structure
const getContextualSuggestions = (
  document: any,
  currentPath: string[],
  providers: Provider[],
  range: IRange,
  completionItemKind: typeof languages.CompletionItemKind,
  indentation: string
): languages.CompletionItem[] => {
  const suggestions: languages.CompletionItem[] = [];

  // Add suggestions based on the current context
  if (currentPath.includes("provider") && currentPath.slice(-1)[0] === "type") {
    // Add provider-specific suggestions
    providers.forEach((provider) => {
      suggestions.push({
        label: provider.type,
        kind: completionItemKind.Value,
        documentation: { value: `Provider: ${provider.type}` },
        insertText: provider.type,
        range,
      });
    });
  }

  if (currentPath.includes("provider") && currentPath.slice(-1)[0] === "with") {
    // Add suggestions based on the provider type
    // TODO: get provider type from document
    const json = document.toJSON();
    const providerObject = getValueByPath(json, currentPath.slice(0, -1));
    const providerType = providerObject?.type;
    const provider = providers.find((p) => p.type === providerType);
    if (provider) {
      provider.query_params?.forEach((param) => {
        suggestions.push({
          label: param,
          kind: completionItemKind.Value,
          documentation: { value: `Provider: ${provider.type}` },
          insertText: `\n  ${param}: `,
          range,
        });
      });
      provider.notify_params?.forEach((param) => {
        suggestions.push({
          label: param,
          kind: completionItemKind.Value,
          documentation: { value: `Provider: ${provider.type}` },
          insertText: `\n  ${param}: `,
          range,
        });
      });
    }
  }

  if (currentPath.slice(-1)[0] === "steps") {
    suggestions.push({
      label: "step-template",
      kind: completionItemKind.Snippet,
      documentation: { value: "Insert a complete step template" },
      insertText: [
        "\n- name: step_name",
        `${indentation}provider:`,
        `${indentation}  type: `,
        `${indentation}  with:`,
        `${indentation}    `,
      ].join("\n"),
      range,
    });
  }

  if (currentPath.slice(-1)[0] === "actions") {
    suggestions.push({
      label: "action-template",
      kind: completionItemKind.Snippet,
      documentation: { value: "Insert a complete action template" },
      insertText: [
        "\n- name: action_name",
        `${indentation}provider:`,
        `${indentation}  type: `,
        `${indentation}  with:`,
        `${indentation}    `,
      ].join("\n"),
      range,
    });
  }

  if (currentPath.slice(-1)[0] === "workflow") {
    workflowFields.forEach((field) => {
      suggestions.push({
        label: field.label,
        kind: completionItemKind.Field,
        documentation: { value: field.documentation },
        insertText: `${field.label}: `,
        range,
      });
    });
  }

  return suggestions;
};

const MonacoEditorWithValidation = (props: Props) => {
  const {
    data: { providers, installed_providers: installedProviders } = {},
    isLoading,
  } = useProviders();

  if (!providers || !providers.length) {
    return <div>No providers found</div>;
  }

  if (isLoading) {
    return <div>Loading providers...</div>;
  }

  return (
    <_MonacoEditorWithValidation
      {...props}
      providers={providers}
      installedProviders={installedProviders ?? []}
    />
  );
};

export default MonacoEditorWithValidation;
