import { redirect } from "next/navigation";

/** La home porta alla dashboard; il proxy reindirizza al login se serve. */
export default function Home() {
  redirect("/dashboard");
}
