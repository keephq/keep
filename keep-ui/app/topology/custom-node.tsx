import React, { useEffect } from "react";
import { Handle, Position } from "@xyflow/react";
import { useAlerts } from "utils/hooks/useAlerts";
import { Service } from "./models";
import { useAlertPolling } from "utils/hooks/usePusher";

const CustomNode = ({ data }: { data: Service }) => {
  const { useAllAlerts } = useAlerts();
  const { data: alerts, mutate } = useAllAlerts("feed");
  const { data: pollAlerts } = useAlertPolling();

  useEffect(() => {
    if (pollAlerts) {
      mutate();
    }
  }, [pollAlerts, mutate]);

  const relevantAlerts = alerts?.filter((alert) => alert.service === data.id);

  const handleClick = () => {
    // router.push(
    //   `/alerts/feed?cel=service%3D%3D${encodeURIComponent(`${data.id}`)}`
    // );
  };

  const alertCount = relevantAlerts?.length || 0;
  const badgeColor = alertCount < 5 ? "bg-orange-500" : "bg-red-500";

  return (
    <div
      onClick={handleClick}
      className="bg-white p-4 border rounded-xl shadow-lg relative"
    >
      <strong className="text-lg">{data.id}</strong>
      {alertCount > 0 && (
        <span
          className={`absolute top-[-20px] right-[-20px] mt-2 mr-2 px-2 py-1 text-white text-xs font-bold rounded-full ${badgeColor}`}
        >
          {alertCount}
        </span>
      )}
      <Handle type="source" position={Position.Right} id="right" />
      <Handle type="target" position={Position.Left} id="left" />
    </div>
  );
};

export default CustomNode;
