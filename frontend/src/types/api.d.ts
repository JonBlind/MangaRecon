export type ApiEnvelope<T> = {
  status: "success" | "error";
  data: T;
  message?: string;
  detail?: unknown;
};
