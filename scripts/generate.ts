import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { fetchAllActiveGrants } from '../src/lib/kstartup-api';
import { buildMarkdown } from '../src/lib/markdown';

// 로컬 개발: .env.local 직접 파싱 (의존성 없이).
// GitHub Actions: env로 주입되므로 이 블록은 건너뛰어짐.
function loadDotenvLocal(): void {
  if (process.env.KSTARTUP_API_KEY) return;
  if (!existsSync('.env.local')) return;
  const content = readFileSync('.env.local', 'utf8');
  for (const raw of content.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith('#')) continue;
    const eq = line.indexOf('=');
    if (eq < 0) continue;
    const key = line.slice(0, eq).trim();
    const value = line.slice(eq + 1).trim();
    if (key && !(key in process.env)) process.env[key] = value;
  }
}

async function main() {
  loadDotenvLocal();

  console.log('[generate] K-Startup API 호출 중...');
  const result = await fetchAllActiveGrants();
  console.log(
    `[generate] 모집중 ${result.grants.length}건 / ${result.pagesFetched}페이지 조회`
  );

  const md = buildMarkdown(result);
  writeFileSync('grants.md', md, 'utf8');
  console.log(`[generate] grants.md 작성 완료 (${md.length.toLocaleString()} chars)`);
}

main().catch((err) => {
  console.error('[generate] 실패:', err);
  process.exit(1);
});
