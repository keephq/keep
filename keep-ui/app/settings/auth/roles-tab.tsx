import {
  Title,
  Subtitle,
  Card,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  Text,
  Button,
  Badge,
  TextInput,
} from "@tremor/react";
import { useState, useEffect, useMemo } from "react";
import { getApiURL } from "utils/apiUrl";
import { useScopes } from "utils/hooks/useScopes";
import { useRoles } from "utils/hooks/useRoles";
import React from "react";
import RoleSidebar from "./roles-sidebar";
import Loading from "../../loading";
import { Role } from "app/settings/models";
import "./multiselect.css";
import { TrashIcon } from "@heroicons/react/24/outline";

interface RolesTabProps {
  accessToken: string;
  customRolesAllowed: boolean;
}

export default function RolesTab({ accessToken, customRolesAllowed }: RolesTabProps) {
  const apiUrl = getApiURL();
  const { data: scopes = [], isLoading: scopesLoading } = useScopes();
  const { data: roles = [], isLoading: rolesLoading, mutate: mutateRoles } = useRoles();

  const [resources, setResources] = useState<string[]>([]);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [selectedRole, setSelectedRole] = useState<Role | null>(null);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    if (scopes && scopes.length > 0) {
      const extractedResources = [...new Set(scopes.map(scope => scope.split(':')[1]).filter(resource => resource !== '*'))];
      setResources(extractedResources);
    }
  }, [scopes]);

  const filteredRoles = useMemo(() => {
    return roles.filter(role =>
      role.name.toLowerCase().includes(filter.toLowerCase())
    );
  }, [roles, filter]);

  if (scopesLoading || rolesLoading) return <Loading />;

  const handleRowClick = (role: any) => {
    setSelectedRole(role);
    setIsSidebarOpen(true);
  };

  const handleDeleteRole = async (roleId: string, event: React.MouseEvent) => {
    event.stopPropagation();
    if (window.confirm("Are you sure you want to delete this role?")) {
      try {
        const response = await fetch(`${apiUrl}/auth/roles/${roleId}`, {
          method: 'DELETE',
          headers: {
            Authorization: `Bearer ${accessToken}`,
          },
        });

        if (response.ok) {
          await mutateRoles();
        } else {
          console.error("Failed to delete role");
        }
      } catch (error) {
        console.error("Error deleting role:", error);
      }
    }
  };

  return (
    <div className="h-full flex flex-col">
      <div className="flex justify-between mb-4">
        <div className="flex flex-col">
          <Title>Roles Management</Title>
          <Subtitle>Manage roles</Subtitle>
        </div>
        <div className="flex space-x-2">
          <Button
            color="orange"
            size="md"
            variant="secondary"
            onClick={() => {
              setSelectedRole(null);
              setIsSidebarOpen(true);
            }}
            disabled={!customRolesAllowed}
            tooltip={customRolesAllowed ? undefined : "This feature is not available in your authentication mode."}
          >
            Create Custom Role
          </Button>
        </div>
      </div>
      <TextInput
        placeholder="Search by role name"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        className="mb-4"
      />
      <Card className="flex-grow overflow-auto h-full">
        <Table className="h-full">
          <TableHead>
            <TableRow>
              <TableHeaderCell className="w-4/24">Role Name</TableHeaderCell>
              <TableHeaderCell className="w-4/24">Description</TableHeaderCell>
              <TableHeaderCell className="w-15/24">Scopes</TableHeaderCell>
              <TableHeaderCell className="w-1/24"></TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {filteredRoles.sort((a, b) => (a.predefined === b.predefined ? 0 : a.predefined ? -1 : 1)).map((role) => (
              <TableRow
                key={role.name}
                className="hover:bg-gray-50 transition-colors duration-200 cursor-pointer group"
                onClick={() => handleRowClick(role)}
              >
                <TableCell className="w-4/24">
                  <div className="flex items-center justify-between">
                    <Text className="truncate">{role.name}</Text>
                    <div className="flex items-center">
                      {role.predefined ? (
                        <Badge color="orange" className="ml-2 w-24 text-center">Predefined</Badge>
                      ) : (
                        <Badge color="orange" className="ml-2 w-24 text-center">Custom</Badge>
                      )}
                    </div>
                  </div>
                </TableCell>
                <TableCell className="w-4/24">
                  <Text>{role.description}</Text>
                </TableCell>
                <TableCell className="w-15/24">
                  <div className="flex flex-wrap gap-1">
                    {role.scopes.slice(0, 4).map((scope, index) => (
                      <Badge key={index} color="orange" className="text-xs">
                        {scope}
                      </Badge>
                    ))}
                    {role.scopes.length > 4 && (
                      <Badge color="orange" className="text-xs">
                        +{role.scopes.length - 4} more
                      </Badge>
                    )}
                  </div>
                </TableCell>
                <TableCell className="w-1/24">
                  {!role.predefined && (
                    <Button
                      icon={TrashIcon}
                      variant="light"
                      color="orange"
                      className="opacity-0 group-hover:opacity-100 transition-opacity"
                      onClick={(e) => handleDeleteRole(role.id, e)}
                    />
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
      <RoleSidebar
        isOpen={isSidebarOpen}
        toggle={() => setIsSidebarOpen(false)}
        accessToken={accessToken}
        selectedRole={selectedRole}
        resources={resources}
        mutateRoles={mutateRoles}
      />
    </div>
  );
}
