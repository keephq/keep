import React from "react";
import { CircleStackIcon } from "@heroicons/react/24/outline";
import { Callout, Italic, Button } from "@tremor/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { MdArrowForwardIos } from "react-icons/md";
import { IoMdCard } from "react-icons/io";
import Image from "next/image";
import { useConfig } from "utils/hooks/useConfig";

const DetailsSection = () => {
  const router = useRouter();
  const { data: configData } = useConfig();
  const docsUrl = configData?.KEEP_DOCS_URL || "https://docs.keephq.dev";

  const links = [
    {
      href: `${docsUrl}/platform/workflows`,
      label: "Learn more about Workflows",
    },
    {
      href: `${docsUrl}/workflows/overview`,
      label: "How to create a basic notification flow",
    },
    {
      href: "https://slack.keephq.dev",
      label: "Get support on your Workflow",
    },
  ];

  return (
    <section className="flex flex-col items-center justify-center mb-10">
      <Image
        src="/icons/workflow-icon.png"
        alt="loading"
        width={200}
        height={200}
      />
      <h2 className="sm:text-2xl  text-xl font-bold">
        Create your first workflow
      </h2>
      <p className="mt-2 font-bold text-sm">
        You do not have any workflow added yet.
      </p>
      <div className="text-sm mt-4 text-gray-500 max-w-md text-center">
        Start from scratch, or browse through workflow templates
      </div>
      <Button
        className="mt-4 px-6 py-2"
        color="orange"
        variant="primary"
        onClick={() => {
          router.push("/workflows/builder");
        }}
      >
        Create a new workflow
      </Button>
      <div className="mt-10 divide-y flex flex-col border border-gray-200 rounded bg-white shadow text-sm">
        {links.map((link) => (
          <a
            key={link.href}
            href={link.href}
            target="_blank"
            className="flex items-center p-2 bg-white hover:bg-gray-100 transition cursor-pointer gap-4"
          >
            <div className="flex flex-row items-center gap-2">
              <IoMdCard className="w-4 h-4 text-gray-500" />
              <p className="truncate">{link.label}</p>
            </div>
            <span className="ml-auto flex items-center">
              <MdArrowForwardIos className="w-4 h-4 text-gray-500 ml-2" />
            </span>
          </a>
        ))}
      </div>
    </section>
  );
};

const WorkflowsEmptyState = ({ isNewUI }: { isNewUI?: boolean }) => {
  const loadAlert = () =>
    document.getElementById("uploadWorkflowButton")?.click();

  if (isNewUI) {
    return (
      <div className="mt-4">
        <DetailsSection />
      </div>
    );
  }

  return (
    <div className="text-center mt-4">
      <Callout
        title="No Workflows"
        icon={CircleStackIcon}
        color="yellow"
        className="mt-5"
      >
        You can start by uploading a workflow file using the{" "}
        <Italic onClick={loadAlert} className="underline cursor-pointer">
          Load a Workflow
        </Italic>{" "}
        button above or by using the{" "}
        <Italic className="underline">
          <Link href="/workflows/builder">Workflow Builder</Link>
        </Italic>{" "}
        to create a new workflow.
      </Callout>
    </div>
  );
};

export default WorkflowsEmptyState;
