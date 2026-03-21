import { useI18n } from "@/i18n/hooks/useI18n";
import { Card, Text } from "@tremor/react";
import Image from "next/image";
import { NextIntlClientProvider } from "next-intl";
import { getMessages } from "next-intl/server";

export const metadata = {
  title: "Keep",
  description: "The open-source alert management and AIOps platform",
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const messages = await getMessages();

  return (
    <html lang="en" className="bg-tremor-background-subtle">
      <body>
        <NextIntlClientProvider messages={messages}>
          <div className="min-h-screen flex items-center justify-center bg-tremor-background-subtle p-4">
            <div className="flex flex-col items-center gap-6">
              <div className="flex items-center gap-3">
                <Image
                  src="/keep_big.svg"
                  alt="Keep Logo"
                  width={48}
                  height={48}
                  priority
                  className="object-contain h-full"
                />
                <Text className="text-tremor-title font-bold text-tremor-content-strong">
                  Keep
                </Text>
              </div>
              <Card
                className="w-full max-w-md p-8 min-w-96 flex flex-col gap-6 items-center"
                decoration="top"
                decorationColor="orange"
              >
                {children}
              </Card>
            </div>
          </div>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
