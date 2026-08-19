import { redirect } from "next/navigation";

/** Friendly alias for /access/reports, which predates this name and is what every other magic-link-authenticated link in the codebase already points to. */
export default function MyReportsRedirect() {
  redirect("/access/reports");
}
