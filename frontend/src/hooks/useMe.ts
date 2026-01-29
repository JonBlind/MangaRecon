import { useQuery } from "@tanstack/react-query";
import { me } from "../api/auth";

export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: me,
    retry: false,
    staleTime: 60_000,
  });
}
