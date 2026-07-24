export type UserMe = {
  id: string;
  email: string;
  is_active: boolean;
  is_superuser: boolean;
  is_verified: boolean;

  username: string;
  displayname: string;
  username_changed_at: string | null;

  created_at: string;
  last_login?: string | null;
};