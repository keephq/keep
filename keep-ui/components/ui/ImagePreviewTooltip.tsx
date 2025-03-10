import { createPortal } from "react-dom";

export type TooltipPosition = { x: number; y: number } | null;

// Add the ImagePreviewTooltip component
export const ImagePreviewTooltip = ({
  imageUrl,
  position,
}: {
  imageUrl: string;
  position: TooltipPosition;
}) => {
  if (!position) return null;

  return createPortal(
    <div
      className="absolute shadow-lg rounded border border-gray-100 z-50"
      style={{
        left: position.x,
        top: position.y,
        pointerEvents: "none",
      }}
    >
      <div className="p-1 bg-gray-200">
        {/* because we'll have to start managing every external static asset url (datadog/grafana/etc.) */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={imageUrl}
          alt="Preview"
          className="max-w-xs max-h-64 object-contain"
        />
      </div>
    </div>,
    document.body
  );
};
