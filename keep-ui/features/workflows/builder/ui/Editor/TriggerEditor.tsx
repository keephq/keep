import { Button, TextInput } from "@/components/ui";
import { useWorkflowStore } from "@/entities/workflows";
import { BackspaceIcon, FunnelIcon } from "@heroicons/react/24/outline";
import { Text, Subtitle, Icon, Switch } from "@tremor/react";
import { EditorLayout } from "./StepEditor";
import { capitalize } from "@/utils/helpers";
import { getHumanReadableInterval } from "@/entities/workflows/lib/getHumanReadableInterval";
import { debounce } from "lodash";
import { useCallback } from "react";
import CelInput from "@/features/cel-input/cel-input";
import { useFacetPotentialFields } from "@/features/filter";

export function TriggerEditor() {
  const {
    v2Properties: properties,
    updateV2Properties,
    updateSelectedNodeData,
    selectedNode,
    validationErrors,
  } = useWorkflowStore();

  const saveNodeDataDebounced = useCallback(
    debounce((key: string, value: string | Record<string, any>) => {
      updateSelectedNodeData(key, value);
    }, 300),
    [updateSelectedNodeData]
  );

  const handleChange = (key: string, value: string | Record<string, any>) => {
    updateV2Properties({ [key]: value });
    if (key === "interval") {
      updateSelectedNodeData("properties", { interval: value });
    }
  };

  const updateAlertFilter = (filter: string, value: string) => {
    const currentFilters = properties.alert || {};
    if (!currentFilters.filters) {
      currentFilters.filters = {};
    }
    currentFilters.filters[filter] = value;
    updateV2Properties({ alert: currentFilters });
    saveNodeDataDebounced("properties", { alert: currentFilters });
  };

  const updateAlertCel = (value: string) => {
    const currentFilters = properties.alert || {};
    updateV2Properties({ alert: { ...currentFilters, cel: value } });
    saveNodeDataDebounced("properties", {
      alert: { ...currentFilters, cel: value },
    });
  };

  const addFilter = () => {
    const filterName = prompt("Enter filter name");
    if (filterName) {
      updateAlertFilter(filterName, "");
    }
  };

  const deleteFilter = (filter: string) => {
    const currentFilters = { ...properties.alert };
    delete currentFilters.filters[filter];
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
    const { data: alertFields } = useFacetPotentialFields("alerts");

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
            {error && (
              <Text className="text-red-500 mb-1.5">
                {Array.isArray(error) ? error[0] : error}
              </Text>
            )}
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
            <div>
              <Subtitle className="mt-2.5">CEL Expression</Subtitle>
              <div className="flex items-center mt-1 relative">
                <CelInput
                  staticPositionForSuggestions={true}
                  value={properties.alert.cel}
                  placeholder="Use CEL to filter alerts that trigger this workflow. e.g. source.contains('kibana')"
                  onValueChange={(value: string) => updateAlertCel(value)}
                  onClearValue={() => updateAlertCel("")}
                  fieldsForSuggestions={alertFields}
                />
                <Icon
                  icon={BackspaceIcon}
                  className="cursor-pointer"
                  color="red"
                  tooltip={`Clear CEL expression`}
                  onClick={() => updateAlertCel("")}
                />
              </div>
            </div>
            {properties.alert.filters &&
              Object.keys(properties.alert.filters ?? {}).map((filter) => (
                <>
                  <Subtitle className="mt-2.5">
                    Alert filter (deprecated)
                  </Subtitle>
                  <Text className="text-sm text-gray-500">
                    Please convert your alert filters to CEL expressions to
                    ensure stability and performance.
                  </Text>
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
                          (properties.alert.filters as any)[filter] ||
                          ("" as string)
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
                </>
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

      case "interval": {
        const value = properties[selectedTriggerKey];
        return (
          <>
            <Subtitle className="mt-2.5">Interval (in seconds)</Subtitle>
            <TextInput
              placeholder={`Set the ${selectedTriggerKey}`}
              onChange={(e: any) =>
                handleChange(selectedTriggerKey, e.target.value)
              }
              value={value || ("" as string)}
              error={!!error}
              errorMessage={error?.[0]}
            />
            {value && (
              <Text className="text-sm text-gray-500">
                Workflow will run every {getHumanReadableInterval(value)}
              </Text>
            )}
          </>
        );
      }

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
