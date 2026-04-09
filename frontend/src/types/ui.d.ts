export type FeedbackMessage = {
  type: "success" | "error";
  message: string;
};

export type ReturnToLocationState = {
  returnTo?: string;
};