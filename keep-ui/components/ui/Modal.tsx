import { DialogPanel, Dialog } from "@tremor/react";
export default function Modal({
  children,
  isOpen,
  onClose,
}: {
  children: React.ReactNode;
  isOpen: boolean;
  onClose: () => void;
}) {
  return (
    <Dialog open={isOpen} onClose={onClose}>
      <DialogPanel>{children}</DialogPanel>
    </Dialog>
  );
}
