import { Controller, useFormContext } from "react-hook-form";
import Checkbox from "@mui/material/Checkbox";
import FormControlLabel from "@mui/material/FormControlLabel";

interface AppFormCheckboxProps {
  name: string;
  label: string;
  disabled?: boolean;
}

export function AppFormCheckbox({ name, label, disabled }: AppFormCheckboxProps) {
  const { control } = useFormContext();
  return (
    <Controller
      name={name}
      control={control}
      render={({ field }) => (
        <FormControlLabel
          control={
            <Checkbox
              checked={field.value ?? false}
              onChange={(e) => field.onChange(e.target.checked)}
              size="small"
              disabled={disabled}
            />
          }
          label={label}
          sx={{ "& .MuiFormControlLabel-label": { fontSize: "0.875rem" } }}
        />
      )}
    />
  );
}
