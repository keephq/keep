import { Title, Subtitle } from "@tremor/react";

export default function Layout({ children }: { children: any }) {
  return (
    <main className="p-4 md:p-10 mx-auto max-w-full">
      <Title>Extractions</Title>
      <Subtitle>
        Easily extract more attributes from your alerts using Regex
      </Subtitle>

      {children}
    </main>
  );
}
