"use client";

import { Link } from "@/components/ui";
import { Title, Button, Subtitle } from "@tremor/react";
import Image from "next/image";
import { useRouter } from "next/navigation";

export default function NotAuthorized({ message }: { message?: string }) {
  const router = useRouter();
  return (
    <div className="flex flex-col items-center justify-center h-full">
      <Title>403 Not Authorized</Title>
      <div className="flex flex-col items-center">
        <Subtitle>
          {message || "You do not have permission to access this page."}
        </Subtitle>
        <Subtitle>
          <br />
          If you need help, please contact us on{" "}
          <Link
            href="https://slack.keephq.dev/"
            target="_blank"
            rel="noopener noreferrer"
          >
            Slack
          </Link>
        </Subtitle>
      </div>
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
