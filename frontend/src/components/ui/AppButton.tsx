import { forwardRef } from "react";
import Button, { type ButtonProps } from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";

export interface AppButtonProps extends Omit<ButtonProps, "color"> {
  /** Visual variant beyond MUI's contained/outlined/text */
  appVariant?: "primary" | "secondary" | "text" | "danger";
  loading?: boolean;
}

const variantMap: Record<
  NonNullable<AppButtonProps["appVariant"]>,
  Pick<ButtonProps, "variant" | "color">
> = {
  primary:   { variant: "contained", color: "primary" },
  secondary: { variant: "outlined",  color: "primary" },
  text:      { variant: "text",      color: "primary" },
  danger:    { variant: "contained", color: "error" },
};

export const AppButton = forwardRef<HTMLButtonElement, AppButtonProps>(
  ({ appVariant = "primary", loading, disabled, children, startIcon, ...rest }, ref) => {
    const mapped = variantMap[appVariant];
    return (
      <Button
        ref={ref}
        {...mapped}
        {...rest}
        disabled={disabled || loading}
        startIcon={loading ? <CircularProgress size={16} color="inherit" /> : startIcon}
      >
        {children}
      </Button>
    );
  }
);
AppButton.displayName = "AppButton";
