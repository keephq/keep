import Image from "next/image";

export default function Loading({
  includeMinHeight = true,
}: {
  includeMinHeight?: boolean;
}) {
  return (
    <main
      className={`flex items-center justify-center ${
        includeMinHeight ? "min-h-screen" : ""
      }`}
    >
      <Image
        src="/keep_loading_new.gif"
        alt="loading"
        width={200}
        height={200}
      />
    </main>
  );
}
