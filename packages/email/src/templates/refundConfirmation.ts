interface RefundConfirmationParams {
  assessmentName: string;
  refundAmountLabel: string;
  partial: boolean;
}

/** Transactional — a refund is a financial event that always warrants a receipt, whether the report itself stays accessible or not (see lib/admin/refunds.ts — refunds don't revoke access). */
export function renderRefundConfirmationEmail(params: RefundConfirmationParams): string {
  return `<!doctype html>
<html>
  <body style="margin:0;padding:0;background-color:#faf6ef;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,system-ui,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#faf6ef;padding:32px 16px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" style="max-width:480px;background-color:#ffffff;border-radius:20px;border:1px solid #e6dcc8;overflow:hidden;">
            <tr>
              <td style="padding:32px 28px 8px;">
                <p style="margin:0 0 12px;font-size:12px;letter-spacing:0.2em;text-transform:uppercase;color:#78705f;">INNER</p>
                <h1 style="margin:0 0 16px;font-family:Georgia,'Iowan Old Style','Palatino Linotype',ui-serif,serif;font-size:24px;line-height:1.3;color:#1c1a17;">
                  ${params.partial ? "Partial refund issued" : "Refund issued"}
                </h1>
                <p style="margin:0 0 20px;font-size:15px;line-height:1.6;color:#4a453d;">
                  We've refunded <strong>${escapeHtml(params.refundAmountLabel)}</strong> for your
                  <strong>${escapeHtml(params.assessmentName)}</strong> purchase. It should appear on your original
                  payment method within a few business days, depending on your bank or card issuer.
                  ${params.partial ? "" : " You'll keep access to the report you already received."}
                </p>
              </td>
            </tr>
            <tr>
              <td style="padding:20px 28px 28px;border-top:1px solid #e6dcc8;">
                <p style="margin:0;font-size:12px;line-height:1.6;color:#78705f;">
                  Questions about this refund? Reply to this email and we'll help.
                </p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>`;
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
}
