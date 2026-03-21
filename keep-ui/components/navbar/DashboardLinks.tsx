"use client";

import {
  DndContext,
  useSensor,
  useSensors,
  PointerSensor,
  TouchSensor,
  rectIntersection,
} from "@dnd-kit/core";
import { arrayMove, SortableContext } from "@dnd-kit/sortable";
import { usePathname, useRouter } from "next/navigation";
import { Subtitle, Button, Badge, Text } from "@tremor/react";
import { Disclosure } from "@headlessui/react";
import { IoChevronUp } from "react-icons/io5";
import clsx from "clsx";
import { useDashboards } from "utils/hooks/useDashboards";
import { useApi } from "@/shared/lib/hooks/useApi";
import { PlusIcon } from "@radix-ui/react-icons";
import { DashboardLink } from "./DashboardLink";
import { useTranslations } from "next-intl";

export const DashboardLinks = () => {
  const t = useTranslations("dashboard");
  const { dashboards = [], isLoading, error, mutate } = useDashboards();
  const api = useApi();
  const router = useRouter();
  const pathname = usePathname();

  const sensors = useSensors(useSensor(PointerSensor), useSensor(TouchSensor));

  const onDragEnd = (event: any) => {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      const oldIndex = dashboards.findIndex(
        (dashboard) => dashboard.id === active.id
      );
      const newIndex = dashboards.findIndex(
        (dashboard) => dashboard.id === over.id
      );
      const newDashboards = arrayMove(dashboards, oldIndex, newIndex);
      mutate(newDashboards, false);
    }
  };

  const deleteDashboard = async (id: string) => {
    const isDeleteConfirmed = confirm(
      t("messages.confirmDelete", { defaultValue: "您即将删除此仪表盘。确定要继续吗？" })
    );
    if (isDeleteConfirmed) {
      try {
        await api.delete(`/dashboard/${id}`);
        mutate(
          dashboards.filter((dashboard) => dashboard.id !== id),
          false
        );
        // now redirect to the first dashboard
        router.push(
          `/dashboard/${encodeURIComponent(dashboards[0].dashboard_name)}`
        );
      } catch (error) {
        console.error("Error deleting dashboard:", error);
      }
    }
  };

  const generateUniqueName = (baseName: string): string => {
    let uniqueName = baseName;
    let counter = 1;
    while (
      dashboards.some(
        (d) => d.dashboard_name.toLowerCase() === uniqueName.toLowerCase()
      )
    ) {
      uniqueName = `${baseName}(${counter})`;
      counter++;
    }
    return uniqueName;
  };

  const handleCreateDashboard = () => {
    const uniqueName = generateUniqueName("My Dashboard");
    router.push(`/dashboard/${encodeURIComponent(uniqueName)}`);
  };

  return (
    <Disclosure as="div" className="space-y-1" defaultOpen>
      <Disclosure.Button className="w-full flex justify-between items-center px-2">
        {({ open }) => (
          <>
            <div className="flex justify-between items-center w-full">
              <Subtitle className="text-xs ml-2 text-gray-900 font-medium uppercase">
                {t("title")}
              </Subtitle>
              <div className="flex items-center">
                <Badge color="orange" size="xs" className="ml-2 mr-2">
                  Beta
                </Badge>
                <IoChevronUp
                  className={clsx(
                    { "rotate-180": open },
                    "mr-2 text-slate-400"
                  )}
                />
              </div>
            </div>
          </>
        )}
      </Disclosure.Button>
      <Disclosure.Panel
        as="ul"
        // pr-4 to make space for scrollbar
        className="space-y-2 overflow-auto px-2 pr-4"
      >
        <DndContext
          sensors={sensors}
          collisionDetection={rectIntersection}
          onDragEnd={onDragEnd}
        >
          <SortableContext items={dashboards.map((dashboard) => dashboard.id)}>
            {dashboards && dashboards.length ? (
              dashboards.map((dashboard) => (
                <DashboardLink
                  key={dashboard.id}
                  dashboard={dashboard}
                  pathname={pathname}
                  deleteDashboard={deleteDashboard}
                  titleClassName="max-w-[150px] overflow-hidden overflow-ellipsis"
                />
              ))
            ) : (
              <Text className="text-xs max-w-[200px] px-2">
                {t("messages.noDashboards", { defaultValue: "保存后的仪表盘将显示在这里。" })}
              </Text>
            )}
          </SortableContext>
        </DndContext>
        {/* TODO: use link instead of button */}
        <Button
          size="xs"
          color="orange"
          variant="secondary"
          className="h-5 mx-2"
          onClick={handleCreateDashboard}
          icon={PlusIcon}
        >
          {t("addDashboard", { defaultValue: "添加仪表盘" })}
        </Button>
      </Disclosure.Panel>
    </Disclosure>
  );
};
