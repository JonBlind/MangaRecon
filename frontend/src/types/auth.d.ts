export type UserMe = {
  id: string;
  email: string;
  is_active: boolean;
  is_superuser: boolean;
  is_verified: boolean;

  username: string;
  displayname: string;
  username_changed_at: string | null;
  show_adult_content: boolean;

  created_at: string;
  last_login?: string | null;
};
