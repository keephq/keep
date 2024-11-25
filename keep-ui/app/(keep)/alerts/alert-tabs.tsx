import { useState } from "react";
import { Tab, TabGroup, TabList, TabPanel, TabPanels } from "@tremor/react";
import { AlertDto } from "./models";
import AlertTabModal from "./alert-tab-modal";
import { evalWithContext } from "./alerts-rules-builder";
import { XMarkIcon } from "@heroicons/react/24/outline";
import { useApiUrl } from "utils/hooks/useConfig";
import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";
import { useApi } from "@/shared/lib/hooks/useApi";
interface Tab {
  id?: string;
  name: string;
  filter: (alert: AlertDto) => boolean;
}

interface Props {
  presetId: string;
  tabs: Tab[];
  setTabs: (tabs: Tab[]) => void;
  selectedTab: number;
  setSelectedTab: (index: number) => void;
}

const AlertTabs = ({
  presetId,
  tabs,
  setTabs,
  selectedTab,
  setSelectedTab,
}: Props) => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const api = useApi();

  const handleTabChange = (index: any) => {
    setSelectedTab(index);
  };

  const addNewTab = (name: string, filter: string) => {
    const newTab = {
      name: name,
      filter: (alert: AlertDto) => evalWithContext(alert, filter),
    };
    const updatedTabs = [...tabs];
    updatedTabs.splice(tabs.length - 1, 0, newTab); // Insert the new tab before the last tab

    setTabs(updatedTabs);
    setIsModalOpen(false);
    setSelectedTab(0); // Set the selected tab to first tab
  };

  const deleteTab = async (index: number) => {
    const tabToDelete = tabs[index];

    // if the tab has id, means it already in the database
    try {
      const response = await api.delete(
        `/preset/${presetId}/tab/${tabToDelete.id}`
      );

      if (!response.ok) {
        throw new Error("Failed to delete the tab");
      }

      const updatedTabs = tabs.filter((_, i) => i !== index);
      setTabs(updatedTabs);
      if (selectedTab === index) {
        setSelectedTab(0); // Set to "All" if the selected tab is deleted
      }
    } catch (error) {
      console.error(error);
      alert("Failed to delete the tab");
    }
  };

  return (
    <div className="tabs-container">
      <TabGroup index={selectedTab} onChange={handleTabChange}>
        <TabList color="orange">
          <>
            {tabs.slice(0, -1).map((tab, index) => (
              <div key={index} className="relative group">
                <Tab className="pr-8">{tab.name.toLowerCase()}</Tab>
                {index !== 0 && (
                  <button
                    className="absolute right-2 top-1/2 transform -translate-y-1/2 opacity-0 group-hover:opacity-100 text-gray-400 hover:text-gray-600"
                    onClick={() => deleteTab(index)}
                  >
                    <XMarkIcon className="h-4 w-4 text-red-500" />
                  </button>
                )}
              </div>
            ))}
            <Tab onClick={() => setIsModalOpen(true)}>
              {tabs[tabs.length - 1].name}
            </Tab>
          </>
        </TabList>
        <TabPanels>
          {tabs.slice(0, -1).map((tab, index) => (
            <TabPanel key={index}></TabPanel>
          ))}
          <TabPanel></TabPanel>
        </TabPanels>
      </TabGroup>

      <AlertTabModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onAddTab={addNewTab}
        presetId={presetId}
      />
    </div>
  );
};

export default AlertTabs;
