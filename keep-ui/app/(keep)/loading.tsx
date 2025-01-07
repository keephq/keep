import { Subtitle, Title } from "@tremor/react";
import Image from "next/image";

export default function Loading({
  includeMinHeight = true,
  slowLoading = false,
  loadingText = "Just a second, getting your data 🚨",
}: {
  includeMinHeight?: boolean;
  slowLoading?: boolean;
  loadingText?: string;
}) {
  return (
    <main
      className={`flex flex-col items-center justify-center ${
        includeMinHeight ? "min-h-screen-minus-200" : ""
      }`}
    >
      <Image
        className="animate-bounce -my-10"
        src="/keep.svg"
        alt="loading"
        width={200}
        height={200}
      />
      <Title>{loadingText}</Title>
      {slowLoading && (
        <Subtitle>
          This is taking a bit longer then usual, please wait...
        </Subtitle>
      )}
    </main>
  );
}
