import React, { useState } from "react";
import { TextInput } from "@tremor/react";
import { PlusIcon } from "@heroicons/react/24/outline";
import Modal from "@/components/ui/Modal";
import { FiSearch } from "react-icons/fi";
import { CreateFacetDto } from "./models";
import { Button } from "@/components/ui";

interface AddFacetModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAddFacet: (createFacet: CreateFacetDto) => void;
}

export const AddFacetModal: React.FC<AddFacetModalProps> = ({
  isOpen,
  onClose,
  onAddFacet
}) => {
  const [name, setName] = useState("");
  const [propertyPath, setPropertyPath] = useState("");

  const handleNewFacetCreation = () => {
    onAddFacet({
      property_path: propertyPath,
      name: name
    })
    close();
  }

  const close = () => {
    setName("");
    setPropertyPath("");
    onClose();
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Add New Facet"
      className="w-[400px]"
    >
      <div className="mt-3 max-h-96 overflow-auto space-y-1">
        <div>
          <div className="mb-1">
            <span className="font-bold">Facet name</span>
          </div>
          
          <TextInput
            placeholder="Enter facet name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="mb-4"
          />
        </div>
        <div>
          <div className="mb-1">
            <span className="font-bold">Facet property path</span>
          </div>
          
          <TextInput
            placeholder="Enter facet property path"
            value={propertyPath}
            onChange={(e) => setPropertyPath(e.target.value)}
            className="mb-4"
          />
        </div>
      </div>
      <div className="flex flex-1 justify-end gap-2">
        <Button
          color="orange"
          size="xs"
          variant="secondary"
          onClick={close}
        >
          Cancel
        </Button>
        <Button
          color="orange"
          size="xs"
          variant="primary"
          type="submit"
          onClick={() => handleNewFacetCreation()}
        >
          Create
        </Button>
      </div>
    </Modal>
  );
};
