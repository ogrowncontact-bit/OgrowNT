import { getOperationalAlerts } from "@/lib/admin/notificationsReader";
import { AdminGlobalSearch } from "@/components/admin/AdminGlobalSearch";
import { AdminNotificationBell } from "@/components/admin/AdminNotificationBell";

export async function AdminTopBar() {
  const alerts = await getOperationalAlerts();

  return (
    <div className="flex items-center gap-3">
      <div className="hidden sm:block">
        <AdminGlobalSearch />
      </div>
      <AdminNotificationBell alerts={alerts} />
    </div>
  );
}
