export type UserMe = {
  id: string;
  email: string;
  is_active: boolean;
  is_superuser: boolean;
  is_verified: boolean;

  username: string;
  displayname: string;

  created_at: string;
  last_login?: string | null;
};