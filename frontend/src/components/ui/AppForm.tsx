import type { ReactNode } from "react";
import type { UseFormReturn, FieldValues } from "react-hook-form";
import { FormProvider } from "react-hook-form";
import Box from "@mui/material/Box";

interface AppFormProps<T extends FieldValues> {
  methods: UseFormReturn<T>;
  onSubmit: (data: T) => void | Promise<void>;
  children: ReactNode;
  gap?: number;
}

export function AppForm<T extends FieldValues>({
  methods,
  onSubmit,
  children,
  gap = 2,
}: AppFormProps<T>) {
  return (
    <FormProvider {...methods}>
      <Box
        component="form"
        noValidate
        onSubmit={methods.handleSubmit(onSubmit)}
        sx={{ display: "flex", flexDirection: "column", gap }}
      >
        {children}
      </Box>
    </FormProvider>
  );
}
