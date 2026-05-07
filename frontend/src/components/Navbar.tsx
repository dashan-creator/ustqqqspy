"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/", label: "总览" },
  { href: "/watchlist", label: "股票池" },
  { href: "/positions", label: "持仓" },
  { href: "/trades", label: "交易" },
  { href: "/strategy", label: "策略" },
  { href: "/risk", label: "风控" },
];

export function Navbar() {
  const pathname = usePathname();
  return (
    <nav style={{ backgroundColor: "var(--bg-secondary)", borderBottom: "1px solid var(--border)" }} className="px-6 py-3 flex items-center gap-6">
      <span className="font-bold text-lg" style={{ color: "var(--accent)" }}>USStock</span>
      {links.map((l) => (
        <Link
          key={l.href}
          href={l.href}
          className="text-sm font-medium transition-colors hover:opacity-80"
          style={{ color: pathname === l.href ? "var(--accent)" : "var(--text-secondary)" }}
        >
          {l.label}
        </Link>
      ))}
    </nav>
  );
}
