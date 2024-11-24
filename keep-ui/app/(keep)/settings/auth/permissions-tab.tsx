import React, { useState, useEffect } from "react";
import { Title, Subtitle, Card, TextInput } from "@tremor/react";
import { usePermissions } from "utils/hooks/usePermissions";
import { useUsers } from "@/entities/users/model/useUsers";
import { useGroups } from "utils/hooks/useGroups";
import { useRoles } from "utils/hooks/useRoles";
import { usePresets } from "utils/hooks/usePresets";
import { useIncidents } from "utils/hooks/useIncidents";
import Loading from "@/app/(keep)/loading";
import { PermissionsTable } from "./permissions-table";
import PermissionSidebar from "./permissions-sidebar";
import { useApiUrl } from "utils/hooks/useConfig";
import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";

interface Props {
  accessToken: string;
  isDisabled?: boolean;
}

interface PermissionEntity {
  id: string;
  type: string; // 'user' or 'group' or 'role'
}

interface ResourcePermission {
  resource_id: string;
  resource_name: string;
  resource_type: string;
  permissions: PermissionEntity[];
}

export default function PermissionsTab({
  accessToken,
  isDisabled = false,
}: Props) {
  const { data: session } = useSession();
  const apiUrl = useApiUrl();
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [selectedResource, setSelectedResource] = useState<any>(null);
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
  const [resources, setResources] = useState<any[]>([]);

  // Combine all resources and their permissions
  useEffect(() => {
    if (presets && incidents && permissions) {
      const allResources = [
        ...(presets?.map((preset) => ({
          id: preset.id,
          name: preset.name,
          type: "preset",
          assignments:
            permissions
              ?.filter((p) => p.resource_id === preset.id)
              .flatMap((p) =>
                p.permissions.map((perm) => `${perm.type}_${perm.id}`)
              ) || [],
        })) || []),
        ...(incidents?.items.map((incident) => ({
          id: incident.id,
          name: incident.user_generated_name || incident.ai_generated_name,
          type: "incident",
          assignments:
            permissions
              ?.filter((p) => p.resource_id === incident.id)
              .flatMap((p) =>
                p.permissions.map((perm) => `${perm.type}_${perm.id}`)
              ) || [],
        })) || []),
      ];
      // Compare current and new resources to prevent unnecessary updates
      const resourcesString = JSON.stringify(allResources);
      const currentResourcesString = JSON.stringify(resources);

      if (resourcesString !== currentResourcesString) {
        setResources(allResources);
      }
      setLoading(false);
    }
  }, [presets, incidents, permissions]);

  const handleSavePermissions = async (
    resourceId: string,
    assignments: string[]
  ) => {
    try {
      // Convert assignments array to PermissionEntity array
      const permissions: PermissionEntity[] = assignments.map((assignment) => {
        // Parse the assignment string to get type and id
        const [type, ...idParts] = assignment.split("_");
        return {
          id: idParts.join("_"), // Rejoin in case the id itself contains underscores
          type: type,
        };
      });

      // Find the resource details
      const resource = resources.find((r) => r.id === resourceId);
      if (!resource) {
        throw new Error("Resource not found");
      }

      // Create the resource permission object
      const resourcePermission: ResourcePermission[] = [
        {
          resource_id: resource.id,
          resource_name: resource.name,
          resource_type: resource.type,
          permissions: permissions,
        },
      ];

      // Send to the backend
      const response = await fetch(`${apiUrl}/auth/permissions`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session?.accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(resourcePermission),
      });

      if (!response.ok) {
        throw new Error("Failed to save permissions");
      }

      await mutatePermissions();
    } catch (error) {
      console.error("Error saving permissions:", error);
      throw error;
    }
  };

  if (loading) return <Loading />;

  const filteredResources = resources.filter((resource) =>
    resource.name.toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <div className="h-full w-full flex flex-col">
      <div className="mb-4">
        <Title>Permissions Management</Title>
        <Subtitle>Manage permissions for resources</Subtitle>
      </div>

      <TextInput
        placeholder="Search resources"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        className="mb-4"
        disabled={isDisabled}
      />

      <Card className="flex-grow overflow-hidden flex flex-col">
        <PermissionsTable
          resources={filteredResources}
          onRowClick={(resource) => {
            setSelectedResource(resource);
            setIsSidebarOpen(true);
          }}
          isDisabled={isDisabled}
        />
      </Card>

      <PermissionSidebar
        isOpen={isSidebarOpen}
        toggle={() => setIsSidebarOpen(false)}
        selectedResource={selectedResource}
        entityOptions={{
          user: users || [],
          group: groups || [],
          role: roles || [],
        }}
        onSavePermissions={handleSavePermissions}
        isDisabled={isDisabled}
      />
    </div>
  );
}
