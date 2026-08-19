interface PaymentFailedParams {
  assessmentName: string;
  retryUrl: string;
}

/** Sent when a checkout session expires unpaid (the real, provider-confirmed signal — see packages/payments' PaymentCancelledEvent), not a guessed timeout. Distinct in timing from the existing checkout-reminder nudge sent 1h after checkout starts. */
export function renderPaymentFailedEmail(params: PaymentFailedParams): string {
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
                  Your payment wasn't completed
                </h1>
                <p style="margin:0 0 20px;font-size:15px;line-height:1.6;color:#4a453d;">
                  Your checkout for <strong>${escapeHtml(params.assessmentName)}</strong> wasn't finished, so you
                  haven't been charged. Your answers are still saved if you'd like to try again.
                </p>
                <a href="${params.retryUrl}"
                   style="display:inline-block;background-color:#6f342a;color:#fff7ef;text-decoration:none;padding:14px 24px;border-radius:14px;font-size:15px;font-weight:500;">
                  Try Again
                </a>
              </td>
            </tr>
            <tr>
              <td style="padding:20px 28px 28px;border-top:1px solid #e6dcc8;">
                <p style="margin:0;font-size:12px;line-height:1.6;color:#78705f;">
                  This is a one-time notice about this specific checkout attempt, not a recurring email.
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
