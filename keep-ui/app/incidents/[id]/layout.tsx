import { Card } from "@tremor/react";

export default function Layout({ children }: { children: any }) {
  return (
    <Card className="flex flex-col items-center justify-center gap-y-8">
      {children}
    </Card>
  );
}
