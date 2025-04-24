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
