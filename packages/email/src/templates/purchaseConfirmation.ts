interface PurchaseConfirmationParams {
  assessmentName: string;
  priceLabel: string;
  purchaseDateLabel: string;
  statusUrl: string;
}

/** Sent the moment payment is confirmed, before report generation finishes — doubles as the "we're preparing it" notice so the customer isn't left wondering between payment and the separate report-ready email. */
export function renderPurchaseConfirmationEmail(params: PurchaseConfirmationParams): string {
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
                  Purchase confirmed
                </h1>
                <p style="margin:0 0 20px;font-size:15px;line-height:1.6;color:#4a453d;">
                  Thanks for unlocking your <strong>${escapeHtml(params.assessmentName)}</strong> report. We're
                  preparing your personalized profile now — you'll get another email the moment it's ready.
                </p>
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 20px;font-size:14px;color:#4a453d;">
                  <tr>
                    <td style="padding:6px 0;color:#78705f;">Product</td>
                    <td style="padding:6px 0;text-align:right;">${escapeHtml(params.assessmentName)}</td>
                  </tr>
                  <tr>
                    <td style="padding:6px 0;color:#78705f;">Amount</td>
                    <td style="padding:6px 0;text-align:right;">${escapeHtml(params.priceLabel)}</td>
                  </tr>
                  <tr>
                    <td style="padding:6px 0;color:#78705f;">Date</td>
                    <td style="padding:6px 0;text-align:right;">${escapeHtml(params.purchaseDateLabel)}</td>
                  </tr>
                </table>
                <a href="${params.statusUrl}"
                   style="display:inline-block;background-color:#6f342a;color:#fff7ef;text-decoration:none;padding:14px 24px;border-radius:14px;font-size:15px;font-weight:500;">
                  View Status
                </a>
              </td>
            </tr>
            <tr>
              <td style="padding:20px 28px 28px;border-top:1px solid #e6dcc8;">
                <p style="margin:0;font-size:12px;line-height:1.6;color:#78705f;">
                  This is a receipt for a report you purchased, not a marketing email.
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
