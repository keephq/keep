import { User } from "@/app/(keep)/settings/models";
import { UserStatefulAvatar } from "@/entities/users/ui/UserStatefulAvatar";
import { Fragment, useEffect, useState } from "react";

interface CommentWithMentionsProps {
  text: string;
  users: User[];
}

export function CommentWithMentions({ text, users }: CommentWithMentionsProps) {
  const [parts, setParts] = useState<Array<{ type: "text" | "mention" | "html"; content: string; displayName?: string; email?: string }>>([]);

  useEffect(() => {
    // Function to parse the HTML content and extract mentions
    const parseContent = () => {
      const parsedParts: Array<{ type: "text" | "mention" | "html"; content: string; displayName?: string; email?: string }> = [];

      // Check if the text is HTML (from Quill editor)
      if (text.includes('<span class="mention"') || text.includes('<p>')) {
        // Create a temporary div to parse the HTML
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = text;

        // Process the HTML content
        processNode(tempDiv, parsedParts);
      } else {
        // Handle plain text with mentions in two formats:
        // 1. @email
        // 2. @DisplayName <email>
        const emailMentionRegex = /@([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/g;
        const nameEmailMentionRegex = /@([^<>]+) <([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})>/g;

        let lastIndex = 0;
        let match;

        // First, find all name+email format mentions
        while ((match = nameEmailMentionRegex.exec(text)) !== null) {
          // Add text before the mention
          if (match.index > lastIndex) {
            parsedParts.push({
              type: "text",
              content: text.substring(lastIndex, match.index),
            });
          }

          // Add the mention with display name
          parsedParts.push({
            type: "mention",
            content: match[1].trim(), // The display name
            email: match[2], // The email
          });

          lastIndex = match.index + match[0].length;
        }

        // If we found any name+email mentions, add any remaining text
        if (lastIndex > 0) {
          if (lastIndex < text.length) {
            parsedParts.push({
              type: "text",
              content: text.substring(lastIndex),
            });
          }
        } else {
          // If no name+email mentions were found, look for direct email mentions
          lastIndex = 0;
          while ((match = emailMentionRegex.exec(text)) !== null) {
            // Add text before the mention
            if (match.index > lastIndex) {
              parsedParts.push({
                type: "text",
                content: text.substring(lastIndex, match.index),
              });
            }

            // Add the mention
            parsedParts.push({
              type: "mention",
              content: match[1], // The display name (same as email in this case)
              email: match[1], // The email
            });

            lastIndex = match.index + match[0].length;
          }

          // Add any remaining text
          if (lastIndex < text.length) {
            parsedParts.push({
              type: "text",
              content: text.substring(lastIndex),
            });
          }
        }
      }

      setParts(parsedParts);
    };

    // Function to recursively process HTML nodes
    const processNode = (node: Node, parts: Array<{ type: "text" | "mention" | "html"; content: string; displayName?: string; email?: string }>) => {
      if (node.nodeType === Node.TEXT_NODE) {
        // Text node
        if (node.textContent && node.textContent.trim()) {
          parts.push({
            type: "text",
            content: node.textContent,
          });
        }
      } else if (node.nodeType === Node.ELEMENT_NODE) {
        const element = node as HTMLElement;

        // Check if this is a mention span
        if (element.classList && element.classList.contains('mention')) {
          const email = element.getAttribute('data-id');
          const value = element.getAttribute('data-value') || element.textContent;

          if (email) {
            parts.push({
              type: "mention",
              content: value || email,
              email: email,
            });
          } else {
            // Fallback if data attributes are not available
            parts.push({
              type: "html",
              content: element.outerHTML,
            });
          }
        } else {
          // Process child nodes
          for (let i = 0; i < node.childNodes.length; i++) {
            processNode(node.childNodes[i], parts);
          }
        }
      }
    };

    parseContent();
  }, [text]);

  return (
    <div className="text-gray-800">
      {parts.map((part, index) => (
        <Fragment key={index}>
          {part.type === "text" ? (
            part.content
          ) : part.type === "html" ? (
            <span dangerouslySetInnerHTML={{ __html: part.content }} />
          ) : (
            <span className="inline-flex items-center gap-1 bg-gray-100 px-1.5 py-0.5 rounded-md">
              <UserStatefulAvatar email={part.email || part.content} size="xs" />
              <span className="font-medium text-blue-600">
                {part.content || part.displayName || users.find(user => user.email === (part.email || part.content))?.name || part.email || part.content}
              </span>
            </span>
          )}
        </Fragment>
      ))}
    </div>
  );
}
