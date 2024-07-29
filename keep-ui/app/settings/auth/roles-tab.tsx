import { Title, Subtitle, Card, Table, TableHead, TableRow, TableHeaderCell, TableBody, TableCell, Text } from "@tremor/react";
import { CircleStackIcon } from "@heroicons/react/24/outline";
import { useConfig } from "utils/hooks/useConfig";
import useSWR from "swr";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";
import Loading from "app/loading";

interface Props {
  accessToken: string;
}

interface Role {
  id: string;
  name: string;
  description: string;
}

const staticRoles: Role[] = [
  { id: "1", name: "Admin", description: "Administrator role with full permissions" },
  { id: "2", name: "Viewer", description: "Viewer role with read-only permissions" },
  { id: "3", name: "NOC", description: "NOC role with specific operational permissions" },
];

const mockCustomRoles: Role[] = [
  { id: "4", name: "Developer", description: "Developer role with development permissions" },
  { id: "5", name: "SRE", description: "SRE role with site reliability engineering permissions" },
  { id: "6", name: "Security", description: "Security role with security-related permissions" },
];

export default function RolesTab({ accessToken }: Props) {
  const { data: configData } = useConfig();
  const apiUrl = getApiURL();

  const { data: customRoles, error, isLoading } = useSWR<Role[]>(
    configData?.AUTH_TYPE === "KEYCLOAK" ? `${apiUrl}/roles/custom` : null,
    (url) => fetcher(url, accessToken)
  );

  if (isLoading) return <Loading />;

  //const displayCustomRoles = configData?.AUTH_TYPE === "KEYCLOAK" ? customRoles : mockCustomRoles;
  const displayCustomRoles = mockCustomRoles;
  return (
    <div className="h-full flex flex-col">
      <div className="mb-4">
        <Title>Roles Management</Title>
        <Subtitle>Manage user roles</Subtitle>
      </div>
      <Card className="flex-grow overflow-auto relative mb-4">
        <Title>Predefined roles</Title>
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Role Name</TableHeaderCell>
              <TableHeaderCell>Description</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {staticRoles.map((role) => (
              <TableRow key={role.id}>
                <TableCell>{role.name}</TableCell>
                <TableCell>{role.description}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
      <Card className="flex-grow overflow-auto relative mt-4">
          <div className="absolute inset-0 bg-white bg-opacity-80 z-10 flex items-center justify-center">
            <div className="text-center">
              <CircleStackIcon
                className="mx-auto h-7 w-7 text-tremor-content-subtle dark:text-dark-tremor-content-subtle"
                aria-hidden={true}
              />
              <Text className="mt-4 font-medium text-tremor-content-strong dark:text-dark-tremor-content-strong">
                Custom roles are not available with current authentication type
              </Text>
            </div>
          </div>
        <Title>Custom roles</Title>
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Role Name</TableHeaderCell>
              <TableHeaderCell>Description</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {displayCustomRoles && displayCustomRoles.map((role) => (
              <TableRow key={role.id}>
                <TableCell>{role.name}</TableCell>
                <TableCell>{role.description}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
}
