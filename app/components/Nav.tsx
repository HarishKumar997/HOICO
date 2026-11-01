"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  ["/", "Overview"],
  ["/forecast", "Demand forecast"],
  ["/capacity", "Capacity"],
  ["/scenarios", "Scenarios"],
  ["/quality", "Quality"],
  ["/about", "About"],
];

export function Nav() {
  const pathname = usePathname();
  return (
    <nav>
      <strong>HOICO</strong>
      <span>Capacity planning</span>
      {links.map(([href, label]) => (
        <Link key={href} href={href} aria-current={pathname === href ? "page" : undefined}>
          {label}
        </Link>
      ))}
    </nav>
  );
}
