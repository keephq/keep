import { useSortable } from "@dnd-kit/sortable";
import { Subtitle } from "@tremor/react";
import { FiLayout } from "react-icons/fi";
import { LinkWithIcon } from "components/LinkWithIcon"; // Ensure you import this correctly
import { clsx } from "clsx";

interface Dashboard {
  id: string;
  dashboard_name: string;
  dashboard_config: any;
}

type DashboardLinkProps = {
  dashboard: Dashboard;
  pathname: string | null;
  deleteDashboard: (id: string) => void;
  titleClassName?: string;
};

export const DashboardLink = ({
  dashboard,
  pathname,
  deleteDashboard,
  titleClassName,
}: DashboardLinkProps) => {
  const href = `/dashboard/${dashboard.dashboard_name}`;
  const isActive = decodeURIComponent(pathname || "") === href;

  const { isDragging } = useSortable({
    id: dashboard.id,
  });

  return (
    <LinkWithIcon
      href={href}
      icon={FiLayout}
      isDeletable={true}
      onDelete={() => deleteDashboard(dashboard.id)}
    >
      <Subtitle
        className={clsx(
          {
            "text-orange-400": isActive,
            "pointer-events-none cursor-auto": isDragging,
          },
          titleClassName
        )}
      >
        {dashboard.dashboard_name}
      </Subtitle>
    </LinkWithIcon>
  );
};
