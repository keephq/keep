import React from "react";
import { DialogPanel, Dialog, Title, Badge } from "@tremor/react";

export default function Modal({
  children,
  isOpen,
  onClose,
  title,
  className = "",
  beta = false,
}: {
  children: React.ReactNode;
  isOpen: boolean;
  onClose: () => void;
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
          <div className="flex items-center gap-2">
            <Title>{title}</Title>
            {beta && <Badge color="orange">Beta</Badge>}
          </div>
        )}
        {children}
      </DialogPanel>
    </Dialog>
  );
}
