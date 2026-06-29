import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "../stores/authStore";

export function useRequireAuth() {
  const { token, user, fetchUser } = useAuthStore();
  const navigate = useNavigate();

  useEffect(() => {
    if (!token) {
      navigate("/login");
    } else if (!user) {
      fetchUser();
    }
  }, [token, user, navigate, fetchUser]);

  return { token, user, isAuthenticated: !!token && !!user };
}
