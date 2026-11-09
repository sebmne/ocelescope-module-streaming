import Form from "@rjsf/mantine";
import type { RJSFSchema, UiSchema } from "@rjsf/utils";
import validator from "@rjsf/validator-ajv8";
import { useMemo } from "react";

type SchemaFormProps = {
  /** JSON schema of the parameters, as provided by the backend catalog. */
  schema: Record<string, unknown>;
  value: Record<string, unknown>;
  onChange: (value: Record<string, unknown>) => void;
};

/** Whether a JSON schema describes at least one parameter. */
export function hasParameters(schema: Record<string, unknown>): boolean {
  const properties = schema.properties;
  return typeof properties === "object" && properties !== null && Object.keys(properties).length > 0;
}

/**
 * Shows field descriptions as small help texts below the fields instead of as headings, and hides
 * the schema's own title and description (the backend model's name and docstring).
 */
function compact(schema: Record<string, unknown>): { schema: RJSFSchema; uiSchema: UiSchema } {
  const properties = (schema.properties ?? {}) as Record<string, Record<string, unknown>>;
  const uiSchema: UiSchema = {
    "ui:submitButtonOptions": { norender: true },
    "ui:title": "",
    "ui:description": "",
  };
  const stripped: Record<string, Record<string, unknown>> = {};
  for (const [name, property] of Object.entries(properties)) {
    const { description, ...rest } = property;
    stripped[name] = rest;
    if (typeof description === "string") uiSchema[name] = { "ui:help": description };
  }
  return { schema: { ...schema, properties: stripped } as RJSFSchema, uiSchema };
}

/** Renders a parameter form from a JSON schema. Renders nothing for schemas without parameters. */
export function SchemaForm({ schema, value, onChange }: SchemaFormProps) {
  const form = useMemo(() => compact(schema), [schema]);
  if (!hasParameters(schema)) return null;
  return (
    <Form
      schema={form.schema}
      uiSchema={form.uiSchema}
      formData={value}
      validator={validator}
      liveValidate
      showErrorList={false}
      onChange={(event) => onChange((event.formData ?? {}) as Record<string, unknown>)}
    />
  );
}
