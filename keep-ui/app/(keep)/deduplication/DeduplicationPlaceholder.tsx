import { Card, Subtitle, Title } from "@tremor/react";
import { DeduplicationSankey } from "./DeduplicationSankey";
import Link from "next/link";

export const DeduplicationPlaceholder = () => {
  return (
    <>
      <Card className="flex flex-col items-center justify-center gap-y-8 h-full">
        <div className="text-center space-y-3">
          <Title className="text-2xl">No Deduplications Yet</Title>
          <Subtitle className="text-gray-400">
            Alert deduplication is the first layer of denoising. It groups
            similar alerts from one source.
            <br /> To connect alerts across sources into incidents, check{" "}
            <Link href="/rules" className="underline text-orange-500">
              Correlations
            </Link>
          </Subtitle>
          <Subtitle className="text-gray-400">
            This page will become active once the first alerts are registered.
          </Subtitle>
        </div>
        <DeduplicationSankey className="max-w-full" />
      </Card>
    </>
  );
};
