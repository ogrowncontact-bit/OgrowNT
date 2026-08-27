import { SupportRequestForm } from "@/components/SupportRequestForm";
import { IssueReportForm } from "@/components/IssueReportForm";

export default function SupportPage() {
  return (
    <>
      <SupportRequestForm />
      <div className="mx-auto max-w-lg px-6 pb-16">
        <IssueReportForm />
      </div>
    </>
  );
}
