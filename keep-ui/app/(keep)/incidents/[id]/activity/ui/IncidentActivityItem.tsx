import { AlertSeverity } from "@/entities/alerts/ui";
import { AlertDto, CommentMentionDto } from "@/entities/alerts/model";
import TimeAgo from "react-timeago";
import { useUsers } from "@/entities/users/model/useUsers";
import { User } from "@/app/(keep)/settings/models";

// TODO: REFACTOR THIS TO SUPPORT ANY ACTIVITY TYPE, IT'S A MESS!

export function IncidentActivityItem({ activity }: { activity: any }) {
  const { data: users = [] } = useUsers();

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

  // Process comment text to style mentions if it's a comment with mentions
  const processCommentText = (text: string) => {
    console.log(activity);
    if (!text || activity.type !== "comment") return text;

    // Create a map of email to name for user lookup
    const emailToName = new Map();
    users.forEach((user: User) => {
      if (user.email) {
        emailToName.set(user.email, user.name || user.email);
      }
    });

    // FIX: sanitize the text, as user can send the comment bypassing the comment input
    // If the text contains HTML (from ReactQuill), it's already formatted
    if (text.includes('<span class="mention">') || text.includes("<p>")) {
      // Sanitize HTML to prevent XSS attacks if needed
      // For a production app, consider using a library like DOMPurify

      return (
        <div
          className="quill-content"
          dangerouslySetInnerHTML={{ __html: text }}
        />
      );
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
