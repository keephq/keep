import { GlobeIcon, PauseIcon, PlayIcon } from "@radix-ui/react-icons";
import { Badge, Button, Subtitle } from "@tremor/react";
import { Channel } from "pusher-js";
import { getAlertLastReceieved } from "utils/helpers";
import "./alert-streamline.css";
import { useState } from "react";

interface Props {
  channel: Channel | null;
  lastReceivedAlertDate: Date | undefined;
}

export default function AlertStreamline({
  channel,
  lastReceivedAlertDate,
}: Props) {
  const [subscribed, setSubscribed] = useState(true);

  function pauseOrPlay() {
    if (channel?.subscribed) {
      channel?.unsubscribe();
      setSubscribed(false);
    } else {
      channel?.subscribe();
      setSubscribed(true);
    }
  }

  return (
    <div className="flex flex-col items-end absolute right-9 top-5">
      <div>
        <Button
          icon={subscribed ? PauseIcon : PlayIcon}
          size="xs"
          color="orange"
          variant="light"
          tooltip="Pause/Play Alerts"
          onClick={pauseOrPlay}
          className="mr-1"
        />
        <Badge
          icon={GlobeIcon}
          color="orange"
          size="xs"
          className="w-24"
        >
          <span className={`${subscribed ? "animate-ping" : ""}`}>
            &nbsp;{subscribed ? `Live` : "Paused"}
          </span>
        </Badge>
      </div>
      <Subtitle className="text-[10px]">
        Last received:{" "}
        {lastReceivedAlertDate
          ? getAlertLastReceieved(lastReceivedAlertDate)
          : "N/A"}
      </Subtitle>
    </div>
  );
}
