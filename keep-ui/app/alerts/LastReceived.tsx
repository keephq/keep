import { Subtitle } from "@tremor/react";
import moment from "moment";
import { useAlerts } from "utils/hooks/useAlerts";

export const LastRecieved = () => {
  const { useAllAlertsWithSubscription } = useAlerts();

  const { lastSubscribedDate } = useAllAlertsWithSubscription();

  return (
    <Subtitle className="text-sm col-span-2 text-right text-gray-400">
      Last received:{" "}
      {lastSubscribedDate ? moment(lastSubscribedDate).fromNow() : "N/A"}
    </Subtitle>
  );
};
