interface PrivacyConfirmParams {
  action: "export" | "delete";
  confirmUrl: string;
}

/** Double opt-in for GDPR self-serve export/delete — the link only lands on a confirmation page, never performs the action itself (email link-scanners pre-fetch links, so a GET that acts would be unsafe). See docs/ARCHITECTURE.md §12. */
export function renderPrivacyConfirmEmail(params: PrivacyConfirmParams): string {
  const isDelete = params.action === "delete";
  const heading = isDelete ? "Confirm deleting your data" : "Confirm your data export";
  const body = isDelete
    ? "Click below to permanently delete your INNER data. This can't be undone — your assessment answers and account will be erased. Purchase records are kept in anonymized form only where required by law."
    : "Click below to download a copy of everything INNER has on file for you.";
  const cta = isDelete ? "Review & Confirm Deletion" : "Review & Download My Data";

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
                  ${escapeHtml(heading)}
                </h1>
                <p style="margin:0 0 20px;font-size:15px;line-height:1.6;color:#4a453d;">
                  ${escapeHtml(body)}
                </p>
                <a href="${params.confirmUrl}"
                   style="display:inline-block;background-color:#6f342a;color:#fff7ef;text-decoration:none;padding:14px 24px;border-radius:14px;font-size:15px;font-weight:500;">
                  ${escapeHtml(cta)}
                </a>
              </td>
            </tr>
            <tr>
              <td style="padding:20px 28px 28px;border-top:1px solid #e6dcc8;">
                <p style="margin:0;font-size:12px;line-height:1.6;color:#78705f;">
                  This link expires in 30 minutes and doesn't do anything by itself — you'll confirm on the next page
                  before anything happens. Didn't request this? You can safely ignore this email.
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
