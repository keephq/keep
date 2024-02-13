import { Dialog, Transition } from "@headlessui/react";
import { Fragment } from "react";
import { AlertDto } from "./models";
import Modal from "@/components/ui/Modal";

interface Props {
  alert: AlertDto | null | undefined;
  handleClose: () => void;
}

export default function AlertRunWorkflowModal({ alert, handleClose }: Props) {
  /**
   *
   */
  const isOpen = !!alert;

  return (
    <Modal onClose={handleClose} isOpen={isOpen}>
      Hello World!
    </Modal>
  );
}
