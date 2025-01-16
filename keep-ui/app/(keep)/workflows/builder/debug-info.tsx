import { CustomEdgeProps } from "./CustomEdge";
import { FlowNode } from "./types";

const WF_DEBUG_INFO = true;

export function DebugNodeInfo({ id, data }: Pick<FlowNode, "id" | "data">) {
  if (!WF_DEBUG_INFO) {
    return null;
  }
  return (
    <div className="flex flex-col absolute top-0 bottom-0 my-auto right-0 translate-x-[calc(100%+20px)]">
      <div
        className={`h-fit bg-black text-pink-500 font-mono text-[10px] px-1 py-1`}
      >
        {id}
      </div>
      <details className="bg-black text-pink-500 font-mono text-[10px] px-1 py-1">
        <summary>data=</summary>
        <pre className="text-xs leading-none text-gray-500">
          {JSON.stringify(data, null, 2)}
        </pre>
      </details>
    </div>
  );
}

export function DebugEdgeInfo({
  id,
  source,
  labelX,
  labelY,
  target,
  isLayouted,
}: Pick<CustomEdgeProps, "id" | "source" | "target"> & {
  labelX: number;
  labelY: number;
  isLayouted: boolean;
}) {
  if (!WF_DEBUG_INFO) {
    return null;
  }
  return (
    <div
      className={`absolute bg-black text-green-500 font-mono text-[10px] px-1 py-1`}
      style={{
        transform: `translate(0, -50%) translate(${labelX + 30}px, ${labelY}px)`,
        pointerEvents: "none",
        opacity: isLayouted ? 1 : 0,
      }}
    >
      {id}
    </div>
  );
}
