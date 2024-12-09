import UsersSettings from "./users-settings";
import { User as AuthUser } from "next-auth";

interface Props {
  currentUser?: AuthUser;
  groupsAllowed: boolean;
  userCreationAllowed: boolean;
}

export default function UserTab({
  currentUser,
  groupsAllowed,
  userCreationAllowed,
}: Props) {
  return (
    <UsersSettings
      currentUser={currentUser}
      groupsAllowed={groupsAllowed}
      userCreationAllowed={userCreationAllowed}
    />
  );
}
