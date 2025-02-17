"use client";

import { AlertDto } from "@/entities/alerts/model";
import Modal from "@/components/ui/Modal";
import { Button, Switch, Text } from "@tremor/react";
import { toast } from "react-toastify";
import "./ViewAlertModal.css";
import React, { useState, useRef, useEffect } from "react";
import { useApi } from "@/shared/lib/hooks/useApi";
import { showErrorToast } from "@/shared/ui";
import dynamic from "next/dynamic";
import { Monaco } from "@monaco-editor/react";
import * as monaco from "monaco-editor";

// Dynamically import the Editor component with no SSR
const Editor = dynamic(() => import("@monaco-editor/react"), { ssr: false });

interface ViewAlertModalProps {
  alert: AlertDto | null | undefined;
  handleClose: () => void;
  mutate: () => void;
}

export const ViewAlertModal: React.FC<ViewAlertModalProps> = ({
  alert,
  handleClose,
  mutate,
}) => {
  const isOpen = !!alert;
  const [showHighlightedOnly, setShowHighlightedOnly] = useState(false);
  const api = useApi();
  const editorRef = useRef<monaco.editor.IStandaloneCodeEditor | null>(null);
  const decorationsRef = useRef<string[]>([]);

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

  const handleEditorDidMount = (
    editor: monaco.editor.IStandaloneCodeEditor,
    monacoInstance: Monaco
  ) => {
    editorRef.current = editor;

    // Add click handler
    editor.onMouseDown((e) => {
      if (!alert?.enriched_fields) return;

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

    // Listen for content changes and update decorations
    editor.onDidChangeModelContent(() => {
      updateDecorations(editor);
    });

    updateDecorations(editor);
  };

  // Update decorations whenever showHighlightedOnly changes
  useEffect(() => {
    if (editorRef.current) {
      updateDecorations(editorRef.current);
    }
  }, [showHighlightedOnly]);

  const updateDecorations = (editor: monaco.editor.IStandaloneCodeEditor) => {
    if (!alert?.enriched_fields || !editor) return;

    const model = editor.getModel();
    if (!model) return;

    const decorations: monaco.editor.IModelDeltaDecoration[] = [];

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

      matches.forEach((match) => {
        decorations.push({
          range: match.range,
          options: {
            inlineClassName: "enriched-field",
            hoverMessage: { value: "Click to un-enrich" },
            stickiness:
              monaco.editor.TrackedRangeStickiness.NeverGrowsWhenTypingAtEdges,
          },
        });
      });
    });

    decorationsRef.current = editor.deltaDecorations(
      decorationsRef.current,
      decorations
    );
  };

  const editorOptions: monaco.editor.IStandaloneEditorConstructionOptions = {
    readOnly: true,
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
        await navigator.clipboard.writeText(JSON.stringify(alert, null, 2));
        toast.success("Alert copied to clipboard!");
      } catch (err) {
        showErrorToast(err, "Failed to copy alert.");
      }
    }
  };

  return (
    <Modal
      onClose={handleClose}
      isOpen={isOpen}
      className="overflow-visible max-w-[800px]"
    >
      <div className="flex justify-between items-center mb-4 min-w-full">
        <h2 className="text-lg font-semibold">Alert Details</h2>
        <div className="flex gap-x-2">
          <div className="placeholder-resizing min-w-48"></div>
          <div className="flex items-center space-x-2">
            <Switch
              color="orange"
              id="showHighlightedOnly"
              checked={showHighlightedOnly}
              onChange={() => setShowHighlightedOnly(!showHighlightedOnly)}
            />
            <label
              htmlFor="showHighlightedOnly"
              className="text-sm text-gray-500"
            >
              <Text>Enriched Fields Only</Text>
            </label>
          </div>
          <Button onClick={handleCopy} color="orange">
            Copy to Clipboard
          </Button>
          <Button onClick={handleClose} color="orange" variant="secondary">
            Close
          </Button>
        </div>
      </div>
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
            `}</style>
            <Editor
              height="100%"
              defaultLanguage="json"
              value={
                showHighlightedOnly
                  ? JSON.stringify(
                      Object.fromEntries(
                        alert.enriched_fields.map((key) => [
                          key,
                          alert[key as keyof typeof alert],
                        ])
                      ),
                      null,
                      2
                    )
                  : JSON.stringify(
                      Object.fromEntries(
                        Object.entries(alert).filter(
                          ([key]) => key !== "enriched_fields"
                        )
                      ),
                      null,
                      2
                    )
              }
              options={editorOptions}
              onMount={handleEditorDidMount}
              theme="vs-light"
            />
          </>
        )}
      </div>
    </Modal>
  );
};
