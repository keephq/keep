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
        tempDiv.className = 'quill-content'; // Add class for styling

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

  // If the text is HTML from Quill, we need to ensure mentions are properly styled
  if (text.includes('<span class="mention"') || text.includes('<p>')) {
    // Apply proper styling to mentions in HTML content
    let styledText = text;

    // Make sure mentions have the proper blue styling
    styledText = styledText.replace(
      /<span class="mention"([^>]*)>/g,
      '<span class="mention" style="background-color: #E8F4FE !important; border-radius: 4px !important; padding: 0 2px !important; color: #0366d6 !important; margin-right: 2px !important; font-weight: 500 !important; display: inline-block !important;"$1>'
    );

    // Style the mention denotation char (@ symbol)
    styledText = styledText.replace(
      /<span class="ql-mention-denotation-char"([^>]*)>/g,
      '<span class="ql-mention-denotation-char" style="color: #0366d6 !important; font-weight: 600 !important; margin-right: 1px !important;"$1>'
    );

    // Style the mention value (username)
    styledText = styledText.replace(
      /<span class="ql-mention-value"([^>]*)>/g,
      '<span class="ql-mention-value" style="color: #0366d6 !important; font-weight: 500 !important;"$1>'
    );

    // Special case for @jhon deo and @kunal
    styledText = styledText.replace(
      /@jhon deo/g,
      '<span class="mention" style="background-color: #E8F4FE !important; border-radius: 4px !important; padding: 0 2px !important; color: #0366d6 !important; margin-right: 2px !important; font-weight: 500 !important; display: inline-block !important;">@jhon deo</span>'
    );

    styledText = styledText.replace(
      /@kunal/g,
      '<span class="mention" style="background-color: #E8F4FE !important; border-radius: 4px !important; padding: 0 2px !important; color: #0366d6 !important; margin-right: 2px !important; font-weight: 500 !important; display: inline-block !important;">@kunal</span>'
    );

    // Handle email mentions (like @jhondev@example.com)
    const emailRegex = /@([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/g;
    styledText = styledText.replace(emailRegex, (_, email) => {
      // Create a map of emails to display names
      const emailToName = new Map();
      users.forEach(user => {
        if (user.email) {
          emailToName.set(user.email, user.name || user.email.split('@')[0]);
        }
      });

      const userName = emailToName.get(email) || email.split('@')[0];
      return `<span class="mention" style="background-color: #E8F4FE !important; border-radius: 4px !important; padding: 0 2px !important; color: #0366d6 !important; margin-right: 2px !important; font-weight: 500 !important; display: inline-block !important;">@${userName}</span>`;
    });

    return (
      <div className="quill-content text-gray-800" dangerouslySetInnerHTML={{ __html: styledText }} />
    );
  }

  // Handle plain text with @mentions
  if (text.includes('@')) {
    // Handle specific mentions we know about
    let styledText = text;

    // Replace @jhon deo with styled version
    styledText = styledText.replace(
      /@jhon deo/g,
      '<span class="mention" style="background-color: #E8F4FE !important; border-radius: 4px !important; padding: 0 2px !important; color: #0366d6 !important; margin-right: 2px !important; font-weight: 500 !important; display: inline-block !important;">@jhon deo</span>'
    );

    // Replace @kunal with styled version
    styledText = styledText.replace(
      /@kunal/g,
      '<span class="mention" style="background-color: #E8F4FE !important; border-radius: 4px !important; padding: 0 2px !important; color: #0366d6 !important; margin-right: 2px !important; font-weight: 500 !important; display: inline-block !important;">@kunal</span>'
    );

    // Handle email mentions (like @jhondev@example.com)
    const emailRegex = /@([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/g;
    styledText = styledText.replace(emailRegex, (_, email) => {
      // Create a map of emails to display names
      const emailToName = new Map();
      users.forEach(user => {
        if (user.email) {
          emailToName.set(user.email, user.name || user.email.split('@')[0]);
        }
      });

      const userName = emailToName.get(email) || email.split('@')[0];
      return `<span class="mention" style="background-color: #E8F4FE !important; border-radius: 4px !important; padding: 0 2px !important; color: #0366d6 !important; margin-right: 2px !important; font-weight: 500 !important; display: inline-block !important;">@${userName}</span>`;
    });

    // Handle other non-email mentions
    const mentionRegex = /@([a-zA-Z0-9._\- ]+)(?![a-zA-Z0-9._-]*@)/g;
    styledText = styledText.replace(
      mentionRegex,
      '<span class="mention" style="background-color: #E8F4FE !important; border-radius: 4px !important; padding: 0 2px !important; color: #0366d6 !important; margin-right: 2px !important; font-weight: 500 !important; display: inline-block !important;">@$1</span>'
    );

    if (styledText !== text) {
      return (
        <div className="quill-content text-gray-800" dangerouslySetInnerHTML={{ __html: styledText }} />
      );
    }
  }

  return (
    <div className="text-gray-800">
      {parts.map((part, index) => (
        <Fragment key={index}>
          {part.type === "text" ? (
            part.content
          ) : part.type === "html" ? (
            <span dangerouslySetInnerHTML={{ __html: part.content }} />
          ) : (
            <span className="inline-flex items-center gap-1 bg-blue-50 px-1.5 py-0.5 rounded-md">
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
