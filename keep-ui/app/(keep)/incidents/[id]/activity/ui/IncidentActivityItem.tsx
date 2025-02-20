import AlertSeverity from "@/app/(keep)/alerts/alert-severity";
import { AlertDto } from "@/entities/alerts/model";
import TimeAgo from "react-timeago";

// TODO: REFACTOR THIS TO SUPPORT ANY ACTIVITY TYPE, IT'S A MESS!

export function IncidentActivityItem({ activity }: { activity: any }) {
  const title =
    typeof activity.initiator === "string"
      ? activity.initiator
      : activity.initiator?.name;
  const subTitle =
    activity.type === "comment"
      ? " Added a comment. "
      : activity.type === "statuschange"
      ? " Incident status changed. "
      : activity.initiator?.status === "firing"
      ? " triggered"
      : " resolved" + ". ";
  return (
    <div className="relative h-full w-full flex flex-col">
      <div className="flex items-center gap-2">
        {activity.type === "alert" &&
          (activity.initiator as AlertDto)?.severity && (
            <AlertSeverity
              severity={(activity.initiator as AlertDto).severity}
            />
          )}
        <span className="font-semibold mr-2.5">{title}</span>
        <span className="text-gray-300">
          {subTitle} <TimeAgo date={activity.timestamp + "Z"} />
        </span>
      </div>
      {activity.text && (
        <div className="font-light text-gray-800">{activity.text}</div>
      )}
    </div>
  );
}
