import { Card, Title } from "@tremor/react";
import Image from "next/image";

export function SignInLoader({ text }: { text: string }) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-tremor-background-subtle p-4">
      <Card
        className="w-full max-w-md p-8"
        decoration="top"
        decorationColor="orange"
      >
        <div className="flex flex-col items-center gap-6">
          <div className="relative w-32 h-32">
            <Image
              className="object-contain"
              src="/keep_big.svg"
              alt="Keep Logo"
              width={96}
              height={96}
              priority
            />
          </div>
          <Title>{text}</Title>
        </div>
      </Card>
    </div>
  );
}
