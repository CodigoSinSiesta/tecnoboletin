// Cliente Supabase compartido (browser). La publishable key es publica por
// diseno -- la seguridad real esta en las politicas RLS de cada tabla.
import { createClient, type Session, type SupabaseClient } from '@supabase/supabase-js';

const SUPABASE_URL = 'https://rjfrceapcdlhpukdsixo.supabase.co';
const SUPABASE_KEY = 'sb_publishable_rwEHLqlaHX0hHGLuWDrTWg_p54vU_PV';

let client: SupabaseClient | null = null;

export function getSupabase(): SupabaseClient {
  if (!client) {
    client = createClient(SUPABASE_URL, SUPABASE_KEY, {
      auth: {
        // Config explicita del callback de login (no depender de defaults).
        // Flujo implicit y no PKCE a proposito: el metodo principal es el
        // magic link por email, y con PKCE el enlace del correo solo
        // funcionaria en el mismo navegador que lo pidio (el code_verifier
        // vive en localStorage). Con implicit, el enlace completa la sesion
        // en cualquier navegador/dispositivo. detectSessionInUrl procesa el
        // #access_token del callback automaticamente al cargar /cuenta/.
        flowType: 'implicit',
        detectSessionInUrl: true,
        persistSession: true,
        autoRefreshToken: true,
      },
    });
  }
  return client;
}

export type Role = 'user' | 'admin';

/**
 * getSession() con recuperacion.
 *
 * Este es un sitio estatico, no una SPA: cada navegacion crea un cliente
 * de Supabase nuevo. Si esa inicializacion aun no ha terminado de leer la
 * sesion persistida, o el token de acceso caduco mientras la pestaña
 * estaba en segundo plano (el refresco automatico no corre si el
 * temporizador esta pausado), getSession() puede devolver null una vez
 * aunque el refresh token siga siendo valido. Antes de darla por
 * perdida, se fuerza un refresco explicito contra Supabase.
 *
 * Usar SIEMPRE esto en vez de supabase.auth.getSession() para decidir si se
 * pinta interfaz de sesion iniciada (botones de guardar, gates de rol...):
 * con el getSession() pelado, un null transitorio deja al usuario viendo la
 * pantalla de "inicia sesion" o sin los botones de guardado aunque su sesion
 * siga siendo valida.
 *
 * No cuesta una llamada de red extra a quien no ha iniciado sesion: sin
 * refresh_token guardado, refreshSession() falla en local sin salir a red.
 */
export async function getSessionResilient(): Promise<Session | null> {
  const supabase = getSupabase();
  const { data: { session } } = await supabase.auth.getSession();
  if (session) return session;
  const { data } = await supabase.auth.refreshSession();
  return data.session;
}

/**
 * Rol de la sesion actual, o null si de verdad no hay sesion.
 *
 * El rol vive en la tabla `user_profiles`, no en `app_metadata`: en un
 * sitio estatico no hay backend con service_role, y app_metadata solo se
 * puede escribir con esa clave. Con la tabla, la RLS es a la vez la
 * barrera real (quien puede cambiar roles) y el dato que la interfaz lee,
 * y la gestion se puede hacer desde la propia web (/cuenta/usuarios/).
 *
 * Un usuario no puede autoascenderse: la politica de UPDATE exige
 * is_admin(auth.uid()), evaluada en Postgres.
 *
 * Los errores de red o del propio Supabase al leer el rol se propagan
 * (no se devuelve null): quien llama debe distinguir "confirmado sin
 * sesion" de "no se pudo comprobar", porque la primera manda a iniciar
 * sesion y la segunda solo merece un reintento.
 */
export async function fetchRole(): Promise<Role | null> {
  const supabase = getSupabase();
  const session = await getSessionResilient();
  if (!session) return null;
  const { data, error } = await supabase
    .from('user_profiles')
    .select('role')
    .eq('id', session.user.id)
    .maybeSingle();
  if (error) throw error;
  return (data?.role as Role) ?? 'user';
}

/** Atajo de lectura: ¿la sesion actual es de administracion? */
export async function isAdmin(): Promise<boolean> {
  return (await fetchRole()) === 'admin';
}

/** URL absoluta de vuelta tras un login OAuth/magic-link, respetando el
 *  base path (/tecnoboletin) tanto en produccion como en local. */
export function accountUrl(): string {
  const base = (import.meta.env.BASE_URL ?? '/').replace(/\/?$/, '/');
  return new URL(`${base}cuenta/`, window.location.origin).toString();
}
