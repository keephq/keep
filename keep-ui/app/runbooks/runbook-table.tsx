"use client";

import React, { useEffect, useMemo, useState } from "react";
import Modal from "react-modal";
import {
  Button,
  Badge,
  Select,
  SelectItem,
  TextInput,
  Title,
  Card,
  Callout,
} from "@tremor/react";
import {
  createColumnHelper,
  DisplayColumnDef,
  Table,
} from "@tanstack/react-table";
import { GenericTable } from "@/components/table/GenericTable";
import { useRunBookTriggers } from "utils/hooks/useRunbook";
import { useForm } from "react-hook-form";
import { getApiURL } from "@/utils/apiUrl";
import useSWR, { mutate } from "swr";
import { fetcher } from "@/utils/fetcher";
import { useSession } from "next-auth/react";
import RunbookActions from "./runbook-actions";
import { RunbookDto, RunbookResponse } from "./models";
import { ExclamationCircleIcon } from "@heroicons/react/20/solid";

const customStyles = {
  content: {
    top: "50%",
    left: "50%",
    right: "auto",
    bottom: "auto",
    marginRight: "-50%",
    transform: "translate(-50%, -50%)",
    width: "400px",
  },
};

interface Content {
  id: string;
  content: string;
  link: string;
  encoding: string | null;
  file_name: string;
}
interface RunbookV2 {
  id: number;
  title: string;
  contents: Content[];
  provider_type: string;
  provider_id: string;
  repo_id: string;
  file_path: string;
}

const columnHelperv2 = createColumnHelper<RunbookV2>();
const extractMetadataFromMarkdown = (markdown) => {
  const charactersBetweenGroupedHyphens = /^---([\s\S]*?)---/;
  const metadataMatched = markdown.match(charactersBetweenGroupedHyphens);
  const metadata = metadataMatched[1];

  if (!metadata) {
    return {};
  }

  const metadataLines = metadata.split("\n");
  const metadataObject = metadataLines.reduce((accumulator, line) => {
    const [key, ...value] = line.split(":").map((part) => part.trim());

    if (key)
      accumulator[key] = value[1] ? value.join(":") : value.join("");
    return accumulator;
  }, {});

  return metadataObject;
};

const columnsv2 = [
  columnHelperv2.display({
    id: "title",
    header: "Runbook Title",
    cell: ({ row }) => {
      const titles = row.original.contents.map(content => {
        let decodedContent = Buffer.from(content.content, "base64").toString("utf-8");
        console.log(decodedContent);
        // const decodedContent = content.decode("utf8");
        // const metadata = extractMetadataFromMarkdown(decodedContent);
        // return metadata.title || row.original.title; 
      });
      return <div></div>; 
    },
  }),
  columnHelperv2.display({
    id: "content",
    header: "File Name",
    cell: ({ row }) => (
      <Badge key={row.original.id} color="green" className="mr-2 mb-1">
      {console.log("from inside row", row)}
        {
        row.original.file_name}
      </Badge>
    ),
  }),
] as DisplayColumnDef<RunbookV2>[];

