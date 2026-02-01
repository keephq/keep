import clsx from "clsx";
import "./vertical-rounded-list.css";

export function VerticalRoundedList({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={clsx("flex flex-col vertical-rounded-list", className)}>
      {children}
    </div>
  );
}
