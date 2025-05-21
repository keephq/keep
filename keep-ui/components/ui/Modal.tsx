import React from "react";
import { DialogPanel, Dialog, Text, Badge, Button } from "@tremor/react";
import { XMarkIcon } from "@heroicons/react/24/outline";
import { PageTitle } from "@/shared/ui/PageTitle";

export default function Modal({
  children,
  isOpen,
  onClose,
  title,
  beforeTitle,
  className = "",
  beta = false,
  description,
}: {
  children: React.ReactNode;
  isOpen: boolean;
  onClose: () => void;
  beforeTitle?: string;
  title?: string;
  className?: string;
  beta?: boolean;
  description?: string;
}) {
  return (
    <Dialog open={isOpen} onClose={onClose}>
      <DialogPanel
        className={`flex flex-col border-2 border-orange-300 rounded-lg ring-0 ${className}`}
      >
        {title && (
          <header className="flex flex-col mb-4">
            {beforeTitle && (
              <Text className="text-sm text-gray-500">{beforeTitle}</Text>
            )}
            <div className="flex flex-row items-center justify-between gap-2">
              <PageTitle>
                {title}
                {beta && <Badge color="orange">Beta</Badge>}
              </PageTitle>
              <Button
                variant="light"
                color="gray"
                size="xl"
                className="aspect-square p-1 hover:bg-gray-100 hover:dark:bg-gray-400/10 rounded"
                icon={XMarkIcon}
                onClick={(e) => {
                  e.preventDefault();
                  onClose();
                }}
              />
            </div>
            {description && (
              <Text className="text-sm text-gray-500">{description}</Text>
            )}
          </header>
        )}
        <div className="flex flex-col flex-1 min-h-0">{children}</div>
      </DialogPanel>
    </Dialog>
  );
}
