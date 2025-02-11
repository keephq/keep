import { useState, useEffect, useRef } from "react";
import { IoMdSettings, IoMdClose } from "react-icons/io";
import { useStore } from "./builder-store";
import { GlobalEditorV2, StepEditorV2 } from "./editors";
import { Provider } from "@/app/(keep)/providers/providers";
import debounce from "lodash.debounce";
import {
  Definition,
  ReactFlowDefinition,
  V2Step,
} from "@/app/(keep)/workflows/builder/types";
import { getDefinitionFromNodesEdgesProperties } from "./utils";

const ReactFlowEditor = ({
  providers,
  installedProviders,
  validatorConfiguration,
  onDefinitionChange,
}: {
  providers: Provider[] | undefined | null;
  installedProviders: Provider[] | undefined | null;
  validatorConfiguration: {
    step: (
      step: V2Step,
      parent?: V2Step,
      defnition?: ReactFlowDefinition
    ) => boolean;
    root: (def: Definition) => boolean;
  };
  onDefinitionChange: (def: Definition) => void;
}) => {
  const {
    selectedNode,
    changes,
    setOpneGlobalEditor,
    synced,
    setSynced,
    setCanDeploy,
    nodes,
    edges,
    v2Properties,
  } = useStore();
  const [isOpen, setIsOpen] = useState(false);
  const stepEditorRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const isTrigger = ["interval", "manual", "alert", "incident"].includes(
    selectedNode || ""
  );
  const saveRef = useRef<boolean>(false);
  useEffect(() => {
    if (saveRef.current && synced) {
      setCanDeploy(true);
      saveRef.current = false;
    }
  }, [saveRef?.current, synced]);

  useEffect(() => {
    setIsOpen(true);
    if (selectedNode) {
      saveRef.current = false;
      const timer = setTimeout(() => {
        if (isTrigger) {
          setOpneGlobalEditor(true);
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

  useEffect(() => {
    setSynced(false);

    const handleDefinitionChange = () => {
      const newDefinition = getDefinitionFromNodesEdgesProperties(
        nodes,
        edges,
        v2Properties,
        validatorConfiguration
      );
      onDefinitionChange(newDefinition);
      setSynced(true);
    };
    const debouncedHandleDefinitionChange = debounce(
      handleDefinitionChange,
      300
    );

    debouncedHandleDefinitionChange();

    return () => {
      debouncedHandleDefinitionChange.cancel();
    };
  }, [changes]);

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
          <div className="flex-1 bg-white border-l-2 overflow-y-auto">
            <div style={{ width: "350px" }}>
              <GlobalEditorV2 saveRef={saveRef} />
              {!selectedNode?.includes("empty") && !isTrigger && (
                <div className="w-full h-px bg-gray-200" ref={stepEditorRef} />
              )}
              {!selectedNode?.includes("empty") && !isTrigger && (
                <StepEditorV2
                  providers={providers}
                  installedProviders={installedProviders}
                  saveRef={saveRef}
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
