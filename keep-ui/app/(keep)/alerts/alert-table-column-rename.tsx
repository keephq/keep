import React, { useState, useRef, useEffect } from "react";
import { CheckIcon, PencilIcon } from "@heroicons/react/24/outline";
import { TextInput, Button } from "@tremor/react";

// Type definition for column rename mapping
export type ColumnRenameMapping = Record<string, string>;

/**
 * Column rename submenu component for dropdown menu
 */
export const ColumnRenameSubMenu = ({
  columnId,
  columnRenameMapping,
  setColumnRenameMapping,
  DropdownMenu,
}: {
  columnId: string;
  columnRenameMapping: ColumnRenameMapping;
  setColumnRenameMapping: (mapping: ColumnRenameMapping) => void;
  DropdownMenu: any;
}) => {
  // Get original column name from the column ID (capitalize and replace underscores)
  const getOriginalName = () => {
    return columnId
      .split(/[._]/)
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");
  };

  const originalName = getOriginalName();
  const [newName, setNewName] = useState(
    columnRenameMapping[columnId] || originalName
  );
  const [isEditing, setIsEditing] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // Focus the input when editing starts
  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  // Function to handle rename submission
  const handleRename = () => {
    if (newName.trim() && newName.trim() !== originalName) {
      setColumnRenameMapping({
        ...columnRenameMapping,
        [columnId]: newName.trim(),
      });
    } else {
      // If empty or same as original, remove the mapping
      const updatedMapping = { ...columnRenameMapping };
      delete updatedMapping[columnId];
      setColumnRenameMapping(updatedMapping);
    }
    setIsEditing(false);
  };

  // Function to reset to original name
  const resetToOriginal = () => {
    const updatedMapping = { ...columnRenameMapping };
    delete updatedMapping[columnId];
    setColumnRenameMapping(updatedMapping);
    setNewName(originalName);
    setIsEditing(false);
  };

  // Prevent event propagation to keep dropdown open
  const stopPropagation = (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
  };

  // Let's go back to using the Menu approach which works better with the DropdownMenu component
  return (
    <DropdownMenu.Menu
      icon={PencilIcon}
      label={
        columnRenameMapping[columnId] ? "Edit column name" : "Rename column"
      }
      nested={true}
      iconClassName="text-gray-900 group-hover:text-orange-500"
    >
      <div className="px-3 py-2" onClick={stopPropagation}>
        <div className="mb-1 text-xs border-orange-500 text-gray-500">
          {columnRenameMapping[columnId]
            ? "Edit column name:"
            : "Enter new column name:"}
        </div>
        <div className="flex items-center">
          <TextInput
            ref={inputRef}
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder={originalName}
            className="flex-1 mr-2"
            onClick={stopPropagation}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                handleRename();
              } else if (e.key === "Escape") {
                setIsEditing(false);
                setNewName(columnRenameMapping[columnId] || originalName);
              }
              e.stopPropagation();
            }}
            autoFocus
          />
          <Button
            onClick={(e) => {
              e.stopPropagation();
              handleRename();
            }}
            size="xs"
            color="orange"
          >
            Save
          </Button>
        </div>
      </div>
    </DropdownMenu.Menu>
  );
};

/**
 * Create column rename menu items for dropdown menu
 */
export const createColumnRenameMenuItems = (
  columnId: string,
  columnRenameMapping: ColumnRenameMapping,
  setColumnRenameMapping: (mapping: ColumnRenameMapping) => void,
  DropdownMenu: any
) => {
  const hasCustomName = !!columnRenameMapping[columnId];

  return (
    <>
      <ColumnRenameSubMenu
        columnId={columnId}
        columnRenameMapping={columnRenameMapping}
        setColumnRenameMapping={setColumnRenameMapping}
        DropdownMenu={DropdownMenu}
      />
      {hasCustomName && (
        <DropdownMenu.Item
          icon={CheckIcon}
          label="Reset to original name"
          onClick={() => {
            const updatedMapping = { ...columnRenameMapping };
            delete updatedMapping[columnId];
            setColumnRenameMapping(updatedMapping);
          }}
        />
      )}
    </>
  );
};

/**
 * Get the display name for a column based on rename mapping
 */
export const getColumnDisplayName = (
  columnId: string,
  originalName: string,
  columnRenameMapping: ColumnRenameMapping
): string => {
  return columnRenameMapping[columnId] || originalName;
};
