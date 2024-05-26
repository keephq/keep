import { CSSProperties, useState } from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import Link from 'next/link';
import { Icon, Badge } from "@tremor/react";
import { Trashcan } from "components/icons"; // Assuming you have a similar icon component
import classNames from 'classnames';

type GridLinkProps = {
  layout: any;  // Define a proper type based on your layout model
  pathname: string | null;
  deleteLayout: (id: string, name: string) => void;
};

export const GridLink = ({ layout, pathname, deleteLayout }: GridLinkProps) => {
  const [isHovered, setIsHovered] = useState(false);
  const href = `/layouts/${layout.name.toLowerCase()}`;
  const isActive = decodeURIComponent(pathname?.toLowerCase() || "") === href;

  const { listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({
      id: layout.id,
    });

  const dragStyle: CSSProperties = {
    opacity: isDragging ? 0.5 : 1,
    transform: CSS.Translate.toString(transform),
    transition,
    cursor: isDragging ? "grabbing" : "grab",
  };

  return (
    <li key={layout.id} ref={setNodeRef} style={dragStyle} {...listeners}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}>
      <span className={classNames("flex items-center space-x-2 text-sm p-1 text-slate-400 font-medium rounded-lg", {
            "bg-stone-200/50": isActive,
            "hover:text-orange-400 focus:ring focus:ring-orange-300 group hover:bg-stone-200/50": !isDragging,
          })}>
        <Link className={classNames("flex items-center flex-1", {
              "pointer-events-none cursor-auto": isDragging,
            })} href={href}>
          <span className={classNames("truncate max-w-[7.5rem]", {
              "text-orange-400": isActive,
            })} title={layout.name}>
            {layout.name}
          </span>
        </Link>
        <div className="flex items-center justify-end flex-1">
          <Badge className="right-0 z-10" size="xs" color="orange">
            {layout.widgets_count || 0}
          </Badge>
          <button onClick={() => deleteLayout(layout.id, layout.name)}
                  className={`flex items-center text-slate-400 hover:text-red-500 p-0 ${isHovered ? 'ml-2' : ''}`}>
            <Trashcan className="text-slate-400 hover:text-red-500 group-hover:block hidden h-4 w-4" />
          </button>
        </div>
      </span>
    </li>
  );
};
