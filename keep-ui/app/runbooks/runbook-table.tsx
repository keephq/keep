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

const columnsv2 = [
  columnHelperv2.display({
    id: "title",
    header: "Runbook Title",
    cell: ({ row }) => {
      return <div>{row.original.title}</div>;
    },
  }),
  columnHelperv2.display({
    id: "contents",
    header: "Contents",
    cell: ({ row }) => {
      const contents = row.original.contents || [];
      const isMoreContentAvailable = contents.length > 4;
      return (
        <div>
          {contents.slice(0, 4)?.map((content: Content) => (
            <Badge key={content.id} color="green" className="mr-2 mb-1">
              {content.file_name}
            </Badge>
          ))}
          {isMoreContentAvailable && (
            <Badge color="green" className="mr-2 mb-1">{`${
              contents.length - 4
            } more...`}</Badge>
          )}
        </div>
      );
    },
  }),
] as DisplayColumnDef<RunbookV2>[];

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
    fileData,
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

  // Modal state management

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
            data={runbooks}
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
