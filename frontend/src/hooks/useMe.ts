import { useQuery } from "@tanstack/react-query";
import { me } from "../api/auth";
import type { UserMe } from "../types/auth";

export function useMe() {
  return useQuery<UserMe | null>({
    queryKey: ["me"],
    queryFn: me,
    retry: false,
    staleTime: 60_000,
  });
}
