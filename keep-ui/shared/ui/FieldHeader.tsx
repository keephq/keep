import clsx from "clsx";

export const FieldHeader = ({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) => (
  <h3 className={clsx("text-sm text-gray-500 font-semibold", className)}>
    {children}
  </h3>
);
