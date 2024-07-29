export interface User {
  name: string;
  email: string;
  role: string;
  picture?: string;
  created_at: string;
  last_login?: string;
}

export interface Group {
  id: string;
  name: string;
  memberCount: number;
  members: string[];
  roles: string[];
}

export interface Permission {
  id: string;
  resource_id: string; // id of the resource
  entity_id: string; // id of the entity
}
