import { useUsers } from "./useUsers";

export function useUser(email: string) {
  const { data: users = [] } = useUsers();
  return users.find((user) => user.email === email) ?? null;
}
