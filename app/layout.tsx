import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "三大赛道高赔率研究系统",
  description: "机器人、商业航天与AI三大赛道的高赔率投资研究终端",
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
  other: {
    "codex-preview": "development",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className="antialiased">{children}</body>
    </html>
  );
}
