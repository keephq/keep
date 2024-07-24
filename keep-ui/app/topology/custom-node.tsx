import React from "react";
import { Handle, Position } from "@xyflow/react";
import { useAlerts } from "utils/hooks/useAlerts";
import { useRouter } from "next/navigation";
import { Service } from "./models";

const CustomNode = ({ data }: { data: Service }) => {
  const { useAllAlerts } = useAlerts();
  const { data: alerts } = useAllAlerts("feed");
  const router = useRouter();

  const relevantAlerts = alerts?.filter(
    (alert) => alert.service === data.display_name
  );

  const handleClick = () => {
    // router.push(
    //   `/alerts/feed?cel=service%3D%3D${encodeURIComponent(`${data.id}`)}`
    // );
  };

  return (
    <div
      onClick={handleClick}
      className="bg-white p-4 border rounded-xl shadow-lg relative"
    >
      <strong className="text-lg">{data.id}</strong>
      <Handle type="source" position={Position.Right} id="right" />
      <Handle type="target" position={Position.Left} id="left" />
    </div>
  );
};

export default CustomNode;
