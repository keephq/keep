import { Status } from "@/app/incidents/models";
import { useApiUrl } from "@/utils/hooks/useConfig";
import { useSession } from "next-auth/react";
import { useCallback } from "react";
import { toast } from "react-toastify";
import { useSWRConfig } from "swr";

type UseIncidentActionsValue = {
  changeStatus: (
    incidentId: string,
    status: Status,
    comment?: string
  ) => Promise<void>;
};

export function useIncidentActions(): UseIncidentActionsValue {
  const apiUrl = useApiUrl();
  const { data: session } = useSession();
  const { mutate } = useSWRConfig();

  const changeStatus = useCallback(
    async (incidentId: string, status: Status, comment?: string) => {
      if (!status) {
        toast.error("Please select a new status.");
        return;
      }

      try {
        const response = await fetch(
          `${apiUrl}/incidents/${incidentId}/status`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${session?.accessToken}`,
            },
            body: JSON.stringify({
              status,
              comment,
            }),
          }
        );

        if (response.ok) {
          toast.success("Incident status changed successfully!");
          mutate(`${apiUrl}/incidents`);
        } else {
          toast.error("Failed to change incident status.");
        }
      } catch (error) {
        toast.error("An error occurred while changing incident status.");
      }
    },
    []
  );

  return {
    changeStatus,
  };
}
