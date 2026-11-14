import type { VisualizationsType } from "@ocelescope/resources";

// Replaces Ocelescope's internal type module, which the package does not export.
export type { VisualizationsType };
export type VisualizationByType<T extends VisualizationsType["type"]> = Extract<VisualizationsType, { type: T }>;

export type MenuItem = { icon: React.ReactNode; label: string; onClick: () => void };

export type VisualizationProps<T extends VisualizationsType["type"]> = {
  visualization: VisualizationByType<T>;
  isPreview?: boolean;
  menuItems?: MenuItem[];
};
