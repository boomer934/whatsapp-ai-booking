/** Variabili d'ambiente validate: un errore chiaro invece di un crash oscuro. */

function required(name: string, value: string | undefined): string {
  if (!value) {
    throw new Error(`Variabile d'ambiente mancante: ${name} (vedi frontend/.env.example)`);
  }
  return value;
}

// Le NEXT_PUBLIC_* vanno lette con accesso statico per essere incluse nel bundle client.
export const SUPABASE_URL = required(
  "NEXT_PUBLIC_SUPABASE_URL",
  process.env.NEXT_PUBLIC_SUPABASE_URL,
);
export const SUPABASE_PUBLISHABLE_KEY = required(
  "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY",
  process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
);
