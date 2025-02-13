import { useEffect, useRef, useMemo } from "react";
import { useWorkflowStore } from "@/entities/workflows";
import { GlobalEditorV2, StepEditorV2 } from "./editors";
import { Divider } from "@tremor/react";
import { Provider } from "@/app/(keep)/providers/providers";
import clsx from "clsx";
import { ChevronRightIcon, Cog8ToothIcon } from "@heroicons/react/24/outline";
import { WorkflowToolbox } from "./WorkflowToolbox";

const ReactFlowEditor = ({
  providers,
  installedProviders,
}: {
  providers: Provider[] | undefined | null;
  installedProviders: Provider[] | undefined | null;
}) => {
  const { selectedNode, selectedEdge, setEditorOpen, getNodeById, editorOpen } =
    useWorkflowStore();
  const stepEditorRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const isTrigger = ["interval", "manual", "alert", "incident"].includes(
    selectedNode || ""
  );

  useEffect(() => {
    setEditorOpen(true);
    if (!selectedNode && !selectedEdge) {
      return;
    }
    // Scroll the StepEditorV2 into view when the editor is opened
    const timer = setTimeout(() => {
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
  }, [selectedNode, selectedEdge]);

  const initialFormData = useMemo(() => {
    if (!selectedNode) {
      return null;
    }
    const { data } = getNodeById(selectedNode) || {};
    const { name, type, properties } = data || {};
    return { name, type, properties };
  }, [selectedNode]);

  return (
    <div className="transition-transform relative z-50" ref={containerRef}>
      <div
        className={clsx(
          "absolute top-0 w-10 h-10",
          editorOpen ? "left-0 -translate-x-[calc(100%-3px)]" : "right-0"
        )}
      >
        {!editorOpen ? (
          <button
            className="flex justify-center items-center bg-white w-full h-full border-b border-l rounded-bl-lg shadow-md"
            onClick={() => setEditorOpen(true)}
            data-testid="wf-open-editor-button"
            title="Show step editor"
          >
            <Cog8ToothIcon className="size-5" />
          </button>
        ) : (
          <div className="flex gap-0.5 h-full">
            <button
              className="flex justify-center bg-white items-center w-full h-full border-b border-l rounded-bl-lg shadow-md"
              onClick={() => setEditorOpen(false)}
              data-testid="wf-close-editor-button"
              title="Hide step editor"
            >
              <ChevronRightIcon className="size-5" />
            </button>
          </div>
        )}
      </div>
      {editorOpen && (
        <div className="relative flex-1 bg-white border-l overflow-y-auto h-full">
          <div className="w-80 2xl:w-96">
            <GlobalEditorV2 />
            {!selectedNode?.includes("empty") && !isTrigger && (
              <Divider ref={stepEditorRef} className="my-2" />
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
            <WorkflowToolbox isDraggable={false} />
          </div>
        </div>
      )}
    </div>
  );
};

export default ReactFlowEditor;
