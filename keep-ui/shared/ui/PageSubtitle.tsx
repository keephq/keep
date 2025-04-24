import { Subtitle } from "@tremor/react";

export const PageSubtitle = ({ children }: { children: React.ReactNode }) => {
  return <Subtitle className="text-gray-700">{children}</Subtitle>;
};
