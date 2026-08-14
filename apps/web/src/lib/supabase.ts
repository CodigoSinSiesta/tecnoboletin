// Cliente Supabase compartido (browser). La publishable key es publica por
// diseno -- la seguridad real esta en las politicas RLS de cada tabla.
import { createClient, type SupabaseClient } from '@supabase/supabase-js';

const SUPABASE_URL = 'https://rjfrceapcdlhpukdsixo.supabase.co';
const SUPABASE_KEY = 'sb_publishable_rwEHLqlaHX0hHGLuWDrTWg_p54vU_PV';

let client: SupabaseClient | null = null;

export function getSupabase(): SupabaseClient {
  if (!client) {
    client = createClient(SUPABASE_URL, SUPABASE_KEY);
  }
  return client;
}

/** URL absoluta de vuelta tras un login OAuth/magic-link, respetando el
 *  base path (/tecnoboletin) tanto en produccion como en local. */
export function accountUrl(): string {
  const base = (import.meta.env.BASE_URL ?? '/').replace(/\/?$/, '/');
  return new URL(`${base}cuenta/`, window.location.origin).toString();
}
