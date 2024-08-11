import { useState, useEffect, useRef } from "react";
import { IoMdSettings, IoMdClose } from "react-icons/io";
import useStore from "./builder-store";
import { GlobalEditorV2, StepEditorV2 } from "./editors";
import { Button, Divider } from "@tremor/react";

const ReactFlowEditor = () => {
  const { selectedNode } = useStore();
  const [isOpen, setIsOpen] = useState(false);
  const stepEditorRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setIsOpen(true);
    if (selectedNode) {
      const timer = setTimeout(() => {
        if (containerRef.current && stepEditorRef.current) {
          const containerRect = containerRef.current.getBoundingClientRect();
          const stepEditorRect = stepEditorRef.current.getBoundingClientRect();
          // Check if StepEditorV2 is already at the top of the container
          const isAtTop = stepEditorRect.top <= containerRect.top;

          if (!isAtTop) {
            // Scroll the StepEditorV2 into view
            stepEditorRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
          }
        }
      }, 100);
      return () => clearTimeout(timer); // Cleanup the timer on unmount
    }
  }, [selectedNode]);

  return (
    <div
      className={`absolute top-0 right-0 transition-transform duration-300 z-50 ${
        isOpen ? "h-full" : "h-14"
      }`}
      ref={containerRef}
    >
      {!isOpen && (
        <button
          className="flex justify-center items-center w-10 bg-white h-14 border rounded-bl-lg shadow-md"
          onClick={() => setIsOpen(true)}
        >
          <IoMdSettings className="text-2xl" />
        </button>
      )}
      {isOpen && (
        <div className="flex gap-0.5 h-full">
          <button
            className="flex justify-center bg-white items-center w-10 h-14 border rounded-bl-lg shadow-md"
            onClick={() => setIsOpen(false)}
          >
            <IoMdClose className="text-2xl" />
          </button>
          <div className="flex-1 p-2 bg-white border-2 overflow-y-auto">
            <div style={{ width: "300px" }}>
              <GlobalEditorV2 />
              <Divider ref={stepEditorRef}/>
              <div>
                <StepEditorV2 />
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ReactFlowEditor;

