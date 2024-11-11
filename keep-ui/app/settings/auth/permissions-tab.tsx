import React, { useState, useEffect } from "react";
import { Title, Subtitle, Card, TextInput, Button } from "@tremor/react";
import { FaUserLock } from "react-icons/fa";
import { Permission, User, Group, Role } from "app/settings/models";
import { useApiUrl } from "utils/hooks/useConfig";
import { useSession } from "next-auth/react";
import Loading from "app/loading";
import { PermissionsTable } from "./permissions-table";
import PermissionSidebar from "./permissions-sidebar";
import { usePermissions } from "utils/hooks/usePermissions";
import { useUsers } from "utils/hooks/useUsers";
import { useGroups } from "utils/hooks/useGroups";
import { useRoles } from "utils/hooks/useRoles";
import { usePresets } from "utils/hooks/usePresets";
import { useIncidents } from "utils/hooks/useIncidents";

interface Props {
  accessToken: string;
  isDisabled?: boolean;
}

export default function PermissionsTab({
  accessToken,
  isDisabled = false,
}: Props) {
  const { data: session } = useSession();
  const apiUrl = useApiUrl();
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [selectedPermission, setSelectedPermission] =
    useState<Permission | null>(null);
  const [filter, setFilter] = useState("");

  // Fetch data using custom hooks
  const { data: permissions, mutate: mutatePermissions } = usePermissions();
  const { data: users } = useUsers();
  const { data: groups } = useGroups();
  const { data: roles } = useRoles();
  const { useAllPresets } = usePresets();
  const { data: presets } = useAllPresets();
  const { data: incidents } = useIncidents();

  const [loading, setLoading] = useState(true);

  // Define available resource types and their corresponding resources
  const resourceTypes = ["preset", "incident"];
  const resources = {
    preset: presets || [],
    incident: incidents || [],
  };

  // Define entity types for permission assignment
  const entityTypes = [
    { id: "user", name: "User" },
    { id: "group", name: "Group" },
    { id: "role", name: "Role" },
  ];

  // Entity options for assignment
  const entityOptions = {
    user: users || [],
    group: groups || [],
    role: roles || [],
  };

  useEffect(() => {
    if (permissions && users && groups && roles && presets && incidents) {
      setLoading(false);
    }
  }, [permissions, users, groups, roles, presets, incidents]);

  const handleSavePermission = async (permissionData: any) => {
    try {
      const method = selectedPermission ? "PUT" : "POST";
      const url = selectedPermission
        ? `${apiUrl}/auth/permissions/${selectedPermission.id}`
        : `${apiUrl}/auth/permissions`;

      const response = await fetch(url, {
        method,
        headers: {
          Authorization: `Bearer ${session?.accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(permissionData),
      });

      if (response.ok) {
        await mutatePermissions();
        setIsSidebarOpen(false);
      }
    } catch (error) {
      console.error("Error saving permission:", error);
    }
  };

  const handleDeletePermission = async (
    permissionId: string,
    event: React.MouseEvent
  ) => {
    event.stopPropagation();
    if (window.confirm("Are you sure you want to delete this permission?")) {
      try {
        const response = await fetch(
          `${apiUrl}/auth/permissions/${permissionId}`,
          {
            method: "DELETE",
            headers: {
              Authorization: `Bearer ${session?.accessToken}`,
            },
          }
        );

        if (response.ok) {
          await mutatePermissions();
        }
      } catch (error) {
        console.error("Error deleting permission:", error);
      }
    }
  };

  if (loading) return <Loading />;

  const filteredPermissions =
    permissions?.filter(
      (permission) =>
        permission.name?.toLowerCase().includes(filter.toLowerCase())
    ) || [];

  return (
    <div className="h-full w-full flex flex-col">
      <div className="flex justify-between items-center mb-4">
        <div>
          <Title>Permissions Management</Title>
          <Subtitle>Manage permissions for resources</Subtitle>
        </div>
        <Button
          color="orange"
          size="md"
          onClick={() => {
            setSelectedPermission(null);
            setIsSidebarOpen(true);
          }}
          icon={FaUserLock}
          disabled={isDisabled}
        >
          Create Permission
        </Button>
      </div>

      <TextInput
        placeholder="Search permissions"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        className="mb-4"
        disabled={isDisabled}
      />

      <Card className="flex-grow overflow-hidden flex flex-col">
        <PermissionsTable
          permissions={filteredPermissions}
          onRowClick={(permission) => {
            setSelectedPermission(permission);
            setIsSidebarOpen(true);
          }}
          onDeletePermission={handleDeletePermission}
          isDisabled={isDisabled}
        />
      </Card>

      <PermissionSidebar
        isOpen={isSidebarOpen}
        toggle={() => setIsSidebarOpen(false)}
        accessToken={accessToken}
        selectedPermission={selectedPermission}
        resourceTypes={resourceTypes}
        resources={{
          preset: resources.preset,
          incident: Array.isArray(resources.incident) ? resources.incident : [],
        }}
        entityOptions={entityOptions}
        onSavePermission={handleSavePermission}
        isDisabled={isDisabled}
      />
    </div>
  );
}
