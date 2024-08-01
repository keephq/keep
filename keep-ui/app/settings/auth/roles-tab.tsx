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
} from "@tremor/react";
import { useState, useEffect } from "react";
import { getApiURL } from "utils/apiUrl";
import { useScopes } from "utils/hooks/useScopes";
import { useRoles } from "utils/hooks/useRoles";
import React from "react";
import RoleSidebar from "./roles-sidebar";
import Loading from "../../loading";
import "./multiselect.css";

interface Props {
  accessToken: string;
}

export default function RolesTab({ accessToken }: Props) {
  const apiUrl = getApiURL();
  const { data: scopes = [], isLoading: scopesLoading } = useScopes();
  const { data: roles = [], isLoading: rolesLoading, mutate: mutateRoles } = useRoles();

  const [resources, setResources] = useState<string[]>([]);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [selectedRole, setSelectedRole] = useState<any>(null); // State to track selected role

  useEffect(() => {
    if (scopes) {
      const extractedResources = [...new Set(scopes.map(scope => scope.split(':')[1]).filter(resource => resource !== '*'))];
      setResources(extractedResources);
    }
  }, [scopes]);

  if (scopesLoading || rolesLoading) return <Loading />;

  const handleRowClick = (role: any) => {
    setSelectedRole(role);
    setIsSidebarOpen(true);
  };

  return (
    <div className="mt-10 h-full flex flex-col">
      <div className="flex justify-between mb-4">
        <div className="flex flex-col">
          <Title>Roles Management</Title>
          <Subtitle>Manage user roles</Subtitle>
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
          >
            Create Role
          </Button>
        </div>
      </div>
      <Card className="flex-grow overflow-auto h-full">
        <Table className="h-full">
          <TableHead>
            <TableRow>
              <TableHeaderCell className="w-1/2">Role Name</TableHeaderCell>
              <TableHeaderCell className="w-1/2">Description</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {roles.sort((a, b) => (a.predefined === b.predefined ? 0 : a.predefined ? -1 : 1)).map((role) => (
              <TableRow
                key={role.name}
                className="hover:bg-gray-50 transition-colors duration-200 cursor-pointer"
                onClick={() => handleRowClick(role)}
              >
                <TableCell className="w-1/6">
                  <div className="flex items-center justify-between">
                    <Text className="truncate">{role.name}</Text>
                    {role.predefined ? (
                      <Badge color="orange" className="ml-2 w-24 text-center">Predefined</Badge>
                    ) : (
                      <Badge color="orange" className="ml-2 w-24 text-center">Custom</Badge>
                    )}
                  </div>
                </TableCell>
                <TableCell className="w-1/6">
                  <Text>{role.description}</Text>
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
