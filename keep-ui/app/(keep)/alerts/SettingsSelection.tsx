import { Fragment, useRef } from "react";
import {
  Button,
  Tab,
  TabGroup,
  TabList,
  TabPanels,
  TabPanel,
} from "@tremor/react";
import { Popover } from "@headlessui/react";
import { FiSettings } from "react-icons/fi";
import { FloatingArrow, arrow, offset, useFloating } from "@floating-ui/react";
import { Table } from "@tanstack/table-core";
import { AlertDto } from "@/entities/alerts/model";
import ColumnSelection from "./ColumnSelection";
import { ThemeSelection } from "./ThemeSelection";
import { RowStyleSelection } from "./RowStyleSelection";
import { ActionTraySelection } from "./ActionTraySelection";

interface SettingsSelectionProps {
  table: Table<AlertDto>;
  presetName: string;
  onThemeChange: (theme: any) => void;
}

export default function SettingsSelection({
  table,
  presetName,
  onThemeChange,
}: SettingsSelectionProps) {
  const arrowRef = useRef(null);
  const { refs, floatingStyles, context } = useFloating({
    strategy: "fixed",
    placement: "bottom-end",
    middleware: [
      offset({ mainAxis: 10 }),
      arrow({
        element: arrowRef,
      }),
    ],
  });

  return (
    <Popover as={Fragment}>
      {({ close }) => (
        <>
          <Popover.Button
            variant="light"
            color="gray"
            as={Button}
            icon={FiSettings}
            ref={refs.setReference}
          />
          <Popover.Overlay className="fixed inset-0 bg-black opacity-30 z-20" />
          <Popover.Panel
            className="bg-white z-30 p-4 rounded-sm w-[400px]"
            ref={refs.setFloating}
            style={{
              ...floatingStyles,
              maxHeight: "80vh", // Limit height to 80% of viewport height
              overflowY: "auto", // Add scroll when content exceeds max height
            }}
          >
            <FloatingArrow
              className="fill-white [&>path:last-of-type]:stroke-white"
              ref={arrowRef}
              context={context}
            />
            <div
              className="flex flex-col"
              style={{ maxHeight: "calc(80vh - 40px)" }}
            >
              <TabGroup className="flex flex-col flex-1">
                <TabList color="orange" className="mb-4">
                  <Tab>Columns</Tab>
                  <Tab>Theme</Tab>
                  <Tab>Row Style</Tab>
                  <Tab>Action Tray</Tab>
                </TabList>
                <TabPanels className="flex-1 overflow-hidden">
                  <TabPanel className="h-full">
                    <ColumnSelection
                      table={table}
                      presetName={presetName}
                      onClose={close}
                    />
                  </TabPanel>
                  <TabPanel className="h-full">
                    <ThemeSelection
                      onThemeChange={onThemeChange}
                      onClose={close}
                    />
                  </TabPanel>
                  <TabPanel className="h-full">
                    <RowStyleSelection onClose={close} />
                  </TabPanel>
                  <TabPanel className="h-full">
                    <ActionTraySelection onClose={close} />
                  </TabPanel>
                </TabPanels>
              </TabGroup>
            </div>
          </Popover.Panel>
        </>
      )}
    </Popover>
  );
}
