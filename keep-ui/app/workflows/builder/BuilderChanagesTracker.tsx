import React, { useEffect, useRef, useState } from 'react'
import useStore, { FlowNode } from './builder-store';
import { Button } from '@tremor/react';
import { Edge } from '@xyflow/react';
import { reConstructWorklowToDefinition } from 'utils/reactFlow';

export default function BuilderChanagesTracker() {
    const {nodes, edges,setEdges, setNodes, isLayouted, setIsLayouted, v2Properties} = useStore();
    const [changes, setChanges] = useState(0);
    const [savedChanges, setSavedChanges] = useState(0);
    const [lastSavedChanges, setLastSavedChanges] = useState<{nodes:FlowNode[], edges:Edge[]}>({nodes: nodes, edges: edges});
    const [firstInitilisationDone, setFirstInitilisationDone] = useState(false);
    const [proprtiesUpdated, setPropertiesUpdated] = useState(false);

    console.log("isLayouted", isLayouted);

    useEffect(()=>{
        if(isLayouted && firstInitilisationDone) {
            setChanges((prev)=>prev+1);
        }
        if(isLayouted && !firstInitilisationDone) {
          setFirstInitilisationDone(true);
          setLastSavedChanges({nodes: nodes, edges: edges});
        }
    },[isLayouted])


    useEffect(()=>{
        reConstructWorklowToDefinition(lastSavedChanges);
    }, [lastSavedChanges])


   const handleDiscardChanges = (e: React.MouseEvent<HTMLButtonElement>) => {
    if(!isLayouted) return;
    setEdges(lastSavedChanges.edges || []);
    setNodes(lastSavedChanges.nodes || []);
    setChanges(0);
    setFirstInitilisationDone(false);
    setIsLayouted(false);
   } 

   const handleSaveChanges = (e: React.MouseEvent<HTMLButtonElement>) =>{
    e.preventDefault();
    e.stopPropagation();
    setSavedChanges((prev)=>(prev+1 || 0));
    setLastSavedChanges({nodes: nodes, edges: edges});
    setChanges(0);
    setPropertiesUpdated(false);
   }




  return (
    <div className='flex gap-2.5'>
      <Button
       onClick={handleDiscardChanges}
       disabled={changes === 0 || !isLayouted}
       >Discard{changes ? `(${changes})`: ""}</Button>
      <Button
       onClick={handleSaveChanges}
       disabled={proprtiesUpdated ? false : !isLayouted || changes === 0}
       >Save{savedChanges ? `(${savedChanges})`: ""}</Button>
    </div>
  )
}
