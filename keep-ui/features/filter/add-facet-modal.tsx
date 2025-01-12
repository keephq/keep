import React, { useState } from "react";
import { TextInput } from "@tremor/react";
import { PlusIcon } from "@heroicons/react/24/outline";
import Modal from "@/components/ui/Modal";
import { FiSearch } from "react-icons/fi";
import { CreateFacetDto } from "./models";

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
    onClose();
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Add New Facet"
      className="w-[400px]"
    >
      <div className="p-6">
        <div className="max-h-96 overflow-auto space-y-1">
        <TextInput
          icon={FiSearch}
          placeholder="Enter facet name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="mb-4"
        />
        <TextInput
          icon={FiSearch}
          placeholder="Enter facet property path"
          value={propertyPath}
          onChange={(e) => setPropertyPath(e.target.value)}
          className="mb-4"
        />
        </div>
      </div>
      <button
        onClick={() => handleNewFacetCreation()}
        className="w-full mt-2 px-2 py-1 text-sm text-gray-600 hover:bg-gray-100 rounded flex items-center gap-2"
        >
        <PlusIcon className="h-4 w-4" />
        Add Facet
        </button>
    </Modal>
  );
};
