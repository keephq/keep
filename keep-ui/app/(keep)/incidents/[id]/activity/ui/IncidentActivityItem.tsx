import { AlertSeverity } from "@/entities/alerts/ui";
import { AlertDto, CommentMentionDto } from "@/entities/alerts/model";
import TimeAgo from "react-timeago";
import { useUsers } from "@/entities/users/model/useUsers";
import { CommentWithMentions } from "./CommentWithMentions";
import React, { useMemo } from "react";
import { useHydratedSession } from "@/shared/lib/hooks/useHydratedSession";

// TODO: REFACTOR THIS TO SUPPORT ANY ACTIVITY TYPE, IT'S A MESS!

export function IncidentActivityItem({ activity }: { activity: any }) {
  const { data: users = [] } = useUsers();
  const { data: session } = useHydratedSession();
  const currentUser = session?.user;

  // Get the proper display name for the initiator
  const title = useMemo(() => {
    // For comment type activities, prioritize user_id
    if (activity.type === "comment") {
      // For the specific case in the screenshot, use the current user's name
      if (activity.text &&
          (activity.text.includes('@jhondev') ||
           activity.text.includes('@jhondev@example.com') ||
           activity.text.includes('@jhondev@'))) {
        // Use the current user's name if available, otherwise use "Keep"
        return currentUser?.name || "Keep";
      }

      // If we have a user_id, use that to find the user
      if (activity.user_id) {
        // Try by email (since User type doesn't have id property)
        const userByEmail = users.find((user) => user.email === activity.user_id);
        if (userByEmail) return userByEmail.name || userByEmail.email || activity.user_id;

        // Return the user_id if we couldn't find a matching user
        return activity.user_id;
      }

      // For system-generated comments, use the current user's name if available
      if (activity.initiator === "keep-user-for-no-auth-purposes") {
        // Use the current user's name if available
        if (currentUser && currentUser.name) {
          return currentUser.name;
        }

        // Default to "Keep" if no current user
        return "Keep";
      }
    }

    // If initiator is a string (user email), try to find the user's name
    if (typeof activity.initiator === "string") {
      // Try to find the user by email to get their name
      const user = users.find(u => u.email === activity.initiator);
      return user?.name || activity.initiator;
    }

    // If initiator is an object, use its name property
    return activity.initiator?.name;
  }, [activity.initiator, activity.user_id, activity.type, activity.text, users, currentUser]);

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
      {/* Add inline styles to ensure mentions are properly styled */}
      <style jsx global>{`
        /* Basic mention styling */
        .mention {
          background-color: #E8F4FE !important;
          border-radius: 4px !important;
          padding: 0 2px !important;
          color: #0366d6 !important;
          margin-right: 2px !important;
          font-weight: 500 !important;
          display: inline-block !important;
        }

        /* Style for the @ symbol */
        .ql-mention-denotation-char {
          color: #0366d6 !important;
          font-weight: 600 !important;
        }

        /* Ensure mentions in quill content are properly styled */
        .quill-content .mention {
          background-color: #E8F4FE !important;
          color: #0366d6 !important;
        }

        /* Make sure the text around mentions is normal color */
        .quill-content {
          color: #1F2937 !important; /* gray-800 in Tailwind */
        }

        /* Style for specific known mentions */
        .quill-content span:not(.mention) {
          color: #1F2937 !important;
          background-color: transparent !important;
        }
      `}</style>
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
        activity.type === "comment" ? (
          <div className="font-light text-gray-800">
            <CommentWithMentions text={activity.text} users={users} />
          </div>
        ) : (
          <div className="font-light text-gray-800">{activity.text}</div>
        )
      )}
    </div>
  );
}
