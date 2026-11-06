import type { Metadata, Viewport } from "next";
import { Geist } from "next/font/google";

import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: { default: "Assistente WhatsApp", template: "%s · Assistente WhatsApp" },
  description: "Prenotazioni automatiche su WhatsApp per attività locali",
};

export const viewport: Viewport = {
  themeColor: "#ffffff",
  viewportFit: "cover",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="it" className={`${geistSans.variable} h-full antialiased`}>
      <body className="min-h-dvh bg-slate-50 font-sans text-slate-900">{children}</body>
    </html>
  );
}
