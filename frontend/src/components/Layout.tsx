import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";

const NAV = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/campaigns", label: "Campaigns" },
  { to: "/queue", label: "Message Queue" },
  { to: "/deals", label: "Deals" },
  { to: "/linkedin", label: "LinkedIn" },
  { to: "/settings", label: "Settings" },
];

export default function Layout() {
  const { me, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="min-h-screen">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-8">
            <span className="text-lg font-semibold text-brand-700">
              OpenOutreach
            </span>
            <nav className="flex gap-1">
              {NAV.map((n) => (
                <NavLink
                  key={n.to}
                  to={n.to}
                  end={n.end}
                  className={({ isActive }) =>
                    `rounded-md px-3 py-1.5 text-sm font-medium ${
                      isActive
                        ? "bg-brand-50 text-brand-700"
                        : "text-gray-600 hover:bg-gray-100"
                    }`
                  }
                >
                  {n.label}
                </NavLink>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-3 text-sm text-gray-600">
            <span>{me?.user.username}</span>
            <button
              className="btn-secondary"
              onClick={async () => {
                await logout();
                navigate("/login");
              }}
            >
              Sign out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}
