import { AlertDto, Status } from "app/alerts/models";
import { useSession } from "next-auth/react";
import { getApiURL } from "utils/apiUrl";

const post = async (path: string, accessToken: string | null, body: any = null) => {
  return await fetch(`${getApiURL()}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
    body,
  });
}

export const useAlertActions = () => {
  const { data: session } = useSession();

  const changeAlertStatusRequest = async (
    alert: AlertDto,
    selectedStatus: Status,
  ): Promise<Response> => {
    console.log("changeAlertStatusRequest", alert, selectedStatus);
    const path = `/alerts/enrich?dispose_on_new_alert=true`;
    const body = JSON.stringify({
      enrichments: {
        status: selectedStatus,
      },
      fingerprint: alert.fingerprint,
    });
    return await post(path, session?.accessToken, body);
  };

  const selfAssignAlertRequest = async (alert: AlertDto): Promise<Response> => {
    console.log("selfAssignAlertRequest", alert);
    const path = `/alerts/${alert.fingerprint}/assign/${alert.lastReceived.toISOString()}`;
    return await post(path, session?.accessToken, null);
  }

  return {
    changeAlertStatusRequest,
    selfAssignAlertRequest,
  }
};
