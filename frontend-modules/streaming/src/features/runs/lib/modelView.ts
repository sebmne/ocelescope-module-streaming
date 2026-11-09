/** Which model the canvas shows. */
export type ModelView = "streaming" | "offline" | "both";

export const MODEL_VIEWS: { value: ModelView; label: string }[] = [
  { value: "streaming", label: "Streaming" },
  { value: "offline", label: "Offline" },
  { value: "both", label: "Side by side" },
];
