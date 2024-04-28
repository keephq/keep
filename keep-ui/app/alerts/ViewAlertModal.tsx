import { AlertDto } from "./models"; // Adjust the import path as needed
import Modal from "@/components/ui/Modal"; // Ensure this path matches your project structure
import { Button } from "@tremor/react";
import { toast } from "react-toastify";

interface ViewAlertModalProps {
  alert: AlertDto | null | undefined;
  handleClose: () => void;
}

export const ViewAlertModal: React.FC<ViewAlertModalProps> = ({ alert, handleClose }) => {
  const isOpen = !!alert;

  const handleCopy = async () => {
    if (alert) {
      try {
        await navigator.clipboard.writeText(JSON.stringify(alert, null, 2));
        toast.success("Alert copied to clipboard!");
      } catch (err) {
        toast.error("Failed to copy alert.");
      }
    }
  };

  return (
    <Modal onClose={handleClose} isOpen={isOpen} className="overflow-visible max-w-fit">
  <div className="flex justify-between items-center mb-4">
    <h2 className="text-lg font-semibold">Alert Details</h2>
    <div className="flex gap-x-2"> {/* Adjust gap as needed */}
      <Button onClick={handleCopy} color="orange">
        Copy to Clipboard
      </Button>
      <Button onClick={handleClose} color="orange" variant="secondary">
        Close
      </Button>
    </div>
  </div>
  {alert && (
    <pre className="p-2 bg-gray-100 rounded mt-2 overflow-auto">
      {JSON.stringify(alert, null, 2)}
    </pre>
  )}
</Modal>

  );
};
