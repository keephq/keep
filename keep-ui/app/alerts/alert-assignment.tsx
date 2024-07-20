import { getApiURL } from "../../utils/apiUrl";
import { AlertDto } from "./models";
import {Session} from "next-auth";

interface assignEndpointProps {
  unassign: boolean;
  alert: AlertDto;
  session: Session | null;
  mutate: () => void;
}

export const callAssignEndpoint = async (props : assignEndpointProps) => {
  const apiUrl = getApiURL();
  const {unassign, alert, session, mutate} = props;

  const res = await fetch(
    `${apiUrl}/alerts/${alert.fingerprint}/assign/${alert.lastReceived.toISOString()}?unassign=${unassign}`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${session!.accessToken}`,
        "Content-Type": "application/json",
      },
    }
  );
  if (res.ok) {
    await mutate();
  }
};
