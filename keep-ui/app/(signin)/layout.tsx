import { Card } from "@tremor/react";
import Image from "next/image";

export const metadata = {
  title: "Keep",
  description: "The open-source alert management and AIOps platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="bg-tremor-background-subtle">
      <body>
        <div className="min-h-screen flex items-center justify-center bg-tremor-background-subtle p-4">
          <Card
            className="w-full max-w-md p-8"
            decoration="top"
            decorationColor="orange"
          >
            <div className="flex flex-col items-center gap-6">
              <div className="relative w-32 h-32">
                <Image
                  src="/keep_big.svg"
                  alt="Keep Logo"
                  width={128}
                  height={128}
                  priority
                  className="object-contain h-full"
                />
              </div>
              {children}
            </div>
          </Card>
        </div>
      </body>
    </html>
  );
}
