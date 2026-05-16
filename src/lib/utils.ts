// YYYYMMDD → Date (KST 자정)
// API가 시간대를 명시하지 않지만 한국 사업이므로 KST 기준으로 해석
export function parseKstartupDate(s: string | null | undefined): Date | null {
  if (!s) return null;
  const m = /^(\d{4})(\d{2})(\d{2})/.exec(s.trim());
  if (!m) return null;
  const [, y, mo, d] = m;
  // UTC로 만들고 9시간 빼서 KST 자정과 맞춘다 (KST 00:00 = UTC -9h = 전날 15:00)
  // → 그냥 UTC 자정으로 두면 D-day 계산이 단순. 시·분 단위 정확도가 필요하지 않으니 OK.
  const dt = new Date(Date.UTC(Number(y), Number(mo) - 1, Number(d)));
  return Number.isFinite(dt.getTime()) ? dt : null;
}

export function formatDate(d: Date | null): string {
  if (!d) return '';
  const y = d.getUTCFullYear();
  const m = String(d.getUTCMonth() + 1).padStart(2, '0');
  const day = String(d.getUTCDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

// 오늘 00:00(UTC) 기준 D-day. 음수면 마감, 0이면 오늘, 양수면 N일 남음
export function ddays(endDate: Date | null, today: Date = new Date()): number | null {
  if (!endDate) return null;
  const t = Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate());
  return Math.floor((endDate.getTime() - t) / 86_400_000);
}

export function formatDDay(n: number | null): string {
  if (n === null) return '';
  if (n < 0) return `마감`;
  if (n === 0) return `D-day`;
  return `D-${n}`;
}

export function splitCsv(s: string | null | undefined): string[] {
  if (!s) return [];
  return s.split(',').map((x) => x.trim()).filter(Boolean);
}

export function truncate(s: string | null | undefined, max: number): string {
  if (!s) return '';
  const t = s.replace(/\s+/g, ' ').trim();
  return t.length > max ? t.slice(0, max) + '…' : t;
}

// detl_pg_url이 가끔 스킴 누락
export function ensureHttps(url: string | null | undefined): string | null {
  if (!url) return null;
  const u = url.trim();
  if (!u) return null;
  if (/^https?:\/\//i.test(u)) return u;
  return `https://${u}`;
}
