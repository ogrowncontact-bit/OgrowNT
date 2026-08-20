import type { Metadata } from "next";
import { LegalDocument } from "@/components/LegalDocument";
import { getSiteUrl } from "@/lib/siteUrl";

export const metadata: Metadata = {
  title: "Refund Policy",
  description: "INNER's refund policy for premium report purchases.",
  alternates: { canonical: `${getSiteUrl()}/refund` },
};

export default function RefundPage() {
  return (
    <LegalDocument title="Refund Policy" lastUpdated="[TBD — set on legal review]">
      <section>
        <h2>1. Digital content, delivered immediately</h2>
        <p>
          A premium report is a one-time digital purchase. Generation begins as soon as payment is confirmed, and the
          report is typically available within minutes. Because of this, standard consumer &quot;cooling-off&quot;
          withdrawal windows that apply to physical goods may not apply the same way once generation has started —
          see our <a href="/terms" className="underline">Terms of Service</a>, Section 7, for the fuller explanation.
        </p>
      </section>

      <section>
        <h2>2. When we do issue a refund</h2>
        <p>
          <strong>[Refund eligibility criteria — TBD, needs explicit legal sign-off.]</strong> Today, refund requests
          are reviewed and handled at our discretion — for example, a duplicate charge, a report that failed to
          generate, or a genuine payment error. Contact us using the details below and we&apos;ll look into it.
        </p>
      </section>

      <section>
        <h2>3. How to request one</h2>
        <p>
          Use the <a href="/support" className="underline">support page</a> and describe what happened, including
          the email address used at checkout. An admin reviews every request individually — there is no automated
          refund flow.
        </p>
      </section>

      <section>
        <h2>4. Contact</h2>
        <p>
          Questions about a charge or a refund: <strong>[contact email — TBD]</strong>.
        </p>
      </section>
    </LegalDocument>
  );
}
