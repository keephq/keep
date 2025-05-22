/**
 * Extracts tagged user IDs from Quill editor content
 * This is called when a comment is submitted to get the final list of mentions
 *
 * @param content - HTML content from the Quill editor
 * @returns Array of user IDs that were mentioned in the content
 */
export function extractTaggedUsers(content: string): string[] {
  const mentionRegex = /data-id="([^"]+)"/g;
  const ids = Array.from(content.matchAll(mentionRegex)).map(match => match[1]) || [];
  return ids;
}
