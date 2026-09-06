import { useMutation, useQueryClient } from "@tanstack/react-query";
import { updateProfile } from "../api/profile";

export function useUpdateProfile() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: updateProfile,
    onSuccess: (response, payload) => {
      qc.setQueryData(["me"], response.data);

      if (payload.show_adult_content !== undefined) {
        for (const queryKey of [
          ["manga"],
          ["mangas"],
          ["genres"],
          ["tags"],
          ["demographics"],
          ["collections", "mangas"],
          ["ratings"],
          ["recommendations"],
        ]) {
          qc.removeQueries({ queryKey });
        }
      }
    },
  });
}
