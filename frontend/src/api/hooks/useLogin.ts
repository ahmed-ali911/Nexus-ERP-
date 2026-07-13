import { useMutation } from "@tanstack/react-query";
import apiClient from "../client";

export interface LoginCredentials {
  company_code: string;
  username: string;
  password: string;
}

interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface BackendUser {
  id: number;
  company_id: number;
  username: string;
  email: string;
  full_name_en: string;
  full_name_ar: string;
  is_active: boolean;
  is_superuser: boolean;
}

export interface LoginResult {
  tokens: TokenResponse;
  user: BackendUser;
}

async function loginFn(credentials: LoginCredentials): Promise<LoginResult> {
  const { data: tokens } = await apiClient.post<TokenResponse>(
    "/api/v1/auth/login",
    credentials
  );
  // Store tokens before /me so the Authorization header is set
  localStorage.setItem("access_token", tokens.access_token);
  localStorage.setItem("refresh_token", tokens.refresh_token);

  const { data: user } = await apiClient.get<BackendUser>("/api/v1/auth/me");
  return { tokens, user };
}

export function useLogin() {
  return useMutation({ mutationFn: loginFn });
}
