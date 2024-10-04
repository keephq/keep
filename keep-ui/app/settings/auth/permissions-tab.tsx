import {
  Title,
  Subtitle,
  Card,
  Table,
  TableHead,
  TableRow,
  TableHeaderCell,
  TableBody,
  TableCell,
  TextInput,
  Badge,
  Button,
} from "@tremor/react";
import { Loading } from "@/components/Loading";
import { useState, useEffect, useMemo } from "react";
import { useSession } from "next-auth/react";
import { usePresets } from "utils/hooks/usePresets";
import { useGroups } from "utils/hooks/useGroups";
import { useUsers } from "utils/hooks/useUsers";
import { usePermissions } from "utils/hooks/usePermissions";
import { getApiURL } from "utils/apiUrl";
import { TrashIcon } from "@heroicons/react/24/outline";
import PermissionSidebar from "./permissions-sidebar";
import { Permission } from "app/settings/models";
import "./multiselect.css";

interface Props {
  accessToken: string;
}

export default function PermissionsTab({ accessToken }: Props) {
  const { data: session } = useSession();
  const apiUrl = getApiURL();
  const [selectedPermissions, setSelectedPermissions] = useState<{ [key: string]: string[] }>({});
  const [initialPermissions, setInitialPermissions] = useState<{ [key: string]: string[] }>({});
  const [filter, setFilter] = useState("");
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [selectedPreset, setSelectedPreset] = useState<any>(null);

  const { useAllPresets } = usePresets();
  const { data: presets = [], error: presetsError, isValidating: presetsLoading } = useAllPresets();
  const { data: groups = [], error: groupsError, isValidating: groupsLoading } = useGroups();
  const { data: users = [], error: usersError, isValidating: usersLoading } = useUsers();
  const { data: permissions = [], error: permissionsError, isValidating: permissionsLoading } = usePermissions();


  // SHAHAR: TODO: fix when needed
  const displayPermissions = useMemo<Permission[]>(() => {
    const groupPermissions: Permission[] = (groups || []).map(group => ({
      id: group.id,
      resource_id: group.id,
      entity_id: group.id,
      permissions: [{ id: 'group' }],
      name: group.name,
      type: "group"
    }));
    const userPermissions: Permission[] = (users || []).map(user => ({
      id: user.email,
      resource_id: user.email,
      entity_id: user.email,
      permissions: [{ id: 'user' }],
      name: user.name,
      type: "user"
    }));
    return [...groupPermissions, ...userPermissions];
  }, [groups, users]);

  const handlePermissionChange = (presetId: string, newPermissions: string[]) => {
    setSelectedPermissions(prev => ({
      ...prev,
      [presetId]: newPermissions
    }));
  };

  useEffect(() => {
    if (permissions) {
      const initialPerms: { [key: string]: string[] } = {};

      permissions.forEach(permission => {
        initialPerms[permission.resource_id] = permission.permissions.map(p => p.id);
      });

      setInitialPermissions(initialPerms);
      setSelectedPermissions(initialPerms);
    }
  }, [permissions]);

  const hasChanges = JSON.stringify(initialPermissions) !== JSON.stringify(selectedPermissions);

  const savePermissions = async () => {
    try {
      const changedPermissions = Object.entries(selectedPermissions).reduce((acc, [presetId, permissions]) => {
        if (JSON.stringify(permissions) !== JSON.stringify(initialPermissions[presetId])) {
          acc[presetId] = permissions;
        }
        return acc;
      }, {} as { [key: string]: string[] });

      const resourcePermissions = Object.entries(changedPermissions).map(([presetId, permissions]) => ({
        resource_id: presetId,
        resource_name: presets?.find(preset => preset.id === presetId)?.name || "",
        resource_type: "preset",
        permissions: permissions.map(permissionId => {
          const permission = displayPermissions.find(p => p.id === permissionId);
          return {
            id: permissionId,
            type: permission?.type
          };
        })
      }));

      if (resourcePermissions.length === 0) {
        console.log("No changes to save");
        return;
      }

      const response = await fetch(`${getApiURL()}/auth/permissions`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session?.accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(resourcePermissions),
      });

      if (response.ok) {
        setInitialPermissions(selectedPermissions);
        // You might want to show a success message here
      } else {
        const errorData = await response.json();
        console.error("Failed to save permissions:", errorData.detail || errorData.message || "Unknown error");
        // You might want to show an error message to the user here
      }
    } catch (error) {
      console.error("An unexpected error occurred while saving permissions:", error);
      // You might want to show an error message to the user here
    }
  };

  if (presetsLoading || groupsLoading || usersLoading || permissionsLoading) return <Loading />;

  const filteredPresets = (presets || []).filter(preset =>
    preset.name.toLowerCase().includes(filter.toLowerCase())
  );

  const handleRowClick = (preset: any) => {
    setSelectedPreset(preset);
    setIsSidebarOpen(true);
  };

  const handleDeletePermission = async (presetId: string, event: React.MouseEvent) => {
    event.stopPropagation();
    if (window.confirm("Are you sure you want to delete this permission?")) {
      try {
        const response = await fetch(`${apiUrl}/auth/permissions/${presetId}`, {
          method: 'DELETE',
          headers: {
            Authorization: `Bearer ${accessToken}`,
          },
        });

        if (response.ok) {
          // Reload permissions
        } else {
          console.error("Failed to delete permission");
        }
      } catch (error) {
        console.error("Error deleting permission:", error);
      }
    }
  };

  return (
    <div className="h-full w-full flex flex-col">
      <div className="flex justify-between items-center mb-4">
        <div>
          <Title>Permissions Management</Title>
          <Subtitle>Manage permissions for Keep resources</Subtitle>
        </div>
        <Button
          color="orange"
          onClick={savePermissions}
          disabled={!hasChanges}
        >
          Save Permissions
        </Button>
      </div>
      <TextInput
        placeholder="Search resource"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        className="mb-4"
      />
      <Card className="flex-grow overflow-hidden flex flex-col">
        <Table className="h-full">
          <TableHead>
            <TableRow>
              <TableHeaderCell className="w-6/24">Resource Name</TableHeaderCell>
              <TableHeaderCell className="w-6/24">Resource Type</TableHeaderCell>
              <TableHeaderCell className="w-11/24">Permissions</TableHeaderCell>
              <TableHeaderCell className="w-1/24"></TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody className="overflow-auto">
            {filteredPresets.map((preset) => (
              <TableRow
                key={preset.id}
                className="hover:bg-gray-50 transition-colors duration-200 cursor-pointer group"
                onClick={() => handleRowClick(preset)}
              >
                <TableCell className="w-6/24">{preset.name}</TableCell>
                <TableCell className="w-6/24"> <Badge color="orange" className="text-xs">preset</Badge></TableCell>
                <TableCell className="w-11/24">
                  <div className="flex flex-wrap gap-1">
                    {selectedPermissions[preset.id]?.slice(0, 5).map((permId, index) => (
                      <Badge key={index} color="orange" className="text-xs">
                        {displayPermissions.find(p => p.id === permId)?.name}
                      </Badge>
                    ))}
                    {selectedPermissions[preset.id]?.length > 5 && (
                      <Badge color="orange" className="text-xs">
                        +{selectedPermissions[preset.id].length - 5} more
                      </Badge>
                    )}
                  </div>
                </TableCell>
                <TableCell className="w-1/24">
                <div className="flex justify-end">
                    <Button
                      icon={TrashIcon}
                      variant="light"
                      color="orange"
                      className="opacity-0 group-hover:opacity-100 transition-opacity"
                      onClick={(e) => handleDeletePermission(preset.id, e)}
                    />
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
      <PermissionSidebar
        isOpen={isSidebarOpen}
        toggle={() => setIsSidebarOpen(false)}
        accessToken={accessToken}
        preset={selectedPreset}
        permissions={displayPermissions}
        selectedPermissions={selectedPermissions}
        onPermissionChange={handlePermissionChange}
      />
    </div>
  );
}
