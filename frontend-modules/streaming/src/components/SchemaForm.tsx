import Form from "@rjsf/mantine";
import type { RJSFSchema, UiSchema } from "@rjsf/utils";
import validator from "@rjsf/validator-ajv8";

type SchemaFormProps = {
  /** JSON schema of the parameters, as provided by the backend catalog. */
  schema: Record<string, unknown>;
  value: Record<string, unknown>;
  onChange: (value: Record<string, unknown>) => void;
};

const uiSchema: UiSchema = {
  "ui:submitButtonOptions": { norender: true },
  // The schema's own title and description come from the backend model's name and docstring.
  "ui:title": "",
  "ui:description": "",
};

/** Whether a JSON schema describes at least one parameter. */
export function hasParameters(schema: Record<string, unknown>): boolean {
  const properties = schema.properties;
  return typeof properties === "object" && properties !== null && Object.keys(properties).length > 0;
}

/** Renders a parameter form from a JSON schema. Renders nothing for schemas without parameters. */
export function SchemaForm({ schema, value, onChange }: SchemaFormProps) {
  if (!hasParameters(schema)) return null;
  return (
    <Form
      schema={schema as RJSFSchema}
      uiSchema={uiSchema}
      formData={value}
      validator={validator}
      liveValidate
      showErrorList={false}
      onChange={(event) => onChange((event.formData ?? {}) as Record<string, unknown>)}
    />
  );
}
