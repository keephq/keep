"use client";
import { ArrowLeftIcon } from "@radix-ui/react-icons";
import Link from "next/link";

export default function Layout({
  children,
  params,
}: {
  children: any;
  params: { workflow_id: string };
}) {
  return (
    <>
      <div className="flex flex-col mb-4 h-full gap-6">
        <Link
          href="/workflows"
          className="flex items-center text-gray-500 hover:text-gray-700"
        >
          <ArrowLeftIcon className="h-5 w-5 mr-1" /> Back to Workflows
        </Link>
        <div className="flex-1 overflow-auto h-full">{children}</div>
      </div>
    </>
  );
}
