import React from "react";
import { ClipboardIcon } from "@heroicons/react/24/outline";
import DragAndDrop from "./dragndrop";

interface NoWorkflowsProps {
  copyCurlCommand: () => void;
}

const NoWorkflows: React.FC<NoWorkflowsProps> = ({ copyCurlCommand }) => {
  return (
    <div className="text-center mt-4">
      <p>No workflows available. </p>
      <p>1. Use the Workflow Builder</p>
      <p>2. Drop the Workflow file here:</p>
      <DragAndDrop/>
      <p>3. Use Keep API to push your YAML files:</p>
      <div className="relative w-1/2 mx-auto">
        <button
          className="absolute top-0 right-0 mt-1 mr-1 p-1 rounded hover:bg-gray-200"
          onClick={copyCurlCommand}
          title="Copy to Clipboard"
        >
          <ClipboardIcon className="h-5 w-5 text-gray-500" />
        </button>
        <pre className="bg-gray-100 p-2 rounded">
          <code className="whitespace-pre-wrap">
            {`curl -X POST ...\n...`}
          </code>
        </pre>
      </div>
    </div>
  );
};

export default NoWorkflows;
