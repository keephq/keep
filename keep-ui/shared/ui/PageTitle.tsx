import { Title } from "@tremor/react";
import clsx from "clsx";
export const PageTitle = ({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) => {
  return (
    <Title className={clsx("text-xl line-clamp-2 font-[600]", className)}>
      {children}
    </Title>
  );
};
