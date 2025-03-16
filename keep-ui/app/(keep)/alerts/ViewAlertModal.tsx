import { AlertDto, Status, Severity } from "@/entities/alerts/model"; // Adjust the import path as needed
import Modal from "@/components/ui/Modal"; // Ensure this path matches your project structure
import { Button, Subtitle, Switch, Text, Callout } from "@tremor/react";
import { toast } from "react-toastify";
import "./ViewAlertModal.css";
import React, { useState, useRef, useEffect } from "react";
import { useApi } from "@/shared/lib/hooks/useApi";
import { showErrorToast } from "@/shared/ui";
import Editor, { Monaco } from "@monaco-editor/react";
import { Lock, Unlock, Save, AlertTriangle, Copy, X } from "lucide-react";

// Monaco Editor - do not load from CDN (to support on-prem)
// https://github.com/suren-atoyan/monaco-react?tab=readme-ov-file#use-monaco-editor-as-an-npm-package
import * as monaco from "monaco-editor";
import { loader } from "@monaco-editor/react";
loader.config({ monaco });

import * as monacoEditor from "monaco-editor/esm/vs/editor/editor.api";

interface ViewAlertModalProps {
  alert: AlertDto | null | undefined;
  handleClose: () => void;
  mutate: () => void;
}

// Fields that shouldn't be editable
const READ_ONLY_FIELDS = [
  "id",
  "lastReceived",
  "isFullDuplicate",
  "isPartialDuplicate",
  "duplicateReason",
  "source",
  "fingerprint",
  "event_id",
  "firingStartTime",
  "apiKeyRef",
  "providerId",
  "providerType",
  "startedAt",
  "incident",
  "incident_id",
  "alert_hash",
];

// Fields with enum values
const ENUM_FIELDS: Record<string, string[]> = {
  status: Object.values(Status),
  severity: Object.values(Severity),
};

// Validation interface
interface ValidationError {
  message: string;
  field?: string;
  type: "read-only" | "enum" | "syntax" | "general";
}

