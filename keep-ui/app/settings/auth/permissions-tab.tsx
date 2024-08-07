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
  MultiSelect,
  MultiSelectItem,
  Button,
} from "@tremor/react";
import Loading from "app/loading";
import { useState, useEffect, useMemo } from "react";
import { useSession } from "next-auth/react";
import { usePresets } from "utils/hooks/usePresets";
import { useGroups } from "utils/hooks/useGroups";
import { useUsers } from "utils/hooks/useUsers";
import { usePermissions } from "utils/hooks/usePermissions";
import { getApiURL } from "utils/apiUrl";
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

  const { useAllPresets } = usePresets();
  const { data: presets = [], error: presetsError, isValidating: presetsLoading } = useAllPresets();
  const { data: groups = [], error: groupsError, isValidating: groupsLoading } = useGroups();
  const { data: users = [], error: usersError, isValidating: usersLoading } = useUsers();
  const { data: permissions = [], error: permissionsError, isValidating: permissionsLoading } = usePermissions();

  const displayPermissions = useMemo(() => {
    const groupPermissions = (groups || []).map(group => ({ id: group.id, name: group.name, type: 'group' as const }));
    const userPermissions = (users || []).map(user => ({ id: user.email, name: user.email, type: 'user' as const }));
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

  return (
    <div className="h-full w-full flex flex-col">
      <div className="flex justify-between items-center mb-4">
        <div>
          <Title>Permissions Management</Title>
          <Subtitle>Manage permissions for presets</Subtitle>
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
        placeholder="Search presets"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        className="mb-4"
      />
      <Card className="flex-grow overflow-hidden flex flex-col">
        <Table className="h-full">
          <TableHead>
            <TableRow>
              <TableHeaderCell className="w-1/3">Preset Name</TableHeaderCell>
              <TableHeaderCell className="w-2/3">Permissions</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody className="overflow-auto">
            {filteredPresets.map((preset) => (
              <TableRow key={preset.id}>
                <TableCell className="w-1/3">{preset.name}</TableCell>
                <TableCell className="w-2/3">
                  <MultiSelect
                    placeholder="Select permissions"
                    className="custom-multiselect"
                    value={selectedPermissions[preset.id] || []}
                    onValueChange={(value) => handlePermissionChange(preset.id, value)}
                  >
                    {displayPermissions.map((permission) => (
                      <MultiSelectItem key={permission.id} value={permission.id}>
                        {permission.name} ({permission.type})
                      </MultiSelectItem>
                    ))}
                  </MultiSelect>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
}
