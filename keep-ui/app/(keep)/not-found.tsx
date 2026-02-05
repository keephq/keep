"use client";

import { Link } from "@/components/ui";
import { Title, Button, Subtitle } from "@tremor/react";
import Image from "next/image";
import { useRouter } from "next/navigation";

export default function NotFound() {
  const router = useRouter();
  return (
    <div className="flex flex-col items-center justify-center h-full">
      <Title>404 Page not found</Title>
      <Subtitle>
        If you believe this is an error, please contact us on{" "}
        <Link
          href="https://slack.keephq.dev/"
          target="_blank"
          rel="noopener noreferrer"
        >
          Slack
        </Link>
      </Subtitle>
      <Image src="/keep.svg" alt="Keep" width={150} height={150} />
      <Button
        onClick={() => {
          router.back();
        }}
        color="orange"
        variant="secondary"
      >
        Go back
      </Button>
    </div>
  );
}
