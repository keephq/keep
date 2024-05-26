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

// Define the interface for layout
interface Layout {
  id: string;
  name: string;
  widgets_count?: number;
}

export const GridLayoutLinks = ({ session }) => {
  const [layouts, setLayouts] = useState<Layout[]>([]);
  const pathname = usePathname();
  const router = useRouter();
  const apiUrl = getApiURL();

  useEffect(() => {
    const fetchLayouts = async () => {
      try {
        const response = await fetch(`${apiUrl}/layout`, {
          headers: {
            'Authorization': `Bearer ${session.accessToken}`
          }
        });
        if (!response.ok) {
          throw new Error('Failed to fetch layouts');
        }
        const data = await response.json();
        setLayouts(data.layouts || []);
      } catch (error) {
        console.error('Error fetching layouts:', error);
        toast.error('Error fetching layouts');
      }
    };

    fetchLayouts();
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
      const oldIndex = layouts.findIndex(layout => layout.id === active.id);
      const newIndex = layouts.findIndex(layout => layout.id === over.id);
      const newLayouts = arrayMove(layouts, oldIndex, newIndex);
      setLayouts(newLayouts);
    }
  };

  return (
    <Disclosure as="div" className="space-y-1" defaultOpen>
      <Disclosure.Button className="w-full flex justify-between items-center p-2">
        {({ open }) => (
          <>
            <div className="flex justify-between items-center w-full">
  <Subtitle className="text-xs ml-2 text-gray-900 font-medium uppercase">
    Layouts
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
          <SortableContext items={layouts.map(layout => layout.id)}>
            {layouts.map((layout) => (
              <GridLink key={layout.id} layout={layout} pathname={pathname} deleteLayout={deleteLayout} />
            ))}
            <li>
              {/* Using Next.js Link for client-side routing */}
              <Link href="/layout/create" passHref>
                <Button size="sm" color="orange" variant="secondary" className="justify-center">
                  Create New Layout
                </Button>
              </Link>
            </li>
          </SortableContext>
        </DndContext>
      </Disclosure.Panel>
    </Disclosure>
  );
};
