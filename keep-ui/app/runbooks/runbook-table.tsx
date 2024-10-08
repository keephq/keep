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
} from "@tremor/react";
import { createColumnHelper, DisplayColumnDef } from "@tanstack/react-table";
import { GenericTable } from "@/components/table/GenericTable";
import { useRunBookTriggers } from "utils/hooks/useRunbook";
import { useForm, get } from "react-hook-form";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { getApiURL } from "@/utils/apiUrl";
import useSWR from "swr";
import { fetcher } from "@/utils/fetcher";
import { useSession } from "next-auth/react";

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
  encoding: string|null;
  file_name: string;
}
interface RunbookV2 {
  id: number;
  title: string;
  contents:Content[],
  provider_type: string,
  provider_id: string
  repo_id: string
  file_path: string
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
      return (
        <div>
          {row.original.contents?.map((content: Content) => (
            <Badge key={content.id} color="green" className="mr-2 mb-1">
              {content.file_name}
            </Badge>
          ))}
        </div>
      );
    },
  }),
] as DisplayColumnDef<RunbookV2>[];

// function PreviewContent({type, data}:{type:string, data:string}){
//   const [isModalOpen, setIsModalOpen] = useState(open);

//   // const closeModal = () => {
//   //   setIsModalOpen(false);
//   // };
//   const decodeBase64 = (encodedContent:string) => {
//     // Use atob to decode the Base64 string and then handle UTF-8 encoding
//     return encodedContent ? decodeURIComponent(atob(encodedContent)) : '';
//   };
//   return <div className={`w-full h-full p-10`}>

//   <Markdown remarkPlugins={[remarkGfm]}>
//           {decodeBase64(data)}
//         </Markdown>
//   </div>
// }

// TO DO: Need to work on styling
function SettingsPage() {
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
  } = useRunBookTriggers(getValues(), refresh);

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
    submitHandler(data); // Call the submit handler with form data
    // closeModal(); // Close modal after submit
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
              {/* <label>Choose Provider</label> */}
              <Select
                onValueChange={handleProviderChange} // Update the form value manually on change
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
          {/* <div style={{ textAlign: "left" }}>
            <Button
              type="button"
              onClick={()=>{closeModal(true)}}
              style={{ marginRight: "10px" }}
            >
              Preview
            </Button>
           
          </div> */}
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
      {/* {fileData?.content && openPreview &&<PreviewContent  type="markdown" data={fileData?.content} />} */}
    </div>
  );
}

function RunbookIncidentTable() {
  const [offset, setOffset] = useState(0);
  const [limit, setLimit] = useState(10);
  const { data: session, status } = useSession();


  let shouldFetch = session?.accessToken ? true : false;

  const { data: runbooksData, error } = useSWR<RunbookV2[]>(
    shouldFetch ? `${getApiURL()}/runbooks` : null,
    (url:string) => {
      return fetcher(url, session?.accessToken!);
    }, 
  );

  // Modal state management

  const handlePaginationChange = (newLimit: number, newOffset: number) => {
    setLimit(newLimit);
    setOffset(newOffset);
  };

  return (
    <div className="flex flex-col h-full gap-4">
      <div className="flex justify-between items-center h-[10%]">
        <Title>Runbook</Title>
        <SettingsPage />
      </div>
      <Card className="flex-1 overflow-auto">
        {runbooksData && <GenericTable<RunbookV2>
          data={runbooksData}
          columns={columnsv2}
          rowCount={runbooksData.length}
          offset={offset}
          limit={limit}
          onPaginationChange={handlePaginationChange}
          onRowClick={(row) => {
            console.log("Runbook clicked:", row);
          }}
        />}
      </Card>
    </div>
  );
}

export default RunbookIncidentTable;
