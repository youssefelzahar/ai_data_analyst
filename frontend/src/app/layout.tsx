import type { Metadata } from "next";
import "../styles/globals.css";
import { AuthProvider } from "@/context/auth-context";

export const metadata: Metadata = {
  title: "AI Data Analyst",
  description: "Upload datasets and analyze them with natural language.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-950 text-slate-100 antialiased">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
