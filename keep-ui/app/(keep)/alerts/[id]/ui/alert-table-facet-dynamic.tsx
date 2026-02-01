import React, { useState } from "react";
import { TextInput } from "@tremor/react";
import { TrashIcon } from "@heroicons/react/24/outline";
import { FacetProps } from "./alert-table-facet-types";
import { AlertDto } from "@/entities/alerts/model";
import { Facet } from "./alert-table-facet";
import Modal from "@/components/ui/Modal";
import { Table } from "@tanstack/table-core";
import { FiSearch } from "react-icons/fi";

interface AddFacetModalProps {
  isOpen: boolean;
  onClose: () => void;
  table: Table<AlertDto>;
  onAddFacet: (column: string) => void;
  existingFacets: string[];
}

export const AddFacetModal: React.FC<AddFacetModalProps> = ({
  isOpen,
  onClose,
  table,
  onAddFacet,
  existingFacets,
}) => {
  const [searchTerm, setSearchTerm] = useState("");

  const availableColumns = table
    .getAllColumns()
    .filter(
      (col) =>
        // Filter out pinned columns and existing facets
        !col.getIsPinned() &&
        !existingFacets.includes(col.id) &&
        // Filter by search term
        col.id.toLowerCase().includes(searchTerm.toLowerCase())
    )
    .map((col) => col.id);

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Add New Facet"
      className="w-[400px]"
    >
      <div className="p-6">
        <TextInput
          icon={FiSearch}
          placeholder="Search columns..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="mb-4"
        />
        <div className="max-h-96 overflow-auto space-y-1">
          {availableColumns.map((column) => (
            <button
              key={column}
              onClick={() => {
                onAddFacet(column);
                onClose();
              }}
              className="w-full text-left px-4 py-2 hover:bg-gray-100 rounded"
            >
              {column}
            </button>
          ))}
        </div>
      </div>
    </Modal>
  );
};

export interface DynamicFacetProps extends FacetProps {
  onDelete: () => void;
}

export const DynamicFacetWrapper: React.FC<DynamicFacetProps> = ({
  onDelete,
  ...facetProps
}) => {
  return (
    <div className="relative">
      <button
        onClick={onDelete}
        className="absolute right-2 top-2 p-1 text-gray-400 hover:text-gray-600"
      >
        <TrashIcon className="h-4 w-4" />
      </button>
      <Facet showIcon={false} {...facetProps} />
    </div>
  );
};
