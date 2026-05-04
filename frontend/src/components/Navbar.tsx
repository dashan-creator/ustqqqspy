"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/", label: "Dashboard" },
  { href: "/watchlist", label: "Watchlist" },
  { href: "/trades", label: "Trades" },
  { href: "/strategy", label: "Strategy" },
  { href: "/risk", label: "Risk" },
];

export function Navbar() {
  const pathname = usePathname();
  return (
    <nav className="bg-gray-900 text-white p-4 flex gap-6">
      <span className="font-bold text-lg">USStock</span>
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
