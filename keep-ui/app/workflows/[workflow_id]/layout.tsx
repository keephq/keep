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
      <div className="flex items-center mb-4 max-h-full">
        <Link
          href="/workflows"
          className="flex items-center text-gray-500 hover:text-gray-700"
        >
          <ArrowLeftIcon className="h-5 w-5 mr-1" /> Back to Workflows
        </Link>
      </div>
      <div className="overflow-auto">{children}</div>
    </>
  );
}
