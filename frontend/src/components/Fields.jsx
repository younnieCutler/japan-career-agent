/* Form controls, wrapped once.

   SEED's Select is a composed primitive: the root takes `value: string[]` and calls back with an
   array, and each item carries `value`. Wrapping it here means the screens deal in one scalar and
   the shape lives in one file rather than in every form.

   The checkbox is the browser's. SEED's is a namespace whose Indicator needs an icon node from a
   package this bundle does not carry, and a native checkbox is already keyboard-operable, already
   announced correctly, and already themed by `accent-color`. */

import React from "react";
import { Select, TextField } from "@seed-design/react";

export function Field({ label, help, children }) {
  const id = React.useId();
  return (
    <div className="field">
      <label className="field__label" htmlFor={id}>{label}</label>
      {React.cloneElement(children, { id })}
      {help ? <p className="field__help">{help}</p> : null}
    </div>
  );
}

export const Line = ({ id, value, onChange, type = "text" }) => (
  <TextField.Root size="medium">
    <TextField.Input id={id} type={type} value={value} onChange={(event) => onChange(event.target.value)} />
  </TextField.Root>
);

export const Block = ({ id, value, onChange, rows = 4 }) => (
  <TextField.Root size="medium">
    <TextField.Textarea id={id} rows={rows} value={value} onChange={(event) => onChange(event.target.value)} />
  </TextField.Root>
);

export function Choice({ id, value, onChange, options, label }) {
  return (
    <Select.Root value={[value]} onValueChange={(next) => onChange(next[0])}>
      <Select.Trigger id={id} aria-label={label}>
        {/* The trigger renders the current option's own text: SEED's Select.Value reads from the
            item list, which is closed at this point, so an empty box is what it would show. */}
        <Select.Value>{options.find(([key]) => key === value)?.[1]}</Select.Value>
      </Select.Trigger>
      <Select.Content>
        {options.map(([key, text]) => (
          <Select.Item key={key} value={key}>
            <Select.ItemLabel>{text}</Select.ItemLabel>
          </Select.Item>
        ))}
      </Select.Content>
    </Select.Root>
  );
}

export const CheckBox = ({ id, checked, disabled, onChange, label }) => (
  <input
    id={id}
    type="checkbox"
    className="checkbox"
    checked={checked}
    disabled={disabled}
    aria-label={label}
    onChange={(event) => onChange(event.target.checked)}
  />
);