const flattenRunbookData = (runbooks: RunbookV2[]) => {
  return runbooks.flatMap((runbook) =>
    runbook.contents.map((content) => ({
      ...runbook,
      file_name: content.file_name,
      content_id: content.id,
    }))
  );
};
function SettingsPage({handleRunbookMutation}:{
  handleRunbookMutation: () => void}) {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const { register, handleSubmit, reset, getValues, setValue, watch } =
    useForm();
  const [refresh, setRefresh] = useState(0);
  const [openPreview, setOpenPreview] = useState(false);

  const {
    runBookInstalledProviders,
    reposData,
    handleSubmit: submitHandler,
    provider,
  } = useRunBookTriggers(getValues(), refresh, setIsModalOpen);

  const selectedProviderId = watch(
    "providerId",
    provider?.details?.authentication?.provider_id ?? ""
  );
  const selectedRepo = watch(
    "repoName",
    provider?.details?.authentication?.repository ?? ""
  );

  useEffect(() => {
    setValue(
      "repoName",
      reposData?.legnth ? provider?.details?.authentication.repository : ""
    );
    setOpenPreview(false);
  }, [reposData]);

  const openModal = () => {
    reset(); // Reset form when opening modal
    setIsModalOpen(true);
    setOpenPreview(false);
  };

  const closeModal = (openPreview?: boolean) => {
    setIsModalOpen(false);
    if (openPreview) {
      setOpenPreview(true);
    } else {
      setOpenPreview(false);
    }
  };

  const onSubmit = (data: any) => {
    submitHandler(data, handleRunbookMutation);
  };

  const handleProviderChange = (value: string) => {
    setValue("repoName", "");
    setValue("providerId", value);
    setRefresh((prev) => prev + 1);
  };

  return (
    <div>
      <Button onClick={openModal}>Settings</Button>
      <Modal
        isOpen={isModalOpen}
        onRequestClose={() => closeModal()}
        style={customStyles}
        contentLabel="Settings Modal"
      >
        <h2>Runbook Settings</h2>
        <form onSubmit={handleSubmit(onSubmit)}>
          <div className="space-y-4 w-full my-4 h-full overflow-hidden">
            <div>
              <Select
                onValueChange={handleProviderChange}
                placeholder="Select Provider"
                required={true}
                value={selectedProviderId}
              >
                <SelectItem key={"provider_select"} value="">
                  Select Provider
                </SelectItem>
                {runBookInstalledProviders?.map((provider) => {
                  return (
                    <SelectItem key={provider.id} value={provider.id}>
                      {provider?.details?.name}
                    </SelectItem>
                  );
                })}
              </Select>
            </div>
            <div>
              <Select
                onValueChange={(value: string) => {
                  setValue("repoName", value);
                }}
                placeholder="Select Repo"
                value={selectedRepo}
              >
                <SelectItem key={"repo_select"} value="">
                  Select Repo
                </SelectItem>
                {reposData.map((repo: any) => (
                  <SelectItem key={repo.option_value} value={repo.option_value}>
                    {repo.display_name}
                  </SelectItem>
                ))}
              </Select>
            </div>
            <div>
              <TextInput
                {...register("runBookTitle")}
                placeholder="Enter Runbook Title"
                required
              />
            </div>
            <div>
              <TextInput
                {...register("pathToMdFile")}
                placeholder="Enter path to markdown files"
                required
              />
            </div>
          </div>
          <div style={{ textAlign: "right" }}>
            <Button
              type="button"
              onClick={() => closeModal()}
              style={{ marginRight: "10px" }}
            >
              Cancel
            </Button>
            <Button type="submit" color="blue">
              Query
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}

function RunbookIncidentTable() {
  const [offset, setOffset] = useState(0);
  const [limit, setLimit] = useState(10);
  const { data: session, status } = useSession();

  let shouldFetch = session?.accessToken ? true : false;

  const { data: runbooksData, error, isLoading } = useSWR<RunbookResponse>(
    shouldFetch
      ? `${getApiURL()}/runbooks?limit=${limit}&offset=${offset}`
      : null,
    (url: string) => {
      return fetcher(url, session?.accessToken!);
    }
  );
  const handleRunbookMutation = ()=>{
    mutate(`${getApiURL()}/runbooks?limit=${limit}&offset=${0}`);
  }

  const { total_count, runbooks } = runbooksData || {
    total_count: 0,
    runbooks: [],
  };
  const flattenedData = flattenRunbookData(runbooks || []);
  const handlePaginationChange = (newLimit: number, newOffset: number) => {
    setLimit(newLimit);
    setOffset(newOffset);
  };

  const getActions = (table: Table<RunbookDto>, selectedRowIds: string[]) => {
    return (
      <RunbookActions
        selectedRowIds={selectedRowIds}
        runbooks={runbooks || []}
        clearRowSelection={table.resetRowSelection}
      />
    );
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-between items-center">
        <Title>Runbook</Title>
        <SettingsPage handleRunbookMutation={handleRunbookMutation}/>
      </div>
      <Card className="flex-grow">
        {!isLoading && !error && (
          <GenericTable<RunbookDto>
          data={flattenedData}
            columns={columnsv2}
            rowCount={total_count}
            offset={offset}
            limit={limit}
            onPaginationChange={handlePaginationChange}
            onRowClick={(row) => {
              console.log("Runbook clicked:", row);
            }}
            getActions={getActions}
            isRowSelectable={true}
          />
        )}
        {error && (
          <Callout title={""}>
            <ExclamationCircleIcon className="h-6 w-6 text-red-600" />
            Something went wrong. please try again or reach out support team.
          </Callout>
        )}
      </Card>
    </div>
  );
}

export default RunbookIncidentTable;
