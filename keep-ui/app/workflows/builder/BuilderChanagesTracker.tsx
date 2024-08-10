import React, { useEffect, useRef, useState } from 'react'
import useStore, { FlowNode } from './builder-store';
import { Button } from '@tremor/react';
import { Edge } from '@xyflow/react';
import { reConstructWorklowToDefinition } from 'utils/reactFlow';

export default function BuilderChanagesTracker({onDefinitionChange}:{onDefinitionChange:(def: WrappedDefinition<Definition>) => void}) {
    const {nodes, edges,setEdges, setNodes, isLayouted, setIsLayouted, v2Properties} = useStore();
    const [changes, setChanges] = useState(0);
    const [savedChanges, setSavedChanges] = useState(0);
    const [lastSavedChanges, setLastSavedChanges] = useState<{nodes:FlowNode[], edges:Edge[]}>({nodes: nodes, edges: edges});
    const [firstInitilisationDone, setFirstInitilisationDone] = useState(false);

    console.log("isLayouted", isLayouted);

    useEffect(()=>{
        if(isLayouted && firstInitilisationDone) {
            setChanges((prev)=>prev+1);
        }
        if(isLayouted && !firstInitilisationDone) {
          setFirstInitilisationDone(true);
          setChanges(0);
          setLastSavedChanges({nodes: nodes, edges: edges});
        }
    },[isLayouted])



   const handleDiscardChanges = (e: React.MouseEvent<HTMLButtonElement>) => {
    if(!isLayouted) return;
    setEdges(lastSavedChanges.edges || []);
    setNodes(lastSavedChanges.nodes || []);
    setChanges(0);
    setIsLayouted(false);
   } 

   const handleSaveChanges = (e: React.MouseEvent<HTMLButtonElement>) =>{
    e.preventDefault();
    e.stopPropagation();
    setChanges(0);
    setSavedChanges((prev)=>(prev+1 || 0));
    setLastSavedChanges({nodes: nodes, edges: edges});
    const value = reConstructWorklowToDefinition({nodes: nodes, edges: edges, properties: v2Properties});
    onDefinitionChange(value);
   }




  return (
    <div className='flex gap-2.5'>
      <Button
       onClick={handleDiscardChanges}
       disabled={changes === 0 || !isLayouted}
       >Discard{changes ? `(${changes})`: ""}</Button>
      <Button
       onClick={handleSaveChanges}
       disabled={!isLayouted || changes === 0}
       >Save{savedChanges ? `(${savedChanges})`: ""}</Button>
    </div>
  )
}
