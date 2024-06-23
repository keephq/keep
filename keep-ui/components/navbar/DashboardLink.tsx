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
  deleteDashboard: (id: string) => void;
};

export const DashboardLink = ({ dashboard, pathname, deleteDashboard }: DashboardLinkProps) => {
  const [isHovered, setIsHovered] = useState(false);
  const href = `/dashboard/${dashboard.dashboard_name}`;
  const isActive = decodeURIComponent(pathname|| "") === href;

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
    <LinkWithIcon
          href={href}
          icon={FiLayout}
          isDeletable={true}
          onDelete={() => deleteDashboard(dashboard.id)}
        >
          <Subtitle className={classNames({
              "text-orange-400": isActive,
              "pointer-events-none cursor-auto": isDragging,
            })}>
            {dashboard.dashboard_name}
          </Subtitle>
        </LinkWithIcon>
  );
};
