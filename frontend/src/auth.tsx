import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { api, ApiError, type Me } from "./api";

interface AuthState {
  me: Me | null;
  loading: boolean;
  refresh: () => Promise<void>;
  login: (username: string, password: string) => Promise<void>;
  signup: (username: string, password: string, email?: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  async function refresh() {
    try {
      setMe(await api.get<Me>("/auth/me"));
    } catch (e) {
      if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
        setMe(null);
      } else {
        throw e;
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function login(username: string, password: string) {
    setMe(await api.post<Me>("/auth/login", { username, password }));
  }
  async function signup(username: string, password: string, email = "") {
    setMe(await api.post<Me>("/auth/signup", { username, password, email }));
  }
  async function logout() {
    await api.post("/auth/logout");
    setMe(null);
  }

  return (
    <AuthContext.Provider value={{ me, loading, refresh, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
