export function JsonCard({
  title,
  json,
}: {
  title: string;
  json: Record<string, any>;
}) {
  return (
    <pre className="bg-gray-100 rounded-md overflow-hidden text-xs my-2">
      <div className="text-gray-500 bg-gray-50 p-2">{title}</div>
      <div className="overflow-auto max-h-48 break-words whitespace-pre-wrap p-2">
        {JSON.stringify(json, null, 2)}
      </div>
    </pre>
  );
}
