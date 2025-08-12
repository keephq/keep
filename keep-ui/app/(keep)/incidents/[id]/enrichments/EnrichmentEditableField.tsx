import { useRouter } from "next/navigation";
import React, { useState } from "react";
import { xor } from "lodash";
import { Badge, Icon, TextInput, NumberInput, Switch } from "@tremor/react";
import { Button } from "@/components/ui";
import { FiSave, FiTrash2, FiX } from "react-icons/fi";
import { MdModeEdit } from "react-icons/md";

interface EnrichmentEditableFieldProps {
  name?: string;
  value: string | string[] | number | boolean | null;
  onUpdate: (fieldName: string, newValue: string | string[] | number | boolean) => Promise<void>;
  onDelete?: (fieldName: string) => Promise<void>;
  children?: React.ReactNode;
}

export const EnrichmentEditableField = ({
  name,
  value,
  onUpdate,
  onDelete,
  children,
}: EnrichmentEditableFieldProps) => {
  const router = useRouter();

  const [editMode, setEditMode] = useState(false);
  const [stringedValue, setStringedValue] = useState(
    Array.isArray(value) ? value.join(", ") : String(value ?? "")
  );
  const [booleanValue, setBooleanValue] = useState<boolean>(
    typeof value === "boolean" ? value : false
  );
  const [numberValue, setNumberValue] = useState<number>(
    typeof value === "number" ? value : 0
  );
  const [fieldName, setFieldName] = useState<string>(name || "");
  const [fieldNameError, setFieldNameError] = useState<boolean>(false);
  const [valueError, setValueError] = useState<boolean>(false);
  const [valueType, setValueType] = useState<"string" | "number" | "boolean">(
    typeof value === "boolean" ? "boolean" : typeof value === "number" ? "number" : "string"
  );

  const handleSave = async () => {
    let newValue: string | string[] | number | boolean;
    
    if (Array.isArray(value)) {
      newValue = stringedValue.split(",").map((s) => s.trim());
    } else if (valueType === "boolean") {
      newValue = booleanValue;
    } else if (valueType === "number") {
      newValue = numberValue;
    } else {
      newValue = stringedValue.toString().trim();
    }

    if (Array.isArray(newValue) && Array.isArray(value) && xor(value, newValue).length === 0) {
      return;
    } else if (value === newValue) {
      return;
    }

    await onUpdate(name || fieldName, newValue);
    setEditMode(false);
  };

  const handleUnenrich = async () => {
    if (onDelete) {
      await onDelete(name || fieldName);
    }
    // Reset value
    setEditMode(false);
    resetForm();
  };

  const resetForm = () => {
    setStringedValue(Array.isArray(value) ? value.join(", ") : String(value ?? ""));
    setBooleanValue(typeof value === "boolean" ? value : false);
    setNumberValue(typeof value === "number" ? value : 0);
    setValueType(typeof value === "boolean" ? "boolean" : typeof value === "number" ? "number" : "string");
    setFieldName(name || "");
  };

  const handleCancel = () => {
    setEditMode(false);
    resetForm();
  };

  const filterBy = (key: string, value: string) => {
    router.push(
      `/alerts/feed?cel=${key}%3D%3D${encodeURIComponent(`"${value}"`)}`
    );
  };

  const handleNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFieldNameError(e.target.value === "");
    setFieldName(e.target.value);
  };

  const handleValueChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setValueError(e.target.value === "");
    setStringedValue(e.target.value);
  };

  if (editMode) {
    return (
      <div className="flex items-center flex-wrap gap-2.5 z-50">
        {!name && (
          <>
            <TextInput
              value={fieldName}
              error={fieldNameError}
              onChange={handleNameChange}
              placeholder="Add name"
            />
            <select
              className="text-sm px-2 py-1 border rounded"
              value={valueType}
              onChange={(e) => setValueType(e.target.value as "string" | "number" | "boolean")}
            >
              <option value="string">Text</option>
              <option value="number">Number</option>
              <option value="boolean">Yes/No</option>
            </select>
          </>
        )}
        {Array.isArray(value) ? (
          <TextInput
            value={stringedValue}
            error={valueError}
            onChange={handleValueChange}
            placeholder="Add values (comma-separated)"
          />
        ) : valueType === "boolean" ? (
          <div className="flex items-center gap-2">
            <Switch
              id="boolean-value"
              checked={booleanValue}
              onChange={setBooleanValue}
            />
            <label htmlFor="boolean-value" className="text-sm">
              {booleanValue ? "Yes" : "No"}
            </label>
          </div>
        ) : valueType === "number" ? (
          <NumberInput
            value={numberValue}
            onValueChange={(val) => {
              setNumberValue(val ?? 0);
              setValueError(false);
            }}
            placeholder="Add number"
            error={valueError}
          />
        ) : (
          <TextInput
            value={stringedValue}
            error={valueError}
            onChange={handleValueChange}
            placeholder="Add value"
          />
        )}
        <Button
          className="leading-none p-2 rounded-md"
          variant="secondary"
          disabled={!fieldName || (valueType === "string" && !stringedValue && !Array.isArray(value))}
          tooltip="Save"
          icon={() => (
            <Icon icon={FiSave} className={`w-4 h-4 text-orange-500`} />
          )}
          onClick={handleSave}
        />
        <Button
          className="leading-none p-2 rounded-md"
          variant="destructive"
          tooltip="Cancel"
          icon={FiX}
          onClick={handleCancel}
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1 relative">
      {name ? (
        <div className="flex flex-wrap gap-1 group items-center">
          {children
            ? children
            : value != null && value !== ""
              ? !Array.isArray(value)
                ? typeof value === "boolean"
                  ? (
                      <Badge
                        color={value ? "green" : "gray"}
                        size="sm"
                      >
                        {value ? "Yes" : "No"}
                      </Badge>
                    )
                  : typeof value === "number"
                    ? (
                        <Badge
                          color="orange"
                          size="sm"
                        >
                          {value.toLocaleString()}
                        </Badge>
                      )
                    : String(value)
                : value.map((item: string) => (
                    <Badge
                      key={item}
                      color="orange"
                      size="sm"
                      className="cursor-pointer"
                      onClick={() => filterBy(fieldName, item)}
                    >
                      {item}
                    </Badge>
                  ))
              : `No data for ${name}`}

          <Button
            variant="light"
            className="text-gray-500 leading-none p-2 rounded-md prevent-row-click hover:bg-slate-200 [&>[role='tooltip']]:z-50 transition-opacity duration-100 opacity-0 group-hover:opacity-100"
            tooltip="Edit"
            onClick={() => setEditMode(true)}
            icon={() => (
              <Icon icon={MdModeEdit} className={`w-4 h-4 text-orange-500`} />
            )}
          />

          {onDelete && (
            <Button
              variant="light"
              className="text-gray-500 leading-none p-2 rounded-md prevent-row-click hover:bg-slate-200 [&>[role='tooltip']]:z-50 transition-opacity duration-100 opacity-0 group-hover:opacity-100"
              tooltip="Un-enrich"
              onClick={handleUnenrich}
              icon={() => (
                <Icon icon={FiTrash2} className={`w-4 h-4 text-red-500`} />
              )}
            />
          )}
        </div>
      ) : (
        <div
          className="flex gap-2 items-center cursor-pointer"
          onClick={() => setEditMode(true)}
        >
          <Badge>+</Badge> Add new field
        </div>
      )}
    </div>
  );
};