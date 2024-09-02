import { useState, useEffect, useRef } from "react";
import { IoMdSettings, IoMdClose } from "react-icons/io";
import useStore, { V2Properties, V2Step, ReactFlowDefinition, Definition } from "./builder-store";
import { GlobalEditorV2, StepEditorV2 } from "./editors";
import { Divider } from "@tremor/react";
import { Provider } from "app/providers/providers";
import { reConstructWorklowToDefinition } from "utils/reactFlow";
import debounce from "lodash.debounce";

const ReactFlowEditor = ({
  providers,
  validatorConfiguration,
  onDefinitionChange
}: {
  providers: Provider[] | undefined | null;
  validatorConfiguration: {
    step: (step: V2Step, parent?: V2Step, defnition?: ReactFlowDefinition) => boolean;
    root: (def: Definition) => boolean;
  };
  onDefinitionChange: (def: Definition) => void
}) => {
  const { selectedNode, changes, v2Properties, nodes, edges, setOpneGlobalEditor, synced, setSynced } = useStore();
  const [isOpen, setIsOpen] = useState(false);
  const stepEditorRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const isTrigger = ['interval', 'manual', 'alert'].includes(selectedNode || '')

  useEffect(() => {
    setIsOpen(true);
    if (selectedNode) {
      const timer = setTimeout(() => {
        if(isTrigger){
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
            stepEditorRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
          }
        }
      }, 100);
      return () => clearTimeout(timer); // Cleanup the timer on unmount
    }
  }, [selectedNode]);

  useEffect(() => {
    setSynced(false);

    const handleDefinitionChange = () => {
      if (changes > 0) {
        let { sequence, properties } =
          reConstructWorklowToDefinition({
            nodes: nodes,
            edges: edges,
            properties: v2Properties,
          }) || {};
        sequence = (sequence || []) as V2Step[];
        properties = (properties || {}) as V2Properties;
        let isValid = true;
        for (let step of sequence) {
          isValid = validatorConfiguration?.step(step);
          if (!isValid) {
            break;
          }
        }

        if (!isValid) {
           onDefinitionChange({ sequence, properties, isValid });
           setSynced(true);
           return;
        }

        isValid = validatorConfiguration.root({ sequence, properties });
        onDefinitionChange({ sequence, properties, isValid });
        setSynced(true);
      }
      setSynced(true);
    };

    const debouncedHandleDefinitionChange = debounce(handleDefinitionChange, 300);

    debouncedHandleDefinitionChange();

    return () => {
      debouncedHandleDefinitionChange.cancel();
    };
  }, [changes]);

  return (
    <div
      className={`absolute top-0 right-0 transition-transform duration-300 z-50 ${isOpen ? "h-full" : "h-14"
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
              <GlobalEditorV2 synced={synced}/>
              {!selectedNode?.includes('empty') && !isTrigger && <Divider ref={stepEditorRef} />}
              {!selectedNode?.includes('empty') && !isTrigger && <StepEditorV2 installedProviders={providers} setSynced={setSynced}/>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ReactFlowEditor;

