import { useMutation, useQueryClient } from "@tanstack/react-query";
import { updateProfile } from "../api/profile";

export function useUpdateProfile() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: updateProfile,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["me"] });
    },
  });
}