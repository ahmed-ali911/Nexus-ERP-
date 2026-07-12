import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { AppButton } from "@/components/ui";
import { useNavigate } from "react-router-dom";

export default function NotFound() {
  const navigate = useNavigate();
  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "80vh",
        gap: 2,
      }}
    >
      <Typography variant="h2" color="text.secondary" sx={{ fontWeight: 700 }}>
        404
      </Typography>
      <Typography variant="body1" color="text.secondary">
        Page not found
      </Typography>
      <AppButton appVariant="secondary" onClick={() => navigate("/app")}>
        Go home
      </AppButton>
    </Box>
  );
}
