import React from "react";
import { useWorkflowStore } from "@/entities/workflows";
import { Button, Divider, Icon, Subtitle, Text } from "@tremor/react";
import { BackspaceIcon, PlusIcon } from "@heroicons/react/24/outline";
import { TextInput } from "@/components/ui";
import { EditorLayout } from "./StepEditor";

export function WorkflowEditorV2() {
  const {
    v2Properties: properties,
    updateV2Properties,
    selectedNode,
    validationErrors,
  } = useWorkflowStore();
  const isDeployed = useWorkflowStore((state) => state.workflowId !== null);

  const handleChange = (key: string, value: string | Record<string, any>) => {
    updateV2Properties({ [key]: value });
  };

  const addNewConstant = () => {
    const updatedConsts = {
      ...(properties["consts"] as { [key: string]: string }),
      [`newKey${Object.keys(properties["consts"] || {}).length}`]: "",
    };
    updateV2Properties({ consts: updatedConsts });
  };

  const lockedKeys = [
    "isLocked",
    "id",
    "disabled",
    "alert",
    "interval",
    "incident",
    "manual",
  ];
  const metadataKeys = ["name", "description"];
  // If workflow is not deployed, we can edit the metadata here, in side panel; otherwise we can edit via modal
  const toSkip = [...lockedKeys, ...(isDeployed ? metadataKeys : [])];

  const propertyKeys = Object.keys(properties).filter(
    (k) => !toSkip.includes(k)
  );
  let renderDivider = false;
  return (
    <EditorLayout>
      <Subtitle className="font-medium flex items-baseline justify-between">
        Workflow Settings
      </Subtitle>
      <div className="flex flex-col gap-2">
        {propertyKeys.map((key, index) => {
          const isTrigger = [
            "manual",
            "alert",
            "interval",
            "incident",
          ].includes(key);

          let isConst = key === "consts";
          if (isConst && !properties[key]) {
            properties[key] = {};
          }

          renderDivider =
            isTrigger && key === selectedNode ? !renderDivider : false;

          const errorKey = ["name", "description"].includes(key)
            ? `workflow_${key}`
            : key;
          const error = validationErrors?.[errorKey];
          return (
            <div key={key}>
              {renderDivider && <Divider />}
              {(key === selectedNode || !isTrigger) && (
                <Text className="capitalize mb-1.5">{key}</Text>
              )}

              {(() => {
                switch (key) {
                  case "consts":
                    // if consts is empty, set it to an empty object
                    if (!properties[key]) {
                      return null;
                    }
                    return (
                      <div key={key}>
                        {Object.entries(
                          properties[key] as { [key: string]: string }
                        ).map(([constKey, constValue]) => (
                          <div
                            key={constKey}
                            className="flex items-center mt-1"
                          >
                            <TextInput
                              placeholder={`Key ${constKey}`}
                              value={constKey}
                              onChange={(e) => {
                                const updatedConsts = {
                                  ...(properties[key] as {
                                    [key: string]: string;
                                  }),
                                };
                                delete updatedConsts[constKey];
                                updatedConsts[e.target.value] = constValue;
                                handleChange(key, updatedConsts);
                              }}
                            />
                            <TextInput
                              placeholder={`Value ${constValue}`}
                              value={constValue}
                              onChange={(e) => {
                                const updatedConsts = {
                                  ...(properties[key] as {
                                    [key: string]: string;
                                  }),
                                };
                                updatedConsts[constKey] = e.target.value;
                                handleChange(key, updatedConsts);
                              }}
                            />
                            <Icon
                              icon={BackspaceIcon}
                              className="cursor-pointer"
                              color="red"
                              tooltip={`Remove ${constKey}`}
                              onClick={() => {
                                const updatedConsts = {
                                  ...(properties[key] as {
                                    [key: string]: string;
                                  }),
                                };
                                delete updatedConsts[constKey];
                                handleChange(key, updatedConsts);
                              }}
                            />
                          </div>
                        ))}
                        <Button
                          onClick={addNewConstant}
                          size="xs"
                          className="ml-1 mt-1"
                          variant="light"
                          color="gray"
                          icon={PlusIcon}
                        >
                          Add Constant
                        </Button>
                      </div>
                    );
                  default:
                    return (
                      <TextInput
                        placeholder={`Set the ${key}`}
                        onChange={(e: any) => handleChange(key, e.target.value)}
                        value={properties[key] || ("" as string)}
                        error={!!error}
                        errorMessage={error}
                      />
                    );
                }
              })()}
            </div>
          );
        })}
      </div>
    </EditorLayout>
  );
}
