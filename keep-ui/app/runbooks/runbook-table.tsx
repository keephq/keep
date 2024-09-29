"use client";

import React, { useState } from "react";
import Modal from "react-modal"; 
import {
    Button,
    Badge,
} from "@tremor/react";
import { DisplayColumnDef } from "@tanstack/react-table";
import { GenericTable } from "@/components/table/GenericTable";  
import { useSession } from "next-auth/react";


const customStyles = {
    content: {
        top: '50%',
        left: '50%',
        right: 'auto',
        bottom: 'auto',
        marginRight: '-50%',
        transform: 'translate(-50%, -50%)',
        width: '400px',
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

const runbookData: Runbook[] = [
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
        incidents: [
            { id: 201, name: "API Latency Issue" },
        ],
    },
    {
        id: 3,
        title: "Server Restart Guide",
        incidents: [
            { id: 301, name: "Unexpected Server Crash" },
            { id: 302, name: "Scheduled Maintenance" },
        ],
    },
];

const columns: DisplayColumnDef<Runbook>[] = [
    {
        accessorKey: 'title',
        header: 'Runbook Title',
        cell: info => info.getValue(),
    },
    {
        accessorKey: 'incidents',
        header: 'Incidents',
        cell: info => (
            <div>
                {info.getValue().map((incident: Incident) => (
                    <Badge key={incident.id} color="green" className="mr-2 mb-1">
                        {incident.name}
                    </Badge>
                ))}
            </div>
        ),
    },
];

function RunbookIncidentTable() {
    const [offset, setOffset] = useState(0);
    const [limit, setLimit] = useState(10);

    // Modal state management
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [repositoryName, setRepositoryName] = useState('');
    const [pathToMdFiles, setPathToMdFiles] = useState('');

    const { data: session } = useSession();

    const handlePaginationChange = (newLimit: number, newOffset: number) => {
        setLimit(newLimit);
        setOffset(newOffset);
    };

    // Open modal handler
    const openModal = () => {
        setIsModalOpen(true);
    };

    // Close modal handler
    const closeModal = () => {
        setIsModalOpen(false);
    };

    const handleQuerySettings = async ({ repositoryName, pathToMdFiles }) => {
        try {
            const [owner, repo] = repositoryName.split("/"); 
            const response = await fetch(`https://api.github.com/repos/${owner}/${repo}/contents/${pathToMdFiles}`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Bearer ${session?.accessToken}`,
                },
            });

            if (!response.ok) {
                throw new Error('Failed to query settings');
            }

            const data = await response.json();
            console.log('Settings queried successfully:', data);

        } catch (error) {
            console.error('Error while querying settings:', error);
            alert('An error occurred while querying settings');
        }
    };

    return (
        <div>
            <Button onClick={openModal}>Settings</Button>

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

            {/* Modal for Settings */}
            <Modal
                isOpen={isModalOpen}
                onRequestClose={closeModal}
                style={customStyles}
                contentLabel="Settings Modal"
            >
                <h2>Runbook Settings</h2>

                <div>
                    <label>Repository Name</label>
                    <input
                        type="text"
                        value={repositoryName}
                        onChange={(e) => setRepositoryName(e.target.value)}
                        placeholder="Enter repository name (e.g., owner/repo)"
                        style={{ width: '100%', padding: '8px', marginBottom: '10px' }}
                    />
                </div>

                <div>
                    <label>Path to MD Files</label>
                    <input
                        type="text"
                        value={pathToMdFiles}
                        onChange={(e) => setPathToMdFiles(e.target.value)}
                        placeholder="Enter path to markdown files"
                        style={{ width: '100%', padding: '8px', marginBottom: '10px' }}
                    />
                </div>

                <div style={{ textAlign: 'right' }}>
                    <Button onClick={closeModal} style={{ marginRight: '10px' }}>Cancel</Button>
                    <Button onClick={() => handleQuerySettings({ repositoryName, pathToMdFiles })} color="blue">Query</Button>
                </div>
            </Modal>
        </div>
    );
}

export default RunbookIncidentTable;
