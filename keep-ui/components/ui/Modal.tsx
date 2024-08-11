import React from "react";
import { DialogPanel, Dialog, Title } from "@tremor/react";

export default function Modal({
  children,
  isOpen,
  onClose,
  title,
  className = "",
}: {
  children: React.ReactNode;
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  className?: string;
}) {
  return (
    <Dialog open={isOpen} onClose={onClose}>
      <DialogPanel className={`border-2 border-orange-300 rounded-lg ring-0 ${className}`}>
        {title && <Title>{title}</Title>}
        {children}
      </DialogPanel>
    </Dialog>
  );
}
