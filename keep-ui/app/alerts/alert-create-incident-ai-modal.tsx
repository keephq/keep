import Modal from "@/components/ui/Modal";
import { Button, Title } from "@tremor/react";
import { useSession } from "next-auth/react";
import { useState } from "react";
import { toast } from "react-toastify";
import { getApiURL } from "../../utils/apiUrl";
import Loading from "../loading";
import { AlertDto } from "./models"; // Assuming you have an AI animation component

interface CreateIncidentWithAIModalProps {
  isOpen: boolean;
  handleClose: () => void;
  alerts: Array<AlertDto>;
}

const CreateIncidentWithAIModal = ({
  isOpen,
  handleClose,
  alerts,
}: CreateIncidentWithAIModalProps) => {
  const [isLoading, setIsLoading] = useState(false);
  const { data: session } = useSession();

  const createIncidentWithAI = async () => {
    setIsLoading(true);
    const apiUrl = getApiURL();
    try {
      const response = await fetch(`${apiUrl}/incidents/create-with-ai`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session?.accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(alerts.map(({ fingerprint }) => fingerprint)),
      });

      if (response.ok) {
        const incident = await response.json();
        toast.success("Incident created successfully with AI");
        handleClose();
        // You might want to do something with the created incident here
      } else {
        toast.error(
          "Failed to create incident with AI, please try again later."
        );
      }
    } catch (error) {
      console.error("Error creating incident with AI:", error);
      toast.error("An unexpected error occurred. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Create Incident with AI"
      className="w-[600px]"
    >
      <div className="relative bg-white p-6 rounded-lg">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center">
            <Loading />
            <Title className="mt-4">Creating incident with AI...</Title>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center gap-y-8 h-full">
            <div className="text-center space-y-3">
              <Title className="text-2xl">Create New Incident with AI</Title>
              <p>
                AI will analyze {alerts.length} alert
                {alerts.length > 1 ? "s" : ""} and create an incident based on
                the analysis.
              </p>
            </div>

            <Button
              className="w-full"
              color="green"
              onClick={createIncidentWithAI}
            >
              Create incident with AI
            </Button>
          </div>
        )}
      </div>
    </Modal>
  );
};

export default CreateIncidentWithAIModal;
