import { Controller, useFormContext } from "react-hook-form";
import { AppSelect } from "./AppSelect";
import type { SelectOption } from "./AppSelect";

interface AppFormSelectProps {
  name: string;
  label?: string;
  options: SelectOption[];
  helperText?: string;
  disabled?: boolean;
  fullWidth?: boolean;
}

export function AppFormSelect({
  name,
  label,
  options,
  helperText,
  disabled,
  fullWidth,
}: AppFormSelectProps) {
  const { control } = useFormContext();
  return (
    <Controller
      name={name}
      control={control}
      render={({ field, fieldState }) => (
        <AppSelect
          {...field}
          label={label}
          options={options}
          helperText={fieldState.error?.message ?? helperText}
          error={!!fieldState.error}
          disabled={disabled}
          fullWidth={fullWidth}
          onChange={(e) => field.onChange(e.target.value)}
        />
      )}
    />
  );
}
