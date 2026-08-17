export type { EmailProvider, SendEmailParams, SendResult, Attachment } from "./types";
export { ResendProvider } from "./resendProvider";
export { LocalProvider } from "./localProvider";
export { renderReportDeliveryEmail } from "./templates/reportDelivery";
export { renderCheckoutReminderEmail } from "./templates/checkoutReminder";
export { renderRecommendationNudgeEmail } from "./templates/recommendationNudge";
export { renderPrivacyConfirmEmail } from "./templates/privacyConfirm";
export { renderAccessLinkEmail } from "./templates/accessLink";
