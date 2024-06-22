import { CSSProperties, useState } from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { Icon, Subtitle } from "@tremor/react";
import { Trashcan } from "components/icons"; // Assuming you have a similar icon component
import { FiLayout } from "react-icons/fi";
import { LinkWithIcon } from "components/LinkWithIcon"; // Ensure you import this correctly
import classNames from 'classnames';

interface Dashboard {
  id: string;
  dashboard_name: string;
  dashboard_config: any;
}

type DashboardLinkProps = {
  dashboard: Dashboard;
  pathname: string | null;
  deleteDashboard: (id: string, name: string) => void;
};

export const DashboardLink = ({ dashboard, pathname, deleteDashboard }: DashboardLinkProps) => {
  const [isHovered, setIsHovered] = useState(false);
  const href = `/dashboard/${dashboard.dashboard_name.toLowerCase()}`;
  const isActive = decodeURIComponent(pathname?.toLowerCase() || "") === href;

  const { listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({
      id: dashboard.id,
    });

  const dragStyle: CSSProperties = {
    opacity: isDragging ? 0.5 : 1,
    transform: CSS.Translate.toString(transform),
    transition,
    cursor: isDragging ? "grabbing" : "grab",
  };

  return (
    <li key={dashboard.id} ref={setNodeRef} style={dragStyle} {...listeners}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}>
      <span className={classNames("flex items-center space-x-2 text-sm p-1 text-slate-400 font-medium rounded-lg", {
            "bg-stone-200/50": isActive,
            "hover:text-orange-400 focus:ring focus:ring-orange-300 group hover:bg-stone-200/50": !isDragging,
          })}>
        <LinkWithIcon
          href={href}
          icon={FiLayout} // Replace with the appropriate icon if different
        >
          <Subtitle className={classNames({
              "text-orange-400": isActive,
              "pointer-events-none cursor-auto": isDragging,
            })}>
            {dashboard.dashboard_name}
          </Subtitle>
        </LinkWithIcon>
        <div className="flex items-center justify-end flex-1">
          <button onClick={() => deleteDashboard(dashboard.id, dashboard.dashboard_name)} // Use correct property for name
                  className={`flex items-center text-slate-400 hover:text-red-500 p-0 ${isHovered ? 'ml-2' : ''}`}>
            <Trashcan className="text-slate-400 hover:text-red-500 group-hover:block hidden h-4 w-4" />
          </button>
        </div>
      </span>
    </li>
  );
};
