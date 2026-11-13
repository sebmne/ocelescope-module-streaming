import { NumberInput, Switch, TextInput } from "@mantine/core";
import type { Params } from "./useConfig";

type Property = { type?: string; title?: string; default?: unknown };

/** Inputs for the flat JSON schema of a heuristic's parameters. */
export function ParamFields({ schema, value, onChange }: { schema: Params; value: Params; onChange: (value: Params) => void }) {
  const properties = (schema.properties ?? {}) as Record<string, Property>;
  return Object.entries(properties).map(([key, property]) => {
    const current = value[key] ?? property.default;
    const set = (next: unknown) => onChange({ ...value, [key]: next });
    const label = property.title ?? key;
    if (property.type === "boolean") {
      return <Switch key={key} size="xs" label={label} checked={Boolean(current)} onChange={(e) => set(e.currentTarget.checked)} />;
    }
    if (property.type === "integer" || property.type === "number") {
      return (
        <NumberInput
          key={key}
          size="xs"
          label={label}
          value={current as number}
          allowDecimal={property.type === "number"}
          onChange={(next) => typeof next === "number" && set(next)}
        />
      );
    }
    return <TextInput key={key} size="xs" label={label} value={String(current ?? "")} onChange={(e) => set(e.currentTarget.value)} />;
  });
}
