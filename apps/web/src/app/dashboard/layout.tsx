import type { ReactNode } from "react";
import { Sidebar } from "@/components/sidebar";
import { Toaster } from "@/components/toast";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="min-w-0 flex-1 px-6 py-8 md:ml-56 md:px-10">
        {children}
      </main>
      <Toaster />
    </div>
  );
}
