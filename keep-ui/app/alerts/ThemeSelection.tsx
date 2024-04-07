import React, { useState, Fragment, useRef } from 'react';
import { Popover } from '@headlessui/react';
import { Button, Tab, TabGroup, TabList, TabPanels, TabPanel } from "@tremor/react";
import { IoColorPaletteOutline } from 'react-icons/io5';
import { FloatingArrow, arrow, offset, useFloating } from "@floating-ui/react";
import { severityMapping } from './models';

const predefinedThemes = {
  Transparent: {
    critical: 'bg-white',
    high: 'bg-white',
    warning: 'bg-white',
    low: 'bg-white',
    info: 'bg-white'
  },
  Keep: {
    critical: 'bg-orange-400', // Highest opacity for critical
    high: 'bg-orange-300',
    warning: 'bg-orange-200',
    low: 'bg-orange-100',
    info: 'bg-orange-50' // Lowest opacity for info
  },
  Basic: {
    critical: 'bg-red-200',
    high: 'bg-orange-200',
    warning: 'bg-yellow-200',
    low: 'bg-green-200',
    info: 'bg-blue-200'
  }
};

const themeKeyMapping = {
  0: 'Transparent',
  1: 'Keep',
  2: 'Basic'
};

export const ThemeSelection = ({ onThemeChange }) => {
  const arrowRef = useRef(null);
  const [selectedTab, setSelectedTab] = useState('Transparent');

  const { refs, floatingStyles, context } = useFloating({
    strategy: "fixed",
    placement: "bottom-end",
    middleware: [offset({ mainAxis: 10 }), arrow({ element: arrowRef })],
  });

  const handleApplyTheme = (themeKey) => {
    const themeName = themeKeyMapping[themeKey];
    setSelectedTab(themeName); // Update the selected tab
  };

  const onApplyTheme = (close) => {
    // Determine the theme name based on the currently selected tab
    const themeName = selectedTab;
    const newTheme = predefinedThemes[themeName];
    onThemeChange(newTheme); // Apply one of the predefined themes
    setSelectedTab('Transparent')
    close(); // Close the popover
  };

  return (
    <Popover as={Fragment}>
      {({ close }) => (
        <>
          <Popover.Button
            as={Button}
            variant="light"
            color="gray"
            icon={IoColorPaletteOutline}
            ref={refs.setReference}
            className="ml-2"
          />
          <Popover.Overlay className="fixed inset-0 bg-black opacity-30 z-20" />
          <Popover.Panel
            className="bg-white z-30 p-4 rounded-sm"
            ref={refs.setFloating}
            style={{ ...floatingStyles, minWidth: '250px' }} // Adjust width here
          >
            <FloatingArrow
              className="fill-white [&>path:last-of-type]:stroke-white"
              ref={arrowRef}
              context={context}
            />
            <span className="text-gray-400 text-sm">Set theme colors</span>
            <TabGroup onChange={(themeKey) => handleApplyTheme(themeKey, close)}>
              <TabList color="orange">
                <Tab>Transparent</Tab>
                <Tab>Keep</Tab>
                <Tab>Basic</Tab>
              </TabList>
              <TabPanels>
                {Object.keys(predefinedThemes).map(themeName => (
                  <TabPanel key={themeName}>
                    {Object.entries(predefinedThemes[themeName]).map(([severity, color]) => (
                      <div key={severity} className="flex justify-between items-center my-2">
                        <span>{severity.charAt(0).toUpperCase() + severity.slice(1).toLowerCase()}</span>
                        <div className={`w-6 h-6 rounded-full border border-gray-400 ${color}`}></div>
                      </div>
                    ))}
                  </TabPanel>
                ))}
              </TabPanels>
            </TabGroup>
             <Button className="mt-5" color="orange" onClick={() => onApplyTheme(close)}>
              Apply theme
            </Button>
          </Popover.Panel>
        </>
      )}
    </Popover>
  );
};
