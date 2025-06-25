import React, {useState} from "react";
import {Button} from "@/components/ui";
import {Icon, TextInput, NumberInput, Switch} from "@tremor/react";
import {MdModeEdit} from "react-icons/md";
import {map, some, startCase} from "lodash";
import {FiSave, FiTrash2, FiX} from "react-icons/fi";
import Modal from "@/components/ui/Modal";
import {FieldHeader} from "@/shared/ui";

interface EnrichmentEditableFormProps {
  fields: Record<string, string | number | boolean>;
  title: string,
  onUpdate: (fields: Record<string, string | number | boolean>) => void;
  onDelete?: (fields: string[]) => void;
  children: React.ReactNode;
}

export const EnrichmentEditableForm = ({fields, title, onUpdate, onDelete, children}: EnrichmentEditableFormProps) => {

  const [isFormOpen, setIsFormOpen] = useState(false);
  const [newFields, setNewFields] = useState<Record<string, string | number | boolean>>(fields);

  const handleOpenForm = () => {
    setIsFormOpen(true);
  }

  const handleCloseForm = () => {
    setIsFormOpen(false);
  }

  const handleValueChange = (key: string, value: string | number | boolean) => {
    setNewFields({
        ...newFields,
        [key]: value
      });
  }

  const handleSave = async () => {
    onUpdate(newFields);
    setIsFormOpen(false);
  }

  const handleCancel = () => {
    setIsFormOpen(false);
    setNewFields(fields);
  }

  const renderFieldInput = (key: string, value: string | number | boolean) => {
    if (typeof value === "boolean") {
      return (
        <div className="flex items-center gap-2">
          <Switch
            id={`switch-${key}`}
            checked={value}
            onChange={(checked) => handleValueChange(key, checked)}
          />
          <label htmlFor={`switch-${key}`} className="text-sm">
            {value ? "Yes" : "No"}
          </label>
        </div>
      );
    } else if (typeof value === "number") {
      return (
        <NumberInput
          value={value}
          onValueChange={(val) => handleValueChange(key, val ?? 0)}
          placeholder={`Add ${key}`}
        />
      );
    } else {
      return (
        <TextInput
          value={value}
          onChange={(e) => handleValueChange(key, e.target.value)}
          placeholder={`Add ${key}`}
        />
      );
    }
  };

  return <>

    <div className="flex gap-2 items-center group">

      {children}

      <Button
        variant="light"
        className="text-gray-500 leading-none p-2 rounded-md prevent-row-click hover:bg-slate-200 [&>[role='tooltip']]:z-50 transition-opacity duration-100 opacity-0 group-hover:opacity-100"
        tooltip="Edit"
        onClick={handleOpenForm}
        icon={() => (
          <Icon
            icon={MdModeEdit}
            className={`w-4 h-4 text-orange-500`}
          />
        )}
      />

      {(onDelete && some(Object.values(fields))) && <Button
        variant="light"
        className="text-gray-500 leading-none p-2 rounded-md prevent-row-click hover:bg-slate-200 [&>[role='tooltip']]:z-50 transition-opacity duration-100 opacity-0 group-hover:opacity-100"
        tooltip="Un-enrich"
        onClick={() => onDelete(Object.keys(fields))}
        icon={() => (
          <Icon
            icon={FiTrash2}
            className={`w-4 h-4 text-red-500`}
          />
        )}
      />}
    </div>

    <Modal
      isOpen={isFormOpen}
      onClose={handleCloseForm}
      className="w-[600px]"
      title={title}
    >
      {map(fields, (value: string | number | boolean, key: string) => {
        return <div key={key}>
          <FieldHeader>{startCase(key)}</FieldHeader>
          {renderFieldInput(key, value)}
        </div>
      })}

      <div className="flex gap-2 justify-end">
        <Button
          className="leading-none p-2 rounded-md"
          variant="secondary"
          disabled={!some(Object.values(newFields), (val) => val !== "" && val !== null && val !== undefined)}
          tooltip="Save"
          icon={() => <Icon
            icon={FiSave}
            className={`w-4 h-4 text-orange-500`}
          />}
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

    </Modal>
  </>
}