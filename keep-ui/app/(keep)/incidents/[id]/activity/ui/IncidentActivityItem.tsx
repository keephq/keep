import { AlertSeverity } from "@/entities/alerts/ui";
import { AlertDto } from "@/entities/alerts/model";
import TimeAgo from "react-timeago";
import { FormattedContent } from "@/shared/ui/FormattedContent/FormattedContent";
import { IncidentActivity } from "../incident-activity";

// TODO: REFACTOR THIS TO SUPPORT ANY ACTIVITY TYPE, IT'S A MESS!

export function IncidentActivityItem({ activity }: { activity: IncidentActivity }) {
  const title =
    typeof activity.initiator === "string"
      ? activity.initiator
      : (activity.initiator as AlertDto)?.name;
  const subTitle =
    activity.type === "comment"
      ? " Added a comment. "
      : activity.type === "statuschange"
        ? " Incident status changed. "
        : (activity.initiator as AlertDto)?.status === "firing"
          ? " triggered"
          : " resolved" + ". ";

  // Process comment text to style mentions if it's a comment with mentions
  const processCommentText = (text: string) => {
    if (!text || activity.type !== "comment") return text;

    if (text.includes('<span class="mention">') || text.includes("<p>")) {
      return <FormattedContent format="html" content={text} />;
    }

    return text;
  };

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
        <div className="font-light text-gray-800">
          {processCommentText(activity.text)}
        </div>
      )}
    </div>
  );
}
