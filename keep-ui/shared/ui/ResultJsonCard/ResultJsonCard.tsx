export function ResultJsonCard({ result }: { result: Record<string, any> }) {
  return (
    <pre className="bg-gray-100 rounded-md overflow-hidden text-xs my-2">
      <div className="text-gray-500 bg-gray-50 p-2">result</div>
      <div className="overflow-auto max-h-48 break-words whitespace-pre-wrap p-2">
        {JSON.stringify(result, null, 2)}
      </div>
    </pre>
  );
}
