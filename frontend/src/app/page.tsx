import AnalyticsDashboard from "@/features/agent/analytics-dashboard";
import { AuthGuard } from "@/components/auth-guard";

export default function HomePage() {
  return (
    <AuthGuard>
      <AnalyticsDashboard />
    </AuthGuard>
  );
}
