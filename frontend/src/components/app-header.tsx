"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { useAuth } from "@/context/auth-context";

interface AppHeaderProps {
  title: string;
  /** Optional links rendered next to the title. */
  links?: { href: string; label: string }[];
}

export function AppHeader({ title, links = [] }: AppHeaderProps) {
  const { user, logout } = useAuth();
  const router = useRouter();

  async function handleLogout() {
    await logout();
    router.replace("/login");
  }

  return (
    <header className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 bg-slate-900/60 px-6 py-4">
      <div className="flex items-center gap-4">
        <span className="text-lg font-semibold text-slate-100">{title}</span>
        <nav className="flex items-center gap-3 text-sm">
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="text-slate-400 transition hover:text-slate-200"
            >
              {link.label}
            </Link>
          ))}
        </nav>
      </div>
      <div className="flex items-center gap-3 text-sm">
        {user && (
          <span className="text-slate-400">
            {user.username}
            <span className="ml-2 rounded-full border border-slate-700 px-2 py-0.5 text-xs text-slate-300">
              {user.role}
            </span>
          </span>
        )}
        <button
          onClick={handleLogout}
          className="rounded-lg border border-slate-700 px-3 py-1.5 text-slate-300 transition hover:border-slate-500 hover:text-slate-100"
        >
          Log out
        </button>
      </div>
    </header>
  );
}
