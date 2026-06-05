const LOCAL_TZ = Intl.DateTimeFormat().resolvedOptions().timeZone;

export function toLocalTime(utcString, options = {}) {
  if (!utcString) return '—';
  try {
    return new Date(utcString).toLocaleString(undefined, {
      timeZone: LOCAL_TZ,
      ...options,
    });
  } catch {
    return '—';
  }
}

export function todayLocalDateString() {
  const now = new Date();
  return [
    now.getFullYear(),
    String(now.getMonth() + 1).padStart(2, '0'),
    String(now.getDate()).padStart(2, '0'),
  ].join('-');
}

export async function getReliableNow() {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 2000);
    const res = await fetch('https://worldtimeapi.org/api/ip', { signal: controller.signal });
    clearTimeout(timeout);
    const data = await res.json();
    return new Date(data.datetime);
  } catch {
    return new Date();
  }
}
