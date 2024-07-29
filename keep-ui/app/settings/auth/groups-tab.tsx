import { Title, Subtitle, Card, Table, TableHead, TableRow, TableHeaderCell, TableBody, TableCell, Text, Button } from "@tremor/react";
import { CircleStackIcon } from "@heroicons/react/24/outline";
import { useConfig } from "utils/hooks/useConfig";
import { getApiURL } from "utils/apiUrl";
import Loading from "app/loading";
import { useGroups } from "utils/hooks/useGroups";
import { Group } from "app/settings/models";

interface Props {
  accessToken: string;
}


const mockGroups: Group[] = [
  { id: "1", name: "Administrators", memberCount: 5, members: ["admin1", "admin2"], roles: ["Admin"] },
  { id: "2", name: "Developers", memberCount: 15, members: ["dev1", "dev2", "dev3"], roles: ["Developer"] },
  { id: "3", name: "SREs", memberCount: 10, members: ["sre1", "sre2"], roles: ["SRE"] },
  { id: "4", name: "NOC", memberCount: 8, members: ["noc1", "noc2"], roles: ["NOC"] },
  { id: "5", name: "Security", memberCount: 7, members: ["sec1", "sec2"], roles: ["Security"] },
];

export default function GroupsTab({ accessToken }: Props) {
  const { data: configData } = useConfig();
  const apiUrl = getApiURL();

  const { data: groups, error, isLoading } = useGroups();

  if (isLoading) return <Loading />;

  const displayGroups = configData?.AUTH_TYPE === "KEYCLOAK" ? groups : mockGroups;

  return (
    <div className="h-full flex flex-col">
      <div className="mb-4 flex justify-between items-center">
        <div>
          <Title>Groups Management</Title>
          <Subtitle>Manage user groups</Subtitle>
        </div>
        <Button
          disabled
          variant="secondary"
          tooltip="Groups are managed through LDAP"
        >
          Manage Groups
        </Button>
      </div>
      <Card className="flex-grow overflow-auto relative">
        {configData?.AUTH_TYPE !== "KEYCLOAK" && (
          <div className="absolute inset-0 bg-white bg-opacity-80 z-10 flex items-center justify-center">
            <div className="text-center">
              <CircleStackIcon
                className="mx-auto h-7 w-7 text-tremor-content-subtle dark:text-dark-tremor-content-subtle"
                aria-hidden={true}
              />
              <Text className="mt-4 font-medium text-tremor-content-strong dark:text-dark-tremor-content-strong">
                Groups are not available with current authentication type
              </Text>
            </div>
          </div>
        )}
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Group Name</TableHeaderCell>
              <TableHeaderCell>Members</TableHeaderCell>
              <TableHeaderCell>Roles</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {displayGroups && displayGroups.map((group) => (
              <TableRow key={group.id}>
                <TableCell>{group.name}</TableCell>
                <TableCell>{group.members.join(", ")}</TableCell>
                <TableCell>{group.roles.join(", ")}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
}
