import { Subtitle, Title } from "@tremor/react";
import clsx from "clsx";
import Image from "next/image";

export function KeepLoader({
  includeMinHeight = true,
  slowLoading = false,
  loadingText = "Just a second, getting your data 🚨",
  className,
  ...props
}: {
  includeMinHeight?: boolean;
  slowLoading?: boolean;
  loadingText?: string;
} & React.HTMLAttributes<HTMLDivElement>) {
  return (
    <main
      className={clsx(
        "flex flex-col items-center justify-center",
        includeMinHeight ? "min-h-screen-minus-200" : "",
        className
      )}
      {...props}
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
