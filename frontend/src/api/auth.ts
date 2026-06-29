import client from "./client";

export interface User {
  id: number;
  phone: string | null;
  email: string | null;
  nickname: string;
  avatar_url: string;
  daily_quota: number;
  is_admin: boolean;
  created_at: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface RegisterResponse {
  message: string;
  user: User;
}

export async function register(params: {
  phone?: string;
  email?: string;
  password: string;
  nickname?: string;
}): Promise<RegisterResponse> {
  const { data } = await client.post("/auth/register", params);
  return data;
}

export async function login(account: string, password: string): Promise<TokenResponse> {
  const { data } = await client.post("/auth/login", { account, password });
  return data;
}

export async function getMe(): Promise<User> {
  const { data } = await client.get("/auth/me");
  return data;
}

export async function updateMe(params: { nickname?: string; avatar_url?: string }): Promise<User> {
  const { data } = await client.patch("/auth/me", params);
  return data;
}
