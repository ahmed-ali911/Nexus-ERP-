import { Controller, useFormContext, type RegisterOptions } from "react-hook-form";
import { AppInput, type AppInputProps } from "./AppInput";

interface AppFormInputProps extends Omit<AppInputProps, "name"> {
  name: string;
  rules?: RegisterOptions;
}

export function AppFormInput({ name, rules, ...rest }: AppFormInputProps) {
  const { control } = useFormContext();
  return (
    <Controller
      name={name}
      control={control}
      rules={rules}
      render={({ field, fieldState }) => (
        <AppInput
          {...field}
          {...rest}
          error={rest.error ?? !!fieldState.error}
          helperText={rest.helperText ?? fieldState.error?.message}
        />
      )}
    />
  );
}
