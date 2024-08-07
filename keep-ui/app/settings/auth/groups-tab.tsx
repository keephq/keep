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
  MultiSelect,
  MultiSelectItem,
} from "@tremor/react";
import Loading from "app/loading";
import { getApiURL } from "utils/apiUrl";
import { useGroups } from "utils/hooks/useGroups";
import { useUsers } from "utils/hooks/useUsers";
import { useRoles } from "utils/hooks/useRoles";
import { useState, useEffect } from "react";
import "./multiselect.css";

interface Props {
  accessToken: string;
}

export default function GroupsTab({ accessToken }: Props) {
  const apiUrl = getApiURL();
  const { data: groups = [], isLoading: groupsLoading, error: groupsError, mutate: mutateGroups } = useGroups();
  const { data: users = [], isLoading: usersLoading, error: usersError } = useUsers();
  const { data: roles = [], isLoading: rolesLoading, error: rolesError } = useRoles();

  const [groupStates, setGroupStates] = useState<{ [key: string]: { members: string[], roles: string[] } }>({});
  const [hasChanges, setHasChanges] = useState(false);

  useEffect(() => {
    if (groups) {
      const initialGroupStates = groups.reduce((acc, group) => {
        acc[group.id] = {
          members: group.members || [],
          roles: group.roles || []
        };
        return acc;
      }, {} as { [key: string]: { members: string[], roles: string[] } });

      // Compare new state with current state before updating
      if (JSON.stringify(initialGroupStates) !== JSON.stringify(groupStates)) {
        setGroupStates(initialGroupStates);
      }
    }
  }, [groups, groupStates]);

  if (groupsLoading || usersLoading || rolesLoading) return <Loading />;

  const handleMemberChange = (groupId: string, newMembers: string[]) => {
    setGroupStates(prevStates => ({
      ...prevStates,
      [groupId]: {
        ...prevStates[groupId],
        members: newMembers
      }
    }));
    setHasChanges(true);
  };

  const handleRoleChange = (groupId: string, newRoles: string[]) => {
    setGroupStates(prevStates => ({
      ...prevStates,
      [groupId]: {
        ...prevStates[groupId],
        roles: newRoles
      }
    }));
    setHasChanges(true);
  };

  const updateGroups = async () => {
    // Implement the logic to update group members and roles
    // This might involve calling an API endpoint
    console.log('Updating group states:', groupStates);
    // After successful update, you might want to refresh the groups data
    await mutateGroups();
    setHasChanges(false);
  };

  return (
    <div className="h-full flex flex-col">
      <div className="flex justify-between mb-4">
        <div className="flex flex-col">
          <Title>Groups Management</Title>
          <Subtitle>Manage user groups</Subtitle>
        </div>
        <Button
          color="orange"
          variant="secondary"
          size="md"
          onClick={updateGroups}
          disabled={!hasChanges}
        >
          Update Groups
        </Button>
      </div>
      <Card className="flex-grow overflow-auto h-full">
        <div className="h-full w-full overflow-auto">
          <Table className="h-full">
            <TableHead>
              <TableRow>
                <TableHeaderCell className="w-2/16">Group Name</TableHeaderCell>
                <TableHeaderCell className="w-7/16">Members</TableHeaderCell>
                <TableHeaderCell className="w-7/16">Roles</TableHeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {groups.map((group) => (
                <TableRow key={group.id}>
                  <TableCell className="w-2/16">{group.name}</TableCell>
                  <TableCell className="w-7/16">
                    <MultiSelect
                      value={groupStates[group.id]?.members || []}
                      onValueChange={(value) => handleMemberChange(group.id, value)}
                      className="custom-multiselect"
                    >
                      {users.map((user) => (
                        <MultiSelectItem key={user.email} value={user.email}>
                          {user.email}
                        </MultiSelectItem>
                      ))}
                    </MultiSelect>
                  </TableCell>
                  <TableCell className="w-7/16">
                    <MultiSelect
                      value={groupStates[group.id]?.roles || []}
                      onValueChange={(value) => handleRoleChange(group.id, value)}
                      className="custom-multiselect"
                    >
                      {roles.map((role) => (
                        <MultiSelectItem key={role.id} value={role.name}>
                          {role.name}
                        </MultiSelectItem>
                      ))}
                    </MultiSelect>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </Card>
    </div>
  );
}
