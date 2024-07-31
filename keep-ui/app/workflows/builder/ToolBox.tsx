import React from 'react';

const DragAndDropSidebar = () => {

  const handleDragStart = (event, nodeType) => {
    event.dataTransfer.setData('application/reactflow', nodeType);
    event.dataTransfer.effectAllowed = 'move';
  };

  return (
    <div
      className="sidebar"
    >
      <div className="description">
        You can drag these nodes to the pane on the right.
      </div>
      <div
        className="dndnode input"
        onDragStart={(event) => handleDragStart(event, 'custom')}
        draggable
      >
        Input Node
      </div>
      <div
        className="dndnode"
        onDragStart={(event) => handleDragStart(event, 'custom')}
        draggable
      >
        Default Node
      </div>
      <div
        className="dndnode output"
        onDragStart={(event) => handleDragStart(event, 'custom')}
        draggable
      >
        Output Node
      </div>
    </div>
  );
};

export default DragAndDropSidebar;
