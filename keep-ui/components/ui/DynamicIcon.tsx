export function DynamicIcon({
  providerType,
  width = "24px",
  height = "24px",
  color = "none",
  ...props
}: {
  providerType: string;
  width?: string;
  height?: string;
  color?: string;
}) {
  const handleImageError = (event: any) => {
    event.target.href.baseVal = "/icons/keep-icon.png";
  };

  return (
    <svg
      width={width}
      height={height}
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
      fill={color}
      {...props}
    >
      <image
        id="image0"
        width="24"
        height="24"
        href={`/icons/${providerType}-icon.png`}
        onError={handleImageError}
      />
    </svg>
  );
}
