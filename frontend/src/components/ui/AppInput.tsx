import { forwardRef } from "react";
import TextField, { type TextFieldProps } from "@mui/material/TextField";

export type AppInputProps = TextFieldProps;

export const AppInput = forwardRef<HTMLDivElement, AppInputProps>(
  ({ size = "small", fullWidth = true, ...rest }, ref) => (
    <TextField ref={ref} size={size} fullWidth={fullWidth} {...rest} />
  )
);
AppInput.displayName = "AppInput";
