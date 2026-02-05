/**
 * Initiates a client-side file download from a string
 * 
 * @param options - Configuration options
 * @param options.data - The string content to be downloaded as a file
 * @param options.filename - The name to give the downloaded file
 * @param options.contentType - The MIME type of the file (e.g., "text/plain", "application/json")
 * 
 * @example
 * // Download JSON data
 * downloadFileFromString({
 *   data: JSON.stringify({ key: "value" }, null, 2),
 *   filename: "data.json",
 *   contentType: "application/json"
 * });
 * 
 * @example
 * // Download plain text
 * downloadFileFromString({
 *   data: "Hello, world!",
 *   filename: "hello.txt",
 *   contentType: "text/plain"
 * });
 * 
 * @remarks
 * This function creates a temporary URL object and cleans it up after download initiation.
 * It must be called in response to a user action (like a click) due to browser security restrictions.
 */
export function downloadFileFromString({
  data,
  filename,
  contentType,
}: {
  data: string;
  filename: string;
  contentType: string;
}) {
  const blob = new Blob([data], { type: contentType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;

  try {
    link.click();
  } catch (error) {
    console.error("Error downloading file", error);
  } finally {
    URL.revokeObjectURL(url);
  }
}
