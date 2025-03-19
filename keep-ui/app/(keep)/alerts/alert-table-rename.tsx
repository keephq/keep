import { DropdownMenu } from "@/shared/ui";
import { PencilIcon } from "@heroicons/react/24/outline";
import { Dialog } from "@headlessui/react";
import { TextInput, Button } from "@tremor/react";
import { useState } from "react";

interface RenameColumnDialogProps {
  isOpen: boolean;
  columnId: string;
  currentName: string;
  onClose: () => void;
  onRename: (columnId: string, newName: string) => void;
}

export const RenameColumnDialog = ({
  isOpen,
  columnId,
  currentName,
  onClose,
  onRename,
}: RenameColumnDialogProps) => {
  const [newName, setNewName] = useState(currentName);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (newName.trim()) {
      onRename(columnId, newName.trim());
      onClose();
    }
  };

  return (
    <Dialog open={isOpen} onClose={onClose} className="relative z-50">
      <div className="fixed inset-0 bg-black/30" aria-hidden="true" />
      <div className="fixed inset-0 flex items-center justify-center p-4">
        <Dialog.Panel className="mx-auto max-w-sm rounded bg-white p-4">
          <Dialog.Title className="text-lg font-medium mb-4">
            Rename Column
          </Dialog.Title>
          <form onSubmit={handleSubmit}>
            <TextInput
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Enter new name"
              autoFocus
            />
            <div className="mt-4 flex justify-end gap-2">
              <Button variant="secondary" onClick={onClose}>
                Cancel
              </Button>
              <Button type="submit" color="orange">
                Rename
              </Button>
            </div>
          </form>
        </Dialog.Panel>
      </div>
    </Dialog>
  );
};

export const createRenameColumnMenuItem = (
  columnId: string,
  columnHeader: string,
  getColumnName: (columnId: string, defaultName: string) => string,
  setRenamingColumn: (columnId: string | null) => void,
  setNewColumnName: (name: string) => void,
  DropdownMenu: typeof DropdownMenu
) => {
  return (
    <DropdownMenu.Item
      icon={PencilIcon}
      label="Rename Column"
      onClick={(e) => {
        e.stopPropagation();
        setRenamingColumn(columnId);
        setNewColumnName(getColumnName(columnId, columnHeader));
      }}
    />
  );
};
