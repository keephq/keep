import { useReducer, useState } from "react";
import { GlobeIcon, PauseIcon, PlayIcon } from "@radix-ui/react-icons";
import { Badge, Button, Subtitle } from "@tremor/react";
import { getAlertLastReceieved } from "utils/helpers";
import { useAlerts } from "utils/hooks/useAlerts";
import "./alert-streamline.css";
import { Channel } from "pusher-js";

interface Props {
  pusherChannel: Channel;
  lastSubscribedDate: Date;
}

export default function AlertStreamline({
  pusherChannel,
  lastSubscribedDate,
}: Props) {
  const [isSubscribed, setIsSubscribed] = useState(true);

  const pauseOrPlay = () => {
    if (pusherChannel.subscribed) {
      pusherChannel.unsubscribe();
      return setIsSubscribed(false);
    }

    pusherChannel.subscribe();
    return setIsSubscribed(true);
  };

  return (
    <div className="flex flex-col items-end absolute right-9 top-5">
      <div>
        <Button
          icon={isSubscribed ? PauseIcon : PlayIcon}
          size="xs"
          color="orange"
          variant="light"
          tooltip="Pause/Play Alerts"
          onClick={pauseOrPlay}
          className="mr-1"
        />
        <Badge icon={GlobeIcon} color="orange" size="xs" className="w-24">
          <span className={`${isSubscribed ? "animate-ping" : ""}`}>
            &nbsp;{isSubscribed ? `Live` : "Paused"}
          </span>
        </Badge>
      </div>
      <Subtitle className="text-[10px]">
        Last received:{" "}
        {lastSubscribedDate ? getAlertLastReceieved(lastSubscribedDate) : "N/A"}
      </Subtitle>
    </div>
  );
}
