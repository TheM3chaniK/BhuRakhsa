"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { UserProfile } from "./types";
import { api } from "./api";
import { useRouter, usePathname } from "next/navigation";

interface AuthContextType {
  user: UserProfile | null;
  token: string | null;
  loading: boolean;
  login: (email: string, pass: string) => Promise<void>;
  register: (
    email: string,
    pass: string,
    name: string,
    phone?: string
  ) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    let isMounted = true;
    const existingToken = api.getToken();

    if (existingToken) {
      setToken(existingToken);
      api
        .getMe()
        .then((u) => {
          if (isMounted) setUser(u);
        })
        .catch(() => {
          if (isMounted) {
            api.setToken(null);
            setToken(null);
            setUser(null);
            if (pathname !== "/login") {
              router.push("/login");
            }
          }
        })
        .finally(() => {
          if (isMounted) setLoading(false);
        });
    } else {
      setLoading(false);
      if (pathname !== "/login") {
        router.push("/login");
      }
    }

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (!loading && !user && pathname !== "/login") {
      router.push("/login");
    }
  }, [pathname, loading, user, router]);

  const login = async (email: string, pass: string) => {
    const res = await api.login(email, pass);
    setToken(res.access_token);
    const u = await api.getMe();
    setUser(u);
  };

  const register = async (
    email: string,
    pass: string,
    name: string,
    phone?: string
  ) => {
    await api.register(email, pass, name, phone);
    await login(email, pass);
  };

  const logout = async () => {
    await api.logout();
    setToken(null);
    setUser(null);
    router.push("/login");
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        loading,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
