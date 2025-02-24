import { useEffect, useRef, useMemo } from "react";
import { useWorkflowStore } from "@/entities/workflows";
import { StepEditorV2 } from "./StepEditor";
import { Divider } from "@tremor/react";
import clsx from "clsx";
import { ChevronRightIcon, Cog8ToothIcon } from "@heroicons/react/24/outline";
import { WorkflowToolbox } from "../WorkflowToolbox";
import { WorkflowEditorV2 } from "./WorkflowEditor";
import { TriggerEditor } from "./TriggerEditor";
import { WorkflowStatus } from "../workflow-status";
import { triggerTypes } from "../../lib/utils";

const ReactFlowEditor = () => {
  const { selectedNode, selectedEdge, setEditorOpen, getNodeById, editorOpen } =
    useWorkflowStore();
  const containerRef = useRef<HTMLDivElement>(null);
  const dividerRef = useRef<HTMLDivElement>(null);

  const isTrigger = triggerTypes.includes(selectedNode || "");
  const isStepEditor = !selectedNode?.includes("empty") && !isTrigger;

  useEffect(
    function scrollRelevantEditorIntoView() {
      if (!selectedNode && !selectedEdge) {
        return;
      }
      // Scroll the view to the divider into view when the editor is opened, so the relevant editor is visible
      const timer = setTimeout(() => {
        if (!containerRef.current || !dividerRef.current) {
          return;
        }
        const containerRect = containerRef.current.getBoundingClientRect();
        const dividerRect = dividerRef.current.getBoundingClientRect();
        // Check if the divider is already at the top of the container
        const isAtTop = dividerRect.top <= containerRect.top;

        if (isAtTop) {
          return;
        }
        // Scroll the divider into view
        dividerRef.current.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      }, 100);
      return () => clearTimeout(timer); // Cleanup the timer on unmount
    },
    [selectedNode, selectedEdge]
  );

  const initialFormData = useMemo(() => {
    if (!selectedNode) {
      return null;
    }
    const { data } = getNodeById(selectedNode) || {};
    const { name, type, properties } = data || {};
    return { name, type, properties };
  }, [selectedNode]);

  const showDivider = Boolean(selectedNode || selectedEdge);

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
        <div className="relative flex-1 flex flex-col bg-white border-l overflow-y-auto h-full w-80 2xl:w-96">
          <WorkflowStatus className="m-2 shrink-0" />
          <WorkflowEditorV2 />
          {showDivider && <Divider ref={dividerRef} className="my-2" />}
          {isTrigger && <TriggerEditor />}
          {isStepEditor && initialFormData && (
            <StepEditorV2
              key={selectedNode}
              initialFormData={initialFormData}
            />
          )}
          <WorkflowToolbox isDraggable={false} />
        </div>
      )}
    </div>
  );
};

export default ReactFlowEditor;
