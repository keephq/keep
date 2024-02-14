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
      <DialogPanel className={className}>
        {title && <Title>{title}</Title>}
        {children}
      </DialogPanel>
    </Dialog>
  );
}
