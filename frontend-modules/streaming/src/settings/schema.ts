/** The subset of JSON schema that pydantic emits for flat settings models. */
export type Property = {
  type?: "integer" | "number" | "boolean" | "string";
  title?: string;
  description?: string;
  default?: unknown;
  minimum?: number;
  maximum?: number;
  enum?: string[];
};

export type Values = Record<string, unknown>;

export const properties = (schema: Record<string, unknown>) =>
  Object.entries((schema.properties ?? {}) as Record<string, Property>);

export const defaults = (schema: Record<string, unknown>): Values =>
  Object.fromEntries(properties(schema).map(([name, property]) => [name, property.default]));
