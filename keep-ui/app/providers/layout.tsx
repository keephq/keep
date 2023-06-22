import { Subtitle, Title } from "@tremor/react";

export default function ProvidersLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  console.log("ProvidersLayout");
  return (
    <main className="p-4 md:p-10 mx-auto max-w-7xl">
      <Title>Providers</Title>
      <Subtitle>Connect providers to Keep to make your alerts better.</Subtitle>
      {children}
    </main>
  );
}
