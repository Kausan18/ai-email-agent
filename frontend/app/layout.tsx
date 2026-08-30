import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const jbMono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-jbmono" });

export const metadata: Metadata = {
  title: "Email Agent",
  description: "AI context-aware email assistant — review dashboard",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${jbMono.variable}`}>
      <body className="min-h-screen font-sans">
        <div className="flex min-h-screen">
          {/* Sidebar — only /inbox is wired in V1; the rest are placeholders
              for the pages listed in the roadmap (/uncertain, /chat) so the
              nav shape is already correct when those pages get built. */}
          <aside className="w-56 shrink-0 border-r border-border bg-surface px-4 py-6">
            <div className="mb-8 px-2 text-sm font-semibold tracking-wide text-text">
              Email Agent
            </div>
            <nav className="flex flex-col gap-1 text-sm">
              <NavItem label="Inbox" href="/inbox" active />
              <NavItem label="Uncertain" href="#" disabled />
              <NavItem label="Chat" href="#" disabled />
            </nav>
          </aside>
          <main className="flex-1 overflow-y-auto">{children}</main>
        </div>
      </body>
    </html>
  );
}

function NavItem({
  label,
  href,
  active = false,
  disabled = false,
}: {
  label: string;
  href: string;
  active?: boolean;
  disabled?: boolean;
}) {
  if (disabled) {
    return (
      <span
        aria-disabled="true"
        className={`rounded-md px-2 py-1.5 text-textMuted/40 ${
          active ? "bg-surfaceHover text-text" : "cursor-not-allowed"
        }`}
      >
        {label}
        <span className="ml-1.5 text-[10px] text-textMuted/40">(V1 roadmap)</span>
      </span>
    );
  }

  return (
    <a
      href={href}
      className={`rounded-md px-2 py-1.5 transition-colors ${
        active
          ? "bg-surfaceHover text-text"
          : "text-textMuted hover:bg-surfaceHover hover:text-text"
      }`}
    >
      {label}
    </a>
  );
}