export const ViewAlertModal: React.FC<ViewAlertModalProps> = ({
  alert,
  handleClose,
  mutate,
}) => {
  const isOpen = !!alert;
  const [showHighlightedOnly, setShowHighlightedOnly] = useState(false);
  const [isEditable, setIsEditable] = useState(false);
  const [editorValue, setEditorValue] = useState("");
  const [originalValue, setOriginalValue] = useState("");
  const [hasChanges, setHasChanges] = useState(false);
  const [validationErrors, setValidationErrors] = useState<ValidationError[]>(
    []
  );
  const api = useApi();
  const editorRef = useRef<any>(null);
  const monacoRef = useRef<typeof monacoEditor | null>(null);
  const decorationsRef = useRef<string[]>([]);

  // Initialize editor value when alert changes
  useEffect(() => {
    if (alert) {
      const alertData: Record<string, any> = { ...alert };

      // Convert Date objects to string for proper JSON display
      Object.keys(alertData).forEach((key) => {
        if (alertData[key] instanceof Date) {
          alertData[key] = alertData[key].toISOString();
        }
      });

      const displayValue = showHighlightedOnly
        ? JSON.stringify(
            Object.fromEntries(
              alert.enriched_fields.map((key) => [
                key,
                alertData[key as keyof typeof alertData],
              ])
            ),
            null,
            2
          )
        : JSON.stringify(
            Object.fromEntries(
              Object.entries(alertData).filter(
                ([key]) => key !== "enriched_fields"
              )
            ),
            null,
            2
          );

      setEditorValue(displayValue);
      setOriginalValue(displayValue);
      setHasChanges(false);
      setValidationErrors([]);
    }
  }, [alert, showHighlightedOnly]);

  // Validate JSON content and return array of validation errors
  const validateJson = (
    jsonContent: string,
    originalJson: any = null
  ): ValidationError[] => {
    const errors: ValidationError[] = [];
    let parsedJson: any = null;

    // First check for syntax errors
    try {
      parsedJson = JSON.parse(jsonContent);
    } catch (err) {
      // JSON syntax error
      errors.push({
        message: (err as Error).message,
        type: "syntax",
      });

      // If there's a syntax error, we still want to continue with enum validation
      // on the last valid JSON if possible
    }

    // If we couldn't parse JSON, there's no point in continuing with other validations
    if (!parsedJson && errors.length > 0) {
      return errors;
    }

    // Use the successfully parsed JSON for further validation
    const jsonToValidate = parsedJson;

    // If we have original JSON to compare against, check for read-only field modifications
    if (originalJson) {
      for (const field of READ_ONLY_FIELDS) {
        if (
          jsonToValidate[field] !== undefined &&
          originalJson[field] !== undefined &&
          JSON.stringify(originalJson[field]) !==
            JSON.stringify(jsonToValidate[field])
        ) {
          errors.push({
            message: `Cannot modify read-only field: ${field}`,
            field,
            type: "read-only",
          });
        }
      }
    }

    // Validate enum fields
    for (const [field, allowedValues] of Object.entries(ENUM_FIELDS)) {
      if (
        jsonToValidate[field] &&
        !allowedValues.includes(jsonToValidate[field])
      ) {
        errors.push({
          message: `Invalid value for "${field}". Allowed values: ${allowedValues.join(
            ", "
          )}`,
          field,
          type: "enum",
        });
      }
    }

    return errors;
  };

  const unEnrichAlert = async (key: string) => {
    if (confirm(`Are you sure you want to un-enrich ${key}?`)) {
      try {
        const requestData = {
          enrichments: [key],
          fingerprint: alert!.fingerprint,
        };
        await api.post(`/alerts/unenrich`, requestData);
        toast.success(`${key} un-enriched successfully!`);
        await mutate();
      } catch (error) {
        showErrorToast(error, `Failed to unenrich ${key}`);
      }
    }
  };

  const setupMonacoCompletionProvider = (monaco: typeof monacoEditor) => {
    // Set up enum value suggestions
    monaco.languages.registerCompletionItemProvider("json", {
      triggerCharacters: ['"', ":", " ", ","],
      provideCompletionItems: (model, position, context, token) => {
        const lineText = model.getLineContent(position.lineNumber);
        const wordUntilPosition = model.getWordUntilPosition(position);
        const range = {
          startLineNumber: position.lineNumber,
          endLineNumber: position.lineNumber,
          startColumn: wordUntilPosition.startColumn,
          endColumn: wordUntilPosition.endColumn,
        };

        const colonPos = lineText.lastIndexOf(":", position.column);
        const cursorAfterColon = colonPos > 0 && position.column > colonPos;

        let suggestions: any[] = [];

        // If we're after a colon, suggest enum values
        if (cursorAfterColon) {
          // Find the key we're editing (look backwards from the colon)
          const lineUntilColon = lineText.substring(0, colonPos);
          const keyMatch = lineUntilColon.match(/"([^"]+)"\s*$/);

          if (keyMatch && keyMatch[1]) {
            const key = keyMatch[1];

            // Check if it's an enum field
            if (key in ENUM_FIELDS) {
              const values = ENUM_FIELDS[key];

              suggestions = values.map((value) => ({
                label: value,
                kind: monaco.languages.CompletionItemKind.EnumMember,
                insertText: `"${value}"`,
                documentation: { value: `Enum value for ${key}` },
                sortText: "0", // Prioritize these suggestions
                range: range,
              }));
            }
          }
        } else {
          // Key suggestions
          try {
            // Only suggest status and severity fields for autocomplete
            const suggestableKeys = Object.keys(ENUM_FIELDS);

            suggestions = suggestableKeys.map((key) => {
              const enumValues = ENUM_FIELDS[key].join(", ");

              return {
                label: key,
                kind: monaco.languages.CompletionItemKind.Property,
                insertText: `"${key}": ""`,
                documentation: {
                  value: `Property with predefined values: ${enumValues}`,
                },
                sortText: "0",
                range: range,
              };
            });
          } catch (e) {
            // If JSON is invalid, don't provide suggestions
          }
        }

        return { suggestions } as any;
      },
    });
  };

  const handleEditorDidMount = (editor: any, monaco: typeof monacoEditor) => {
    editorRef.current = editor;
    monacoRef.current = monaco;

    // Configure Monaco
    setupMonacoCompletionProvider(monaco);

    // Add custom tooltip for read-only mode
    if (!isEditable) {
      const editorDomNode = editor.getDomNode();
      if (editorDomNode) {
        editorDomNode.setAttribute("title", "Click the unlock button to edit");
      }
    }

    // Add click handler for un-enriching (only when not in edit mode)
    editor.onMouseDown((e: any) => {
      if (isEditable || !alert?.enriched_fields) return;

      const position = e.target.position;
      if (!position) return;

      const model = editor.getModel();
      if (!model) return;

      // Get the word at click position
      const word = model.getWordAtPosition(position);
      if (!word) return;

      // Get the line content
      const lineContent = model.getLineContent(position.lineNumber);

      // Check if the clicked word is a key in enriched_fields
      const clickedKey = alert.enriched_fields.find(
        (field) =>
          lineContent.includes(`"${field}"`) &&
          position.column >= lineContent.indexOf(`"${field}"`) &&
          position.column <=
            lineContent.indexOf(`"${field}"`) + field.length + 2
      );

      if (clickedKey) {
        unEnrichAlert(clickedKey);
      }
    });

    // Listen for content changes
    editor.onDidChangeModelContent(() => {
      const newValue = editor.getValue();
      setEditorValue(newValue);
      setHasChanges(newValue !== originalValue);

      // Run JSON validation
      let parsedOriginal;
      try {
        parsedOriginal = JSON.parse(originalValue);
      } catch {
        parsedOriginal = null;
      }

      const errors = validateJson(newValue, parsedOriginal);
      setValidationErrors(errors);

      // If editing a read-only field, restore it automatically
      const readOnlyFieldErrors = errors.filter((e) => e.type === "read-only");
      if (readOnlyFieldErrors.length > 0 && parsedOriginal) {
        try {
          const parsedNew = JSON.parse(newValue);
          const model = editor.getModel();

          // Apply fixes for read-only fields
          readOnlyFieldErrors.forEach((error) => {
            if (error.field) {
              // Restore the original value
              parsedNew[error.field] = parsedOriginal[error.field];
            }
          });

          // Update editor content with fixed JSON
          editor.executeEdits("", [
            {
              range: model.getFullModelRange(),
              text: JSON.stringify(parsedNew, null, 2),
            },
          ]);
        } catch {
          // If there's a syntax error, don't try to fix anything
        }
      }

      updateDecorations(editor);
    });

    updateDecorations(editor);

    // Setup the editor model
    if (editor && monaco) {
      applyReadOnlyDecorations(editor, monaco);
    }
  };

  // Update decorations when relevant states change
  useEffect(() => {
    if (editorRef.current) {
      updateDecorations(editorRef.current);
    }
  }, [showHighlightedOnly, isEditable]);

  const applyReadOnlyDecorations = (
    editor: any,
    monaco: typeof monacoEditor
  ) => {
    if (!editor || !monaco) return;

    const model = editor.getModel();
    if (!model) return;

    try {
      const parsedJson = JSON.parse(editor.getValue());
      const readOnlyDecorations: any[] = [];

      // For each read-only field, find its position and create a decoration
      READ_ONLY_FIELDS.forEach((field) => {
        // Skip if field doesn't exist in the current JSON
        if (!parsedJson.hasOwnProperty(field)) return;

        const fieldPattern = `"${field}"\\s*:`;
        const matches = model.findMatches(
          fieldPattern,
          true,
          true,
          false,
          null,
          true
        );

        matches.forEach((match: any) => {
          // Find the line number of the match
          const lineNumber = match.range.startLineNumber;
          // Get the whole line content
          const line = model.getLineContent(lineNumber);
          // Find where the value starts (after the colon and whitespace)
          const colonIndex = line.indexOf(":", match.range.startColumn);

          if (colonIndex > 0) {
            // Create a decoration for the entire line
            const lineLength = line.length;
            readOnlyDecorations.push({
              range: new monaco.Range(
                lineNumber,
                1,
                lineNumber,
                lineLength + 1
              ),
              options: {
                inlineClassName: "read-only-field",
                hoverMessage: { value: "This field cannot be edited" },
                stickiness:
                  monaco.editor.TrackedRangeStickiness
                    .NeverGrowsWhenTypingAtEdges,
              },
            });
          }
        });
      });

      // Apply the decorations
      editor.createDecorationsCollection(readOnlyDecorations);
    } catch (error) {
      // Silently fail if JSON is invalid
      console.error("Failed to apply read-only decorations:", error);
    }
  };

  const updateDecorations = (editor: any) => {
    if (!alert?.enriched_fields || !editor || isEditable) {
      // Clear decorations when in edit mode
      decorationsRef.current = editor.deltaDecorations(
        decorationsRef.current,
        []
      );
      return;
    }

    const model = editor.getModel();
    if (!model) return;

    const decorations: any[] = [];

    // For each enriched field, find its position and create a decoration
    alert.enriched_fields.forEach((field) => {
      const matches = model.findMatches(
        `"${field}"`,
        false,
        false,
        true,
        null,
        true
      );

      matches.forEach((match: any) => {
        decorations.push({
          range: match.range,
          options: {
            inlineClassName: "enriched-field",
            hoverMessage: { value: "Click to un-enrich" },
            stickiness: 1,
          },
        });
      });
    });

    decorationsRef.current = editor.deltaDecorations(
      decorationsRef.current,
      decorations
    );
  };

  const toggleEditMode = () => {
    if (isEditable) {
      // Switching from edit mode to view mode
      setIsEditable(false);

      // Reset any validation errors
      setValidationErrors([]);

      // If there were unsaved changes, ask for confirmation
      if (hasChanges) {
        if (
          confirm(
            "You have unsaved changes. Are you sure you want to discard them?"
          )
        ) {
          setEditorValue(originalValue);
          setHasChanges(false);
        } else {
          setIsEditable(true); // Stay in edit mode if user cancels
          return;
        }
      }
    } else {
      // Switching from view mode to edit mode
      setIsEditable(true);
    }
  };

  // Updated saveChanges method to use the enrichment API
  const saveChanges = async () => {
    if (!alert || !hasChanges) return;

    try {
      // Parse the current and original JSON
      const currentJson = JSON.parse(editorValue);
      const originalJson = JSON.parse(originalValue);

      // Run final validation before saving
      const errors = validateJson(editorValue, originalJson);
      if (errors.length > 0) {
        setValidationErrors(errors);
        return;
      }

      // Calculate which fields to enrich
      const enrichments: Record<string, any> = {};

      // Track keys that need to be un-enriched (removed)
      const keysToUnenrich: string[] = [];

      // Find keys that were in original but not in current JSON (to un-enrich)
      Object.keys(originalJson).forEach((key) => {
        // Skip read-only fields
        if (READ_ONLY_FIELDS.includes(key)) return;

        // If key existed in original but not in current version
        if (
          !currentJson.hasOwnProperty(key) &&
          originalJson.hasOwnProperty(key)
        ) {
          // Only add to unenrich if it was an enriched field
          if (alert?.enriched_fields?.includes(key)) {
            keysToUnenrich.push(key);
          }
        }
      });

      // Find keys that are new or changed
      Object.keys(currentJson).forEach((key) => {
        // Skip read-only fields
        if (READ_ONLY_FIELDS.includes(key)) return;

        // If key is new or value changed
        if (
          !originalJson.hasOwnProperty(key) ||
          JSON.stringify(currentJson[key]) !== JSON.stringify(originalJson[key])
        ) {
          enrichments[key] = currentJson[key];
        }
      });

      // Handle un-enrichments first if there are any
      if (keysToUnenrich.length > 0) {
        await api.post("/alerts/unenrich", {
          fingerprint: alert.fingerprint,
          enrichments: keysToUnenrich,
        });
      }

      // Handle enrichments if there are any
      if (Object.keys(enrichments).length > 0) {
        await api.post("/alerts/enrich", {
          fingerprint: alert.fingerprint,
          enrichments: enrichments,
        });
      }

      toast.success("Alert updated successfully!");

      // Update local state
      setOriginalValue(editorValue);
      setHasChanges(false);

      // Refresh the data
      await mutate();
    } catch (error) {
      showErrorToast(error, "Failed to update alert");
    }
  };

  const editorOptions: any = {
    readOnly: !isEditable,
    minimap: { enabled: false },
    lineNumbers: "on",
    scrollBeyondLastLine: false,
    automaticLayout: true,
    tabSize: 2,
    fontSize: 14,
    renderWhitespace: "all",
    wordWrap: "on",
    wordWrapColumn: 80,
    wrappingIndent: "indent",
    contextmenu: false,
  };

  const handleCopy = async () => {
    if (alert) {
      try {
        await navigator.clipboard.writeText(editorValue);
        toast.success("Alert copied to clipboard!");
      } catch (err) {
        showErrorToast(err, "Failed to copy alert.");
      }
    }
  };

  // Format validation errors for display with grouping by type
  const getErrorMessage = () => {
    if (validationErrors.length === 0) return null;

    // Group errors by type for better organization
    const syntaxErrors = validationErrors.filter((e) => e.type === "syntax");
    const readOnlyErrors = validationErrors.filter(
      (e) => e.type === "read-only"
    );
    const enumErrors = validationErrors.filter((e) => e.type === "enum");
    const generalErrors = validationErrors.filter((e) => e.type === "general");

    return (
      <>
        {syntaxErrors.map((error, index) => (
          <div key={`syntax-${index}`}>{error.message}</div>
        ))}

        {enumErrors.map((error, index) => (
          <div key={`enum-${index}`}>{error.message}</div>
        ))}

        {readOnlyErrors.map((error, index) => (
          <div key={`readonly-${index}`}>{error.message}</div>
        ))}

        {generalErrors.map((error, index) => (
          <div key={`general-${index}`}>{error.message}</div>
        ))}
      </>
    );
  };

  return (
    <Modal
      onClose={handleClose}
      isOpen={isOpen}
      className="overflow-visible max-w-[800px]"
    >
      <div className="flex justify-between items-center mb-4 min-w-full">
        <div className="flex flex-col flex-1">
          <Text className="text-sm text-gray-500">{alert?.name}</Text>
          <div className="flex items-center">
            <h2 className="text-lg font-semibold mr-2">Alert Payload</h2>
            <Button
              onClick={toggleEditMode}
              color="orange"
              variant="light"
              size="xs"
              icon={isEditable ? Unlock : Lock}
              className="p-1"
            ></Button>
          </div>
        </div>
        <div className="flex gap-x-2">
          <div className="flex items-center space-x-2 pr-2">
            <Switch
              color="orange"
              id="showHighlightedOnly"
              checked={showHighlightedOnly}
              onChange={() => setShowHighlightedOnly(!showHighlightedOnly)}
            />
            <label
              htmlFor="showHighlightedOnly"
              className={`text-sm ${
                isEditable ? "text-gray-400" : "text-gray-500"
              }`}
            >
              <Text>Enriched Fields Only</Text>
            </label>
          </div>
          <Button
            onClick={saveChanges}
            color="orange"
            icon={Save}
            disabled={!hasChanges || validationErrors.length > 0}
            title={!hasChanges ? "No changes in the alert payload" : ""}
          ></Button>
          <Button
            onClick={handleCopy}
            color="orange"
            variant="secondary"
            icon={Copy}
          ></Button>
          <Button
            onClick={handleClose}
            color="orange"
            variant="secondary"
            icon={X}
          ></Button>
        </div>
      </div>

      {isEditable && (
        <Callout
          className="mb-4"
          title="Edit with caution"
          color="orange"
          icon={AlertTriangle}
        >
          Keep in mind that some of the fields are used in ways that editing may
          break them.
          <br />
          <br />
          Any changes in the following fields will be ignored:
          <br />
          {READ_ONLY_FIELDS.map((field, index) => (
            <span key={field}>
              {index > 0 && ", "}
              <strong>{field}</strong>
            </span>
          ))}
        </Callout>
      )}

      <div className="h-[600px]">
        {alert && (
          <>
            <style jsx global>{`
              .enriched-field {
                background-color: rgba(34, 197, 94, 0.2);
                cursor: pointer;
              }
              .enriched-field:hover {
                background-color: rgba(34, 197, 94, 0.4);
              }
              .read-only-field {
                background-color: rgba(229, 231, 235, 0.5);
                cursor: not-allowed;
              }
            `}</style>
            <div className="relative h-full">
              {validationErrors.length > 0 && (
                <div className="sticky top-0 left-0 right-0 bg-red-100 text-red-800 p-2 text-sm z-10">
                  {getErrorMessage()}
                </div>
              )}
              <Editor
                height="100%"
                defaultLanguage="json"
                value={editorValue}
                options={editorOptions}
                onMount={handleEditorDidMount}
                onChange={(value) => setEditorValue(value || "")}
                theme="vs-light"
              />
            </div>
          </>
        )}
      </div>
    </Modal>
  );
};
