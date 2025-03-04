import React from "react";
import { DialogPanel, Dialog, Title, Text, Badge } from "@tremor/react";

export default function Modal({
  children,
  isOpen,
  onClose,
  title,
  beforeTitle,
  className = "",
  beta = false,
}: {
  children: React.ReactNode;
  isOpen: boolean;
  onClose: () => void;
  beforeTitle?: string;
  title?: string;
  className?: string;
  beta?: boolean;
}) {
  return (
    <Dialog open={isOpen} onClose={onClose}>
      <DialogPanel
        className={`border-2 border-orange-300 rounded-lg ring-0 ${className}`}
      >
        {title && (
          <div className="flex flex-col">
            {beforeTitle && (
              <Text className="text-sm text-gray-500">{beforeTitle}</Text>
            )}
            <Title>
              {title} {beta && <Badge color="orange">Beta</Badge>}
            </Title>
          </div>
        )}
        {children}
      </DialogPanel>
    </Dialog>
  );
}
