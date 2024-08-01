// import { IoMdSettings, IoMdClose } from "react-icons/io";
// import useStore from "./builder-store";
// import { GlobalEditorV2, StepEditorV2 } from "./editors";
// import { useEffect, useState } from "react";


// const FlowEditor = ({ forceOpen }: { forceOpen?: boolean }) => {
//   const { openGlobalEditor, selectedNode } = useStore();
//   const [panelToggle, setPanelToggle] = useState(forceOpen || false);

//   console.log("panelToggle========>", panelToggle);
//   console.log("forceOpen in flow editor========>", forceOpen);


//   return (
//     <div
//       className={`absolute top-0 right-0 bg-white transition-transform duration-300 z-50 h-full`}
//     >
//       {!panelToggle && (
//         <button
//           className={`flex justify-center items-center w-10 h-14 border rounded-bl-lg shadow-md`}
//           onClick={() => setPanelToggle(true)}
//         >
//           <IoMdSettings className="text-2xl" />
//         </button>
//       )}
//       {panelToggle && (
//         <div className="flex gap-0.5 h-full">
//           <button
//             className={`flex justify-center items-center w-10 h-14 border rounded-bl-lg shadow-md`}
//             onClick={() => setPanelToggle(false)}
//           >
//             <IoMdClose className="text-2xl" />
//           </button>
//           <div
//             className={`flex-1 p-2 border-2 overflow-y-auto`}
//           >
//             <div style={{ width: "300px" }}>
//               {openGlobalEditor && <GlobalEditorV2 />}
//               {!openGlobalEditor && selectedNode && <StepEditorV2 />}
//             </div>
//           </div>
//         </div>
//       )}
//     </div>
//   );
// };

// export default function ReactFlowEditor() {
//   const { selectedNode, stepEditorOpenForNode } = useStore();
//   const [forceOpen, setForceOpen] = useState(false);

//   useEffect(() => {
//     if (selectedNode && selectedNode.id == stepEditorOpenForNode) {
//       setForceOpen(true);
//     } else {
//       setForceOpen(false);
//     }
//   }, [stepEditorOpenForNode, selectedNode]);

//   console.log("forceOpen===============>", forceOpen);
//   console.log("selectedNode===============>", selectedNode);
//   console.log("stepEditorOpenForNode===============>", stepEditorOpenForNode);
 


//   return (
//     <div className={`space-y-1 flex flex-col`}>
//        <FlowEditor forceOpen={forceOpen} />
//     </div>

//   );
// }



import { useState, useEffect } from 'react';
import { IoMdSettings, IoMdClose } from 'react-icons/io';
import useStore from './builder-store';
import { GlobalEditorV2, StepEditorV2 } from './editors';
import { Button } from '@tremor/react';

const ReactFlowEditor = () => {
  const { openGlobalEditor, selectedNode, stepEditorOpenForNode } = useStore();
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    setIsOpen(stepEditorOpenForNode === selectedNode?.id);
  }, [stepEditorOpenForNode, selectedNode]);

  return (
    <div className={`absolute top-0 right-0 bg-white transition-transform duration-300 z-50${isOpen ? ' h-full': 'h-14'}`}>
      {!isOpen && (
        <button
          className="flex justify-center items-center w-10 h-14 border rounded-bl-lg shadow-md"
          onClick={() => setIsOpen(true)}
          tooltip='Settings'
        >
          <IoMdSettings className="text-2xl" />
        </button>
      )}
      {isOpen && (
        <div className="flex gap-0.5 h-full">
          <button
            className="flex justify-center items-center w-10 h-14 border rounded-bl-lg shadow-md"
            onClick={() => setIsOpen(false)}
            tooltip='Close'
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
