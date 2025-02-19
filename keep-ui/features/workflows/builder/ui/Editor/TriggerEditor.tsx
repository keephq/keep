import { Button, TextInput } from "@/components/ui";
import { useWorkflowStore } from "@/entities/workflows";
import { BackspaceIcon, FunnelIcon } from "@heroicons/react/24/outline";
import { Text, Subtitle, Icon, Switch } from "@tremor/react";
import { EditorLayout } from "./StepEditor";
import { capitalize } from "@/utils/helpers";

export function TriggerEditor() {
  const {
    v2Properties: properties,
    updateV2Properties,
    selectedNode,
    validationErrors,
  } = useWorkflowStore();

  const handleChange = (key: string, value: string | Record<string, any>) => {
    updateV2Properties({ [key]: value });
  };

  const updateAlertFilter = (filter: string, value: string) => {
    const currentFilters = properties.alert || {};
    const updatedFilters = { ...currentFilters, [filter]: value };
    updateV2Properties({ alert: updatedFilters });
  };

  const addFilter = () => {
    const filterName = prompt("Enter filter name");
    if (filterName) {
      updateAlertFilter(filterName, "");
    }
  };

  const deleteFilter = (filter: string) => {
    const currentFilters = { ...properties.alert };
    delete currentFilters[filter];
    updateV2Properties({ alert: currentFilters });
  };

  const triggerKeys = ["alert", "incident", "interval", "manual"];

  if (!selectedNode || !triggerKeys.includes(selectedNode)) {
    return null;
  }

  const selectedTriggerKey = triggerKeys.find(
    (key) => key === selectedNode
  ) as string;
  const error = validationErrors?.[selectedTriggerKey];

  const renderTriggerContent = () => {
    switch (selectedTriggerKey) {
      case "manual":
        return (
          // TODO: explain what is manual trigger
          <div>
            <input
              type="checkbox"
              checked={true}
              onChange={(e) =>
                handleChange(
                  selectedTriggerKey,
                  e.target.checked ? "true" : "false"
                )
              }
              disabled={true}
            />
          </div>
        );

      case "alert":
        return (
          <>
            <Subtitle className="mt-2.5">Alert filter</Subtitle>
            {error && <Text className="text-red-500 mb-1.5">{error}</Text>}
            <div className="w-1/2">
              <Button
                onClick={addFilter}
                size="xs"
                className="ml-1 mt-1"
                variant="light"
                color="gray"
                icon={FunnelIcon}
              >
                Add Filter
              </Button>
            </div>
            {properties.alert &&
              Object.keys(properties.alert ?? {}).map((filter) => (
                <div key={filter}>
                  <Subtitle className="mt-2.5">{filter}</Subtitle>
                  <div className="flex items-center mt-1">
                    <TextInput
                      key={filter}
                      placeholder={`Set alert ${filter}`}
                      onChange={(e: any) =>
                        updateAlertFilter(filter, e.target.value)
                      }
                      value={
                        (properties.alert as any)[filter] || ("" as string)
                      }
                    />
                    <Icon
                      icon={BackspaceIcon}
                      className="cursor-pointer"
                      color="red"
                      tooltip={`Remove ${filter} filter`}
                      onClick={() => deleteFilter(filter)}
                    />
                  </div>
                </div>
              ))}
          </>
        );

      case "incident":
        return (
          <>
            <Subtitle className="mt-2.5">Incident events</Subtitle>
            {Array("created", "updated", "deleted").map((event) => (
              <div key={`incident-${event}`} className="flex">
                <Switch
                  id={event}
                  checked={properties.incident.events?.indexOf(event) > -1}
                  onChange={() => {
                    let events = properties.incident.events || [];
                    if (events.indexOf(event) > -1) {
                      events = (events as string[]).filter((e) => e !== event);
                      updateV2Properties({
                        [selectedTriggerKey]: { events: events },
                      });
                    } else {
                      events.push(event);
                      updateV2Properties({
                        [selectedTriggerKey]: { events: events },
                      });
                    }
                  }}
                  color={"orange"}
                />
                <label
                  htmlFor={`incident-${event}`}
                  className="text-sm text-gray-500"
                >
                  <Text>{event}</Text>
                </label>
              </div>
            ))}
          </>
        );

      case "interval":
        return (
          <>
            <Subtitle className="mt-2.5">Interval (in seconds)</Subtitle>
            <TextInput
              placeholder={`Set the ${selectedTriggerKey}`}
              onChange={(e: any) =>
                handleChange(selectedTriggerKey, e.target.value)
              }
              value={properties[selectedTriggerKey] || ("" as string)}
              error={!!error}
              errorMessage={error}
            />
          </>
        );

      default:
        return null;
    }
  };

  return (
    <EditorLayout>
      <Subtitle className="font-medium flex items-baseline justify-between">
        {capitalize(selectedTriggerKey)} Trigger
      </Subtitle>
      <div className="flex flex-col gap-2">{renderTriggerContent()}</div>
    </EditorLayout>
  );
}
