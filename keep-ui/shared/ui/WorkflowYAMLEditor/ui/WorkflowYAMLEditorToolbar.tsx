import { Check, Copy, Download } from "lucide-react";
import { Button } from "@tremor/react";
import { useState } from "react";
import clsx from "clsx";

export interface WorkflowYAMLEditorToolbarProps {
  onCopy: () => Promise<void>;
  onDownload: () => void;
  onSave?: () => void;
  isEditorMounted: boolean;
  readOnly?: boolean;
  className?: string;
}

export function WorkflowYAMLEditorToolbar({
  onCopy,
  onDownload,
  onSave,
  isEditorMounted,
  readOnly = false,
  className,
}: WorkflowYAMLEditorToolbarProps) {
  const [isCopied, setIsCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await onCopy();
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy text:", err);
    }
  };

  return (
    <div className={clsx("absolute top-2 right-6 z-10 flex gap-2", className)}>
      <Button
        color="orange"
        size="sm"
        className="h-8 px-2 bg-white"
        onClick={handleCopy}
        variant="secondary"
        data-testid="copy-yaml-button"
        disabled={!isEditorMounted}
      >
        {isCopied ? (
          <Check className="h-4 w-4" />
        ) : (
          <Copy className="h-4 w-4" />
        )}
      </Button>
      <Button
        color="orange"
        size="sm"
        className="h-8 px-2 bg-white"
        onClick={onDownload}
        variant="secondary"
        data-testid="download-yaml-button"
        disabled={!isEditorMounted}
      >
        <Download className="h-4 w-4" />
      </Button>
      {!readOnly && onSave ? (
        <Button
          color="orange"
          size="sm"
          className="h-8 px-2"
          onClick={onSave}
          variant="primary"
          data-testid="save-yaml-button"
        >
          Save
        </Button>
      ) : null}
    </div>
  );
}
