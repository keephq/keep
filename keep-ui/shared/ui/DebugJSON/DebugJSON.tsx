export function DebugJSON({
  name,
  json,
}: {
  name: string;
  json: Record<string, any>;
}) {
  return (
    <code className="text-xs leading-none text-gray-500">
      <details>
        <summary>
          <b>{name}</b>
        </summary>
        <pre>{JSON.stringify(json, null, 2)}</pre>
      </details>
    </code>
  );
}
