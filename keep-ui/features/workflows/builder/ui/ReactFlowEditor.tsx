import { useState, useEffect, useRef, useMemo } from "react";
import { IoMdSettings, IoMdClose } from "react-icons/io";
import { useWorkflowStore } from "@/entities/workflows";
import { GlobalEditorV2, StepEditorV2 } from "./editors";
import { Divider } from "@tremor/react";
import { Provider } from "@/app/(keep)/providers/providers";

const ReactFlowEditor = ({
  providers,
  installedProviders,
}: {
  providers: Provider[] | undefined | null;
  installedProviders: Provider[] | undefined | null;
}) => {
  const { selectedNode, setGlobalEditorOpen, getNodeById } = useWorkflowStore();
  const [isOpen, setIsOpen] = useState(false);
  const stepEditorRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const isTrigger = ["interval", "manual", "alert", "incident"].includes(
    selectedNode || ""
  );

  useEffect(() => {
    setIsOpen(true);
    if (selectedNode) {
      const timer = setTimeout(() => {
        if (isTrigger) {
          setGlobalEditorOpen(true);
          return;
        }
        if (containerRef.current && stepEditorRef.current) {
          const containerRect = containerRef.current.getBoundingClientRect();
          const stepEditorRect = stepEditorRef.current.getBoundingClientRect();
          // Check if StepEditorV2 is already at the top of the container
          const isAtTop = stepEditorRect.top <= containerRect.top;

          if (!isAtTop) {
            // Scroll the StepEditorV2 into view
            stepEditorRef.current.scrollIntoView({
              behavior: "smooth",
              block: "start",
            });
          }
        }
      }, 100);
      return () => clearTimeout(timer); // Cleanup the timer on unmount
    }
  }, [selectedNode]);

  const initialFormData = useMemo(() => {
    if (!selectedNode) {
      return null;
    }
    const { data } = getNodeById(selectedNode) || {};
    const { name, type, properties } = data || {};
    return { name, type, properties };
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
            <div style={{ width: "350px" }}>
              <GlobalEditorV2 />
              {!selectedNode?.includes("empty") && !isTrigger && (
                <Divider ref={stepEditorRef} />
              )}
              {!selectedNode?.includes("empty") &&
                !isTrigger &&
                initialFormData && (
                  <StepEditorV2
                    key={selectedNode}
                    providers={providers}
                    installedProviders={installedProviders}
                    initialFormData={initialFormData}
                  />
                )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ReactFlowEditor;
