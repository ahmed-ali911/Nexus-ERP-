import {
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  FormHelperText,
  type SelectProps,
} from "@mui/material";
import { useId } from "react";

export interface SelectOption {
  value: string | number;
  label: string;
}

export interface AppSelectProps extends Omit<SelectProps, "labelId"> {
  label?: string;
  options: SelectOption[];
  helperText?: string;
  error?: boolean;
  fullWidth?: boolean;
}

export function AppSelect({
  label,
  options,
  helperText,
  error,
  fullWidth = true,
  size = "small",
  ...rest
}: AppSelectProps) {
  const id = useId();
  return (
    <FormControl fullWidth={fullWidth} size={size} error={error}>
      {label && <InputLabel id={id}>{label}</InputLabel>}
      <Select labelId={id} label={label} {...rest}>
        {options.map((o) => (
          <MenuItem key={o.value} value={o.value}>
            {o.label}
          </MenuItem>
        ))}
      </Select>
      {helperText && <FormHelperText>{helperText}</FormHelperText>}
    </FormControl>
  );
}
