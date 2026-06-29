import { create } from "zustand";
import type { User } from "../api/auth";
import { getMe } from "../api/auth";

interface AuthState {
  user: User | null;
  token: string | null;
  loading: boolean;
  setAuth: (token: string, user: User) => void;
  logout: () => void;
  fetchUser: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: JSON.parse(localStorage.getItem("user") || "null"),
  token: localStorage.getItem("token"),
  loading: false,

  setAuth: (token, user) => {
    localStorage.setItem("token", token);
    localStorage.setItem("user", JSON.stringify(user));
    set({ token, user });
  },

  logout: () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    set({ token: null, user: null });
  },

  fetchUser: async () => {
    set({ loading: true });
    try {
      const user = await getMe();
      localStorage.setItem("user", JSON.stringify(user));
      set({ user });
    } catch {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
      set({ token: null, user: null });
    } finally {
      set({ loading: false });
    }
  },
}));
