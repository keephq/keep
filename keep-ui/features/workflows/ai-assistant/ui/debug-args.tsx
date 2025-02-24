import { FlowNode } from "@/entities/workflows";

export function DebugArgs({
  args,
  nodes,
}: {
  args: Record<string, any>;
  nodes: FlowNode[];
}) {
  return (
    <>
      <code className="text-xs leading-none text-gray-500">
        {/* {JSON.stringify(args, null, 2)} */}
        args=
        {Object.entries(args).map(([k, v]) => (
          <p key={k}>
            <b>{k}</b>= {JSON.stringify(v, null, 2)}
          </p>
        ))}
        all_nodes=
        {nodes.map((n) => `${n.data.id}:${n.data.type}`).join(", ")}
      </code>
    </>
    /* <code className="text-xs leading-none text-gray-500">
                  {JSON.stringify(definition.value, null, 2)}
                </code> */
  );
}
