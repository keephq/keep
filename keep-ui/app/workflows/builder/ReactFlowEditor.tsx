import { useState, useEffect, useRef } from "react";
import { IoMdSettings, IoMdClose } from "react-icons/io";
import useStore from "./builder-store";
import { GlobalEditorV2, StepEditorV2 } from "./editors";
import { Button, Divider } from "@tremor/react";
import { Provider } from "app/providers/providers";
import { reConstructWorklowToDefinition } from "utils/reactFlow";
import debounce from "lodash.debounce";

const ReactFlowEditor = ({
  providers,
  validatorConfiguration,
  onDefinitionChange
}:{
  providers:Provider[];
  validatorConfiguration: {
    step: (step: any, defnition?:any)=>boolean;
    root: (def: any) => boolean;
  };
  onDefinitionChange: (def: any) => void
}) => {
  const { selectedNode, changes, v2Properties, nodes, edges } = useStore();
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

  useEffect(() => {
    const handleDefinitionChange = () => {
      if (changes > 0) {
        let { sequence, properties } =
          reConstructWorklowToDefinition({
            nodes: nodes,
            edges: edges,
            properties: v2Properties,
          }) || {};
        sequence = sequence || [];
        properties = properties || {};
        console.log("sequence", sequence, "properties", properties);
  
        let isValid = true;
        for (let step of sequence) {
          isValid = validatorConfiguration?.step(step);
          if (!isValid) {
            break;
          }
        }
  
        if (!isValid) {
          return onDefinitionChange({ sequence, properties, isValid });
        }
  
        isValid = validatorConfiguration.root({ sequence, properties });
        onDefinitionChange({ sequence, properties, isValid });
      }
    };
  
    const debouncedHandleDefinitionChange = debounce(handleDefinitionChange, 300);
  
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
          <div className="flex-1 p-2 bg-white border-2 overflow-y-auto">
            <div style={{ width: "300px" }}>
              <GlobalEditorV2 />
              {!selectedNode?.includes('empty') && <Divider ref={stepEditorRef}/>}
              {!selectedNode?.includes('empty') && <StepEditorV2 installedProviders={providers}/>}  
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ReactFlowEditor;

