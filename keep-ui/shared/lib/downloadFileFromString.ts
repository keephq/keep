export function downloadFileFromString({
  data,
  filename,
  contentType,
}: {
  data: string;
  filename: string;
  contentType: string;
}) {
  var blob = new Blob([data], { type: contentType });
  var url = URL.createObjectURL(blob);
  var link = document.createElement("a");
  link.href = url;
  link.download = filename;

  link.click();

  URL.revokeObjectURL(url);
}
