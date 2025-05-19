/**
 * Extracts tagged user IDs from Quill editor content
 * This is called when a comment is submitted to get the final list of mentions
 *
 * @param content - HTML content from the Quill editor
 * @returns Array of user IDs that were mentioned in the content
 */
export function extractTaggedUsers(content: string): string[] {
  const mentionRegex = /data-id="([^"]+)"/g;
  const matches = content.match(mentionRegex) || [];

  return matches
    .map((match) => {
      const idMatch = match.match(/data-id="([^"]+)"/);
      return idMatch ? idMatch[1] : null;
    })
    .filter(Boolean) as string[];
}
