import { NumberInput, Select, Stack, Switch, TextInput } from "@mantine/core";
import { type Property, properties, type Values } from "./schema";

type Props = { schema: Record<string, unknown>; values: Values; onChange: (values: Values) => void };

/** One input per property of the algorithm's settings schema. */
export function SettingsFields({ schema, values, onChange }: Props) {
  return (
    <Stack gap="md">
      {properties(schema).map(([name, property]) => (
        <Field key={name} property={property} value={values[name]} onChange={(value) => onChange({ ...values, [name]: value })} />
      ))}
    </Stack>
  );
}

function Field({ property, value, onChange }: { property: Property; value: unknown; onChange: (value: unknown) => void }) {
  const common = { label: property.title, description: property.description };
  if (property.enum) {
    return <Select {...common} data={property.enum} value={value as string} allowDeselect={false} onChange={onChange} />;
  }
  switch (property.type) {
    case "integer":
    case "number":
      return (
        <NumberInput
          {...common}
          value={value as number}
          min={property.minimum}
          max={property.maximum}
          allowDecimal={property.type === "number"}
          onChange={(next) => onChange(typeof next === "number" ? next : property.default)}
        />
      );
    case "boolean":
      return <Switch {...common} checked={Boolean(value)} onChange={(event) => onChange(event.currentTarget.checked)} />;
    default:
      return <TextInput {...common} value={(value as string) ?? ""} onChange={(event) => onChange(event.currentTarget.value)} />;
  }
}
