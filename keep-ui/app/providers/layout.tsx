import { Title } from "@tremor/react";

export default function ProvidersLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <main className="p-4">
      <Title className="mb-8 ml-5">Providers</Title>
      <div className="flex flex-col">{children}</div>
    </main>
  );
}
