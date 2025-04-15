"use client";

import React, { useEffect, useState } from "react";
import {
  Card,
  Text,
  Title,
  Switch,
  NumberInput,
  Button,
  Callout,
  Divider,
} from "@tremor/react";
import { KeepLoader, showErrorToast, showSuccessToast } from "@/shared/ui";
import { InformationCircleIcon } from "@heroicons/react/24/outline";
import {
  useTopologySettings,
  TopologyProcessorSettings,
} from "@/app/(keep)/topology/model/useTopologySettings";

// Default values for settings
const DEFAULT_SETTINGS: TopologyProcessorSettings = {
  enabled: false,
  lookBackWindow: 15,
};

export function TopologySettings() {
  const [isSaving, setIsSaving] = useState(false);
  const [settings, setSettings] =
    useState<TopologyProcessorSettings>(DEFAULT_SETTINGS);
  const [initialSettings, setInitialSettings] =
    useState<TopologyProcessorSettings>(DEFAULT_SETTINGS);
  const [settingsLoaded, setSettingsLoaded] = useState(false);

  const {
    settings: fetchedSettings,
    isLoading,
    error,
    updateSettings,
  } = useTopologySettings({
    initialData: DEFAULT_SETTINGS,
  });

  useEffect(() => {
    if (fetchedSettings && !isLoading) {
      // Create new objects to avoid reference issues
      const settingsData = {
        enabled: Boolean(fetchedSettings.enabled),
        lookBackWindow: Number(fetchedSettings.lookBackWindow),
      };

      setSettings(settingsData);
      setInitialSettings(settingsData);
      setSettingsLoaded(true);
    }
  }, [fetchedSettings, isLoading]);

  const handleSettingsChange = (
    newSettings: Partial<TopologyProcessorSettings>
  ) => {
    setSettings((prev) => ({ ...prev, ...newSettings }));
  };

  const handleSave = async () => {
    try {
      setIsSaving(true);
      await updateSettings(settings);
      // Update initialSettings with a new object to avoid reference issues
      setInitialSettings({ ...settings });
      showSuccessToast("Topology processor settings updated successfully");
    } catch (error) {
      showErrorToast(error, "Failed to update topology processor settings");
    } finally {
      setIsSaving(false);
    }
  };

  // Direct comparison of individual values
  const hasChanges =
    settingsLoaded &&
    (initialSettings.enabled !== settings.enabled ||
      initialSettings.lookBackWindow !== settings.lookBackWindow);

  // Get reason why button is disabled
  const getDisabledReason = () => {
    if (isLoading) return "Loading settings...";
    if (isSaving) return "Saving changes...";
    if (!hasChanges) return "No changes to save";
    return "";
  };

  const disabledReason = getDisabledReason();
  const isButtonDisabled = isLoading || isSaving || !hasChanges;

  if (isLoading) {
    return (
      <div className="h-64 flex items-center justify-center">
        <KeepLoader />
      </div>
    );
  }

  if (error) {
    showErrorToast(error, "Failed to fetch topology processor settings");
  }

  return (
    <div className="space-y-6 w-full">
      <Card className="p-6">
        <div className="space-y-6">
          <Title>Topology Correlation Settings</Title>

          <Callout
            title="About Topology Correlation"
            icon={InformationCircleIcon}
            color="blue"
            className="mt-4"
          >
            The Topology Processor correlates alerts based on service
            relationships in your infrastructure topology. When enabled, it
            creates meaningful incidents that reflect dependencies between your
            services.
          </Callout>

          <Divider />

          <div className="space-y-8 mt-6">
            <div>
              <Text className="font-medium text-base">
                Enable Topology Processor
              </Text>
              <Text className="text-sm text-gray-500 mt-1 mb-3">
                When enabled, alerts will be correlated based on topology
                relationships
              </Text>
              <div className="mt-2">
                <Switch
                  id="topology-processor-enabled"
                  name="enabled"
                  checked={settings.enabled}
                  onChange={(checked) =>
                    handleSettingsChange({ enabled: checked })
                  }
                  disabled={isLoading}
                  color="orange"
                />
              </div>
            </div>

            <div className={!settings.enabled ? "opacity-60" : ""}>
              <Text className="font-medium text-base">Look Back Window</Text>
              <Text className="text-sm text-gray-500 mt-1 mb-3">
                The time window in minutes during which alerts are considered
                for correlation
              </Text>
              <NumberInput
                placeholder="Enter minutes"
                value={settings.lookBackWindow}
                onChange={(e) => {
                  const value = parseInt(e.target.value, 10);
                  if (!isNaN(value) && value > 0) {
                    handleSettingsChange({ lookBackWindow: value });
                  }
                }}
                min={1}
                className="max-w-xs"
                disabled={isLoading || !settings.enabled}
              />
            </div>
          </div>

          <Divider />

          <div className="flex justify-end mt-8">
            <Button
              color="orange"
              disabled={isButtonDisabled}
              loading={isSaving}
              onClick={handleSave}
              tooltip={disabledReason}
            >
              Save Changes
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
