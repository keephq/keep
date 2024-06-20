'use client';
import { useEffect, useState } from "react";
import { DndContext, useSensor, useSensors, PointerSensor, TouchSensor, rectIntersection } from "@dnd-kit/core";
import { SortableContext, arrayMove } from "@dnd-kit/sortable";
import { usePathname, useRouter } from "next/navigation";
import { GridLink } from "./GridLink";
import { toast } from "react-toastify";
import { getApiURL } from "utils/apiUrl";
import { Subtitle, Button, Badge } from "@tremor/react";
import { Disclosure } from "@headlessui/react";
import { IoChevronUp } from "react-icons/io5";
import classNames from 'classnames';
import Link from "next/link";  // Import Next.js Link if you want to use client-side navigation without full page reloads.

// Define the interface for dashboard
interface Dashboard {
  id: string;
  name: string;
  widgets_count?: number;
}

export const DashboardLinks = ({ session }) => {
  const [dashboards, setDashboards] = useState<Dashboard[]>([]);
  const pathname = usePathname();
  const router = useRouter();
  const apiUrl = getApiURL();

  useEffect(() => {
    const fetchDashboards = async () => {
      try {
        const response = await fetch(`${apiUrl}/dashboard`, {
          headers: {
            'Authorization': `Bearer ${session.accessToken}`
          }
        });
        if (!response.ok) {
          throw new Error('Failed to fetch dashboards');
        }
        const data = await response.json();
        setDashboards(data.dashboards || []);
      } catch (error) {
        console.error('Error fetching dashboards:', error);
      }
    };

    fetchDashboards();
  }, [session]);


  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(TouchSensor)
  );

  if (!session) {
    return null;
  }

  const onDragEnd = (event) => {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      const oldIndex = dashboards.findIndex(dashboard => dashboard.id === active.id);
      const newIndex = dashboards.findIndex(dashboard => dashboard.id === over.id);
      const newDashboards = arrayMove(dashboards, oldIndex, newIndex);
      setDashboards(newDashboards);
    }
  };

  return (
    <Disclosure as="div" className="space-y-1" defaultOpen>
      <Disclosure.Button className="w-full flex justify-between items-center p-2">
        {({ open }) => (
          <>
            <div className="flex justify-between items-center w-full">
              <Subtitle className="text-xs ml-2 text-gray-900 font-medium uppercase">
                Dashboards
              </Subtitle>
              <div className="flex items-center">
                <Badge size="xs" className="mr-1" color="orange">
                  <p className="ml-1">Beta</p>
                </Badge>
                <IoChevronUp className={classNames({ "rotate-180": open }, "mr-2 text-slate-400")} />
              </div>
            </div>
          </>
        )}
      </Disclosure.Button>
      <Disclosure.Panel as="ul" className="space-y-2 overflow-auto min-w-[max-content] p-2 pr-4">
        <DndContext sensors={sensors} collisionDetection={rectIntersection} onDragEnd={onDragEnd}>
          <SortableContext items={dashboards.map(dashboard => dashboard.id)}>
            {dashboards.map((dashboard) => (
              <GridLink key={dashboard.id} dashboard={dashboard} pathname={pathname} deleteDashboard={deleteDashboard} />
            ))}
            <li className="flex justify-center">
              {/* Using Next.js Link for client-side routing */}
              <Link href="/dashboard/create" passHref>
                <Button size="xs" color="orange" variant="secondary">
                  +
                </Button>
              </Link>
            </li>
          </SortableContext>
        </DndContext>
      </Disclosure.Panel>
    </Disclosure>
  );
};
