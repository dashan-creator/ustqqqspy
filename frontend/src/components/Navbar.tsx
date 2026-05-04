"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/", label: "总览" },
  { href: "/watchlist", label: "股票池" },
  { href: "/trades", label: "交易日志" },
  { href: "/strategy", label: "策略" },
  { href: "/risk", label: "风控" },
];

export function Navbar() {
  const pathname = usePathname();
  return (
    <nav className="bg-gray-900 text-white p-4 flex gap-6">
      <span className="font-bold text-lg">USStock 量化交易</span>
      {links.map((l) => (
        <Link
          key={l.href}
          href={l.href}
          className={`hover:text-blue-400 ${pathname === l.href ? "text-blue-400 font-semibold" : ""}`}
        >
          {l.label}
        </Link>
      ))}
    </nav>
  );
}
