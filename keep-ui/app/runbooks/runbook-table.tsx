"use client";

import React, { useEffect, useMemo, useState } from "react";
import Modal from "react-modal";
import { Button, Badge } from "@tremor/react";
import { createColumnHelper, DisplayColumnDef } from "@tanstack/react-table";
import { GenericTable } from "@/components/table/GenericTable";
import { useSession } from "next-auth/react";
import { useProviders } from "utils/hooks/useProviders";
import { ProvidersResponse, Provider } from "app/providers/providers";
import { set } from "date-fns";
import { useRunBookTriggers } from "utils/hooks/useRunbook";
import { useForm, get } from "react-hook-form";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

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

interface Incident {
  id: number;
  name: string;
}

interface Runbook {
  id: number;
  title: string;
  incidents: Incident[];
}

const runbookData = [
  {
    id: 1,
    title: "Database Recovery",
    incidents: [
      { id: 101, name: "DB Outage on 2024-01-01" },
      { id: 102, name: "DB Backup Failure" },
    ],
  },
  {
    id: 2,
    title: "API Health Check",
    incidents: [{ id: 201, name: "API Latency Issue" }],
  },
  {
    id: 3,
    title: "Server Restart Guide",
    incidents: [
      { id: 301, name: "Unexpected Server Crash" },
      { id: 302, name: "Scheduled Maintenance" },
    ],
  },
] as Runbook[];

const columnHelper = createColumnHelper<Runbook>();

const columns = [
  columnHelper.display({
    id: "title",
    header: "Runbook Title",
    cell: ({ row }) => {
      return <div>{row.original.title}</div>;
    },
  }),
  columnHelper.display({
    id: "incidents",
    header: "Incdients",
    cell: ({ row }) => {
      return (
        <div>
          {row.original.incidents?.map((incident: Incident) => (
            <Badge key={incident.id} color="green" className="mr-2 mb-1">
              {incident.name}
            </Badge>
          ))}
        </div>
      );
    },
  }),
] as DisplayColumnDef<Runbook>[];

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
  const { register, handleSubmit, reset, getValues, setValue } = useForm();
  const [refresh, setRefresh] = useState(0);
  const [openPreview, setOpenPreview] = useState(false);
  const {
    runBookInstalledProviders,
    reposData,
    handleSubmit: submitHandler,
    provider,
    fileData,
  } = useRunBookTriggers(getValues(), refresh);

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
          <div>
            <label>Choose Provider</label>
            <select
              {...register("providerId")}
              style={{ width: "100%", padding: "8px", marginBottom: "10px" }}
              onChange={(e) => {
                setValue("providerId", e.target.value);
                setRefresh((prev) => prev + 1);
              }}
            >
              <option value="" disabled>
                Select Provider
              </option>
              {runBookInstalledProviders.map((provider) => (
                <option key={provider.id} value={provider.id}>
                  {provider.details.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label>Choose Repo</label>
            <select
              {...register("repoName")}
              style={{ width: "100%", padding: "8px", marginBottom: "10px" }}
            >
              <option value="" disabled>
                Select Repo
              </option>
              {reposData.map((repo: any) => (
                <option key={repo.id} value={repo.option_value}>
                  {repo.display_name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label>Runbook Title</label>
            <input
              type="text"
              {...register("runBookTitle")}
              placeholder="Enter Runbook Title"
              style={{ width: "100%", padding: "8px", marginBottom: "10px" }}
            />
          </div>
          <div>
            <label>Path to MD Files</label>
            <input
              type="text"
              {...register("pathToMdFile")}
              placeholder="Enter path to markdown files"
              style={{ width: "100%", padding: "8px", marginBottom: "10px" }}
            />
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

  // Modal state management

  const handlePaginationChange = (newLimit: number, newOffset: number) => {
    setLimit(newLimit);
    setOffset(newOffset);
  };

  return (
    <div>
      <SettingsPage />
      <GenericTable<Runbook>
        data={runbookData}
        columns={columns}
        rowCount={runbookData.length}
        offset={offset}
        limit={limit}
        onPaginationChange={handlePaginationChange}
        onRowClick={(row) => {
          console.log("Runbook clicked:", row);
        }}
      />
    </div>
  );
}

export default RunbookIncidentTable;
