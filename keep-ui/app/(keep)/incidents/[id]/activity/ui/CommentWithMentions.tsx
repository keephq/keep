import { User } from "@/app/(keep)/settings/models";
import { UserStatefulAvatar } from "@/entities/users/ui/UserStatefulAvatar";
import { Fragment } from "react";

interface CommentWithMentionsProps {
  text: string;
  users: User[];
}

export function CommentWithMentions({ text, users }: CommentWithMentionsProps) {
  // Parse the text to find mentions in two formats:
  // 1. @email
  // 2. @DisplayName <email>
  const emailMentionRegex = /@([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/g;
  const nameEmailMentionRegex = /@([^<>]+) <([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})>/g;
  const parts: Array<{ type: "text" | "mention"; content: string; displayName?: string }> = [];

  let processedText = text;
  let lastIndex = 0;
  let match;

  // First, find all name+email format mentions
  while ((match = nameEmailMentionRegex.exec(text)) !== null) {
    // Add text before the mention
    if (match.index > lastIndex) {
      parts.push({
        type: "text",
        content: text.substring(lastIndex, match.index),
      });
    }

    // Add the mention with display name
    parts.push({
      type: "mention",
      content: match[2], // The email without the @ symbol
      displayName: match[1].trim() // The display name
    });

    lastIndex = match.index + match[0].length;
  }

  // If we found any name+email mentions, add any remaining text
  if (lastIndex > 0) {
    if (lastIndex < text.length) {
      parts.push({
        type: "text",
        content: text.substring(lastIndex),
      });
    }
    return parts;
  }

  // If no name+email mentions were found, look for direct email mentions
  lastIndex = 0;
  while ((match = emailMentionRegex.exec(text)) !== null) {
    // Add text before the mention
    if (match.index > lastIndex) {
      parts.push({
        type: "text",
        content: text.substring(lastIndex, match.index),
      });
    }

    // Add the mention
    parts.push({
      type: "mention",
      content: match[1], // The email without the @ symbol
    });

    lastIndex = match.index + match[0].length;
  }

  // Add any remaining text
  if (lastIndex < text.length) {
    parts.push({
      type: "text",
      content: text.substring(lastIndex),
    });
  }

  return (
    <div className="text-gray-800">
      {parts.map((part, index) => (
        <Fragment key={index}>
          {part.type === "text" ? (
            part.content
          ) : (
            <span className="inline-flex items-center gap-1 bg-gray-100 px-1.5 py-0.5 rounded-md">
              <UserStatefulAvatar email={part.content} size="xs" />
              <span className="font-medium text-blue-600">
                {part.displayName || users.find(user => user.email === part.content)?.name || part.content}
              </span>
            </span>
          )}
        </Fragment>
      ))}
    </div>
  );
}
