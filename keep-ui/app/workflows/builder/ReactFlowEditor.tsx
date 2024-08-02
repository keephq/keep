import { useState, useEffect } from "react";
import { IoMdSettings, IoMdClose } from "react-icons/io";
import useStore from "./builder-store";
import { GlobalEditorV2, StepEditorV2 } from "./editors";
import { Button } from "@tremor/react";

const ReactFlowEditor = () => {
  const { openGlobalEditor, selectedNode, stepEditorOpenForNode } = useStore();
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    if (stepEditorOpenForNode) {
      setIsOpen(stepEditorOpenForNode === selectedNode?.id);
    }
  }, [stepEditorOpenForNode, selectedNode?.id]);

  return (
    <div
      className={`absolute top-0 right-0 bg-white transition-transform duration-300 z-50${
        isOpen ? " h-full" : "h-14"
      }`}
    >
      {!isOpen && (
        <button
          className="flex justify-center items-center w-10 h-14 border rounded-bl-lg shadow-md"
          onClick={() => setIsOpen(true)}
        >
          <IoMdSettings className="text-2xl" />
        </button>
      )}
      {isOpen && (
        <div className="flex gap-0.5 h-full">
          <button
            className="flex justify-center items-center w-10 h-14 border rounded-bl-lg shadow-md"
            onClick={() => setIsOpen(false)}
          >
            <IoMdClose className="text-2xl" />
          </button>
          <div className="flex-1 p-2 border-2 overflow-y-auto">
            <div style={{ width: "300px" }}>
              {openGlobalEditor && <GlobalEditorV2 />}
              {!openGlobalEditor && selectedNode && <StepEditorV2 />}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ReactFlowEditor;
