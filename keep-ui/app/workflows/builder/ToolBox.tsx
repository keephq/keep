// ToolBox.tsx
import React from 'react';
import { useDrag } from 'react-dnd';
// import { ItemType } from './constants'; // Define item types

interface ToolBoxItemProps {
  id: string;
  name: string;
  type: string;
}

const ToolBoxItem: React.FC<ToolBoxItemProps> = ({ id, name, type }) => {
  const [{ isDragging }, drag] = useDrag(() => ({
    type: 'input',
    item: { id, type, name },
    collect: (monitor) => ({
      isDragging: monitor.isDragging(),
    }),
  }));

  return (
    <div
      ref={drag}
      style={{
        padding: 10,
        border: '1px solid black',
        borderRadius: 5,
        marginBottom: 5,
        opacity: isDragging ? 0.5 : 1,
        cursor: 'move',
      }}
    >
      {name}
    </div>
  );
};

const ToolBox: React.FC = ({ toolboxConfiguration }: { toolboxConfiguration: { groups: Record<string, any> } }) => {
  const { groups } = toolboxConfiguration;

  return (
    <div style={{ padding: 10, border: '1px solid black', borderRadius: 5, width: 250 }}>
      {groups.map((group) => (
        <div key={group.name}>
          <h4>{group.name}</h4>
          {group.steps.map((step) => (
            <ToolBoxItem key={step.id} id={step.id} name={step.name} type={step.type} />
          ))}
        </div>
      ))}
    </div>
  );
};

export default ToolBox;
