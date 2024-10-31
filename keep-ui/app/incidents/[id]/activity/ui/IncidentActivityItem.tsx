import AlertSeverity from "@/app/alerts/alert-severity";
import { AlertDto } from "@/app/alerts/models";
import TimeAgo from "react-timeago";

export function IncidentActivityItem({ activity }: { activity: any }) {
  const title =
    typeof activity.initiator === "string"
      ? activity.initiator
      : activity.initiator?.name;
  const subTitle =
    typeof activity.initiator === "string"
      ? " Added a comment. "
      : (activity.initiator?.status === "firing" ? " triggered" : " resolved") +
        ". ";
  return (
    <div className="relative h-full w-full flex items-center">
      {activity.type === "alert" &&
        (activity.initiator as AlertDto)?.severity && (
          <AlertSeverity
            severity={(activity.initiator as AlertDto).severity}
            marginLeft={false}
          />
        )}
      <span className="font-semibold mr-2.5">{title}</span>
      <span className="text-gray-300">
        {subTitle} <TimeAgo date={activity.timestamp + "Z"} />
      </span>
      {activity.text && (
        <div className="absolute top-14 font-light text-gray-800">
          {activity.text}
        </div>
      )}
    </div>
  );
}
