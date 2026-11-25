import { Group, NumberInput, Switch, TextInput, Tooltip } from "@mantine/core";

type Property = {
  type?: string;
  title?: string;
  description?: string;
  minimum?: number;
  maximum?: number;
  exclusiveMinimum?: number;
};

type ParamsFieldsProps = {
  schema: Record<string, unknown>;
  values: Record<string, unknown>;
  onChange: (values: Record<string, unknown>) => void;
  size?: "xs" | "sm";
};

/** Inputs for the flat parameter models (numbers, integers, booleans) of algorithms and heuristics. */
export function ParamsFields({ schema, values, onChange, size = "xs" }: ParamsFieldsProps) {
  const properties = (schema.properties ?? {}) as Record<string, Property>;
  const entries = Object.entries(properties);
  if (entries.length === 0) return null;
  const set = (key: string, value: unknown) => onChange({ ...values, [key]: value });

  return (
    <Group gap="xs" align="flex-end" wrap="wrap">
      {entries.map(([key, property]) => {
        const label = (
          <Tooltip label={property.description} disabled={!property.description} multiline maw={260}>
            <span>{property.title ?? key}</span>
          </Tooltip>
        );
        if (property.type === "boolean") {
          return (
            <Switch
              key={key}
              size={size}
              label={label}
              checked={Boolean(values[key])}
              onChange={(event) => set(key, event.currentTarget.checked)}
            />
          );
        }
        if (property.type === "integer" || property.type === "number") {
          return (
            <NumberInput
              key={key}
              size={size}
              w={92}
              label={label}
              value={values[key] as number | undefined}
              min={property.minimum ?? property.exclusiveMinimum}
              max={property.maximum}
              step={property.type === "integer" ? 1 : 0.05}
              allowDecimal={property.type === "number"}
              onChange={(value) => set(key, typeof value === "number" ? value : Number(value))}
            />
          );
        }
        return (
          <TextInput
            key={key}
            size={size}
            w={120}
            label={label}
            value={String(values[key] ?? "")}
            onChange={(event) => set(key, event.currentTarget.value)}
          />
        );
      })}
    </Group>
  );
}
