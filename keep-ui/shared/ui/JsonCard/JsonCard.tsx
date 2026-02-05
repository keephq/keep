import { MonacoEditor } from "@/shared/ui";

export function JsonCard({
  title,
  json,
  maxHeight = 192,
  readOnly = true,
}: {
  title: string;
  json: Record<string, any>;
  maxHeight?: number;
  readOnly?: boolean;
}) {
  const stringifiedJson = JSON.stringify(json, null, 2);
  const lines = stringifiedJson.split("\n");
  const lineCount = lines.length;
  const height = Math.min(lineCount * 20 + 16, maxHeight);

  return (
    <pre className="bg-gray-100 rounded-md text-xs my-2 overflow-hidden">
      <div className="text-gray-500 bg-gray-50 p-2">{title}</div>
      <div
        className="overflow-auto bg-[#fffffe] break-words whitespace-pre-wrap py-2 border rounded-[inherit] rounded-t-none  border-gray-200"
        style={{
          height,
        }}
      >
        <MonacoEditor
          value={stringifiedJson}
          language="json"
          theme="vs-light"
          options={{
            readOnly,
            minimap: { enabled: false },
            scrollBeyondLastLine: false,
            fontSize: 12,
            lineNumbers: "off",
            folding: true,
            wordWrap: "on",
          }}
        />
      </div>
    </pre>
  );
}
