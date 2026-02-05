import React, { useState } from "react";
import {
  Button,
  Tab,
  TabGroup,
  TabList,
  TabPanels,
  TabPanel,
} from "@tremor/react";
import clsx from "clsx";
import { useAlertTableTheme } from "@/entities/alerts/model";

export const predefinedThemes = {
  Transparent: {
    critical: "bg-white",
    high: "bg-white",
    warning: "bg-white",
    low: "bg-white",
    info: "bg-white",
  },
  Keep: {
    critical: "bg-orange-400", // Highest opacity for critical
    high: "bg-orange-300",
    warning: "bg-orange-200",
    low: "bg-orange-100",
    info: "bg-orange-50", // Lowest opacity for info
  },
  Basic: {
    critical: "bg-red-200",
    high: "bg-orange-200",
    warning: "bg-yellow-200",
    low: "bg-green-200",
    info: "bg-blue-200",
  },
};

const themeKeyMapping = {
  0: "Transparent",
  1: "Keep",
  2: "Basic",
};

type ThemeName = keyof typeof predefinedThemes;

export const AlertTableThemeSelection = ({
  onClose,
}: {
  onClose?: () => void;
}) => {
  const { setTheme } = useAlertTableTheme();
  const [selectedTab, setSelectedTab] = useState<ThemeName>("Transparent");

  const handleTabChange = (event: any) => {
    const themeIndex = event as 0 | 1 | 2;
    const themeName = themeKeyMapping[themeIndex];
    setSelectedTab(themeName as ThemeName);
  };

  const onApplyTheme = () => {
    const themeName: ThemeName = selectedTab;
    const newTheme = predefinedThemes[themeName];
    setTheme(newTheme);
    setSelectedTab("Transparent");
    onClose?.();
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-hidden flex flex-col">
        <span className="text-gray-400 text-sm mb-2">Set theme colors</span>
        <div className="flex-1 overflow-y-auto">
          <TabGroup onIndexChange={handleTabChange}>
            <TabList data-testid="theme-tab-list">
              <Tab>Transparent</Tab>
              <Tab>Keep</Tab>
              <Tab>Basic</Tab>
            </TabList>
            <TabPanels>
              {Object.keys(predefinedThemes).map((themeName) => (
                <TabPanel key={themeName}>
                  {Object.entries(
                    predefinedThemes[themeName as keyof typeof predefinedThemes]
                  ).map(([severity, colorClassName]) => (
                    <div
                      key={severity}
                      className="flex justify-between items-center my-2"
                    >
                      <span className="capitalize">{severity}</span>
                      <div
                        className={clsx(
                          "w-6 h-6 rounded-full border border-gray-400",
                          colorClassName
                        )}
                      ></div>
                    </div>
                  ))}
                </TabPanel>
              ))}
            </TabPanels>
          </TabGroup>
        </div>
      </div>
      <Button
        data-testid="apply-theme-button"
        className="mt-4"
        color="orange"
        onClick={onApplyTheme}
      >
        Apply theme
      </Button>
    </div>
  );
};
