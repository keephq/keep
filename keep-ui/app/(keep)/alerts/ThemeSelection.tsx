import React, { useState } from "react";
import {
  Button,
  Tab,
  TabGroup,
  TabList,
  TabPanels,
  TabPanel,
} from "@tremor/react";

const predefinedThemes = {
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

export const ThemeSelection = ({
  onThemeChange,
  onClose,
}: {
  onThemeChange: (theme: any) => void;
  onClose?: () => void;
}) => {
  const [selectedTab, setSelectedTab] = useState<ThemeName>("Transparent");

  const handleThemeChange = (event: any) => {
    const themeIndex = event as 0 | 1 | 2;
    handleApplyTheme(themeIndex as 0 | 1 | 2);
  };

  const handleApplyTheme = (themeKey: keyof typeof themeKeyMapping) => {
    const themeName = themeKeyMapping[themeKey];
    setSelectedTab(themeName as ThemeName);
  };

  const onApplyTheme = () => {
    const themeName: ThemeName = selectedTab;
    const newTheme = predefinedThemes[themeName];
    onThemeChange(newTheme);
    setSelectedTab("Transparent");
    onClose?.();
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-hidden flex flex-col">
        <span className="text-gray-400 text-sm mb-2">Set theme colors</span>
        <div className="flex-1 overflow-y-auto">
          <TabGroup onChange={handleThemeChange}>
            <TabList>
              <Tab>Transparent</Tab>
              <Tab>Keep</Tab>
              <Tab>Basic</Tab>
            </TabList>
            <TabPanels>
              {Object.keys(predefinedThemes).map((themeName) => (
                <TabPanel key={themeName}>
                  {Object.entries(
                    predefinedThemes[themeName as keyof typeof predefinedThemes]
                  ).map(([severity, color]) => (
                    <div
                      key={severity}
                      className="flex justify-between items-center my-2"
                    >
                      <span>
                        {severity.charAt(0).toUpperCase() +
                          severity.slice(1).toLowerCase()}
                      </span>
                      <div
                        className={`w-6 h-6 rounded-full border border-gray-400 ${color}`}
                      ></div>
                    </div>
                  ))}
                </TabPanel>
              ))}
            </TabPanels>
          </TabGroup>
        </div>
      </div>
      <Button className="mt-4" color="orange" onClick={onApplyTheme}>
        Apply theme
      </Button>
    </div>
  );
};
