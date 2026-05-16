import type { GrantsResult } from './kstartup-api';
import { ddays, formatDate, formatDDay } from './utils';

// 공고명이 [ ] 를 포함하면 MD 링크가 깨지므로 제거
function safeTitle(s: string): string {
  return s.replace(/[\[\]]/g, '').trim();
}

function normalize(s: string | null | undefined): string {
  if (!s) return '';
  return s.replace(/\r\n?/g, '\n').replace(/[ \t]+\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim();
}

function truncate(s: string, max: number): string {
  if (s.length <= max) return s;
  return s.slice(0, max).trimEnd() + '…';
}

function kstString(d: Date): string {
  const kst = new Date(d.getTime() + 9 * 60 * 60_000);
  const date = formatDate(kst);
  const hh = String(kst.getUTCHours()).padStart(2, '0');
  const mm = String(kst.getUTCMinutes()).padStart(2, '0');
  return `${date} ${hh}:${mm} KST`;
}

export function buildMarkdown(result: GrantsResult): string {
  const { grants, fetchedAt } = result;
  const out: string[] = [];

  out.push('---');
  out.push('title: K-Startup 모집중 공고');
  out.push(`total: ${grants.length}`);
  out.push(`fetched_at: ${fetchedAt.toISOString()}`);
  out.push(`fetched_at_kst: "${kstString(fetchedAt)}"`);
  out.push('source: https://www.data.go.kr/data/15125364/openapi.do');
  out.push('refresh: 매일 KST 02:00');
  out.push('---');
  out.push('');
  out.push(`# K-Startup 모집중 공고 (${grants.length}건)`);
  out.push('');
  out.push(
    `> 창업진흥원 K-Startup 공공데이터 API의 **모집중 공고 전체 목록**입니다. 마감일 가까운 순. 매일 KST 02:00 갱신.`
  );
  out.push('');
  out.push(
    `**AI/챗봇 사용 가이드:** 이 문서를 컨텍스트에 넣은 후, 사용자 프로필(예비/창업기업 여부, 업력, 연령, 지역, 관심 분야)에 맞는 공고를 추천하도록 요청하세요. 각 공고의 \`detail\` 링크가 K-Startup 원문입니다.`
  );
  out.push('');
  out.push(`---`);
  out.push('');

  grants.forEach((g, i) => {
    const dd = ddays(g.endDate);
    const ddStr = formatDDay(dd);
    const title = safeTitle(g.title);
    const link = g.detailUrl ?? g.guideUrl ?? g.applyUrl ?? '';

    out.push(`## ${i + 1}. ${link ? `[${title}](${link})` : title}`);
    out.push('');

    const meta: string[] = [];
    if (g.organization) meta.push(`- **기관**: ${g.organization}`);
    const cls: string[] = [];
    if (g.sprvInst) cls.push(`주관 ${g.sprvInst}`);
    if (g.category) cls.push(`분야 ${g.category}`);
    if (g.region) cls.push(`지역 ${g.region}`);
    if (cls.length) meta.push(`- ${cls.join(' · ')}`);
    if (g.endDate) {
      const range =
        (g.startDate ? formatDate(g.startDate) : '~') +
        ' ~ ' +
        formatDate(g.endDate);
      meta.push(`- **접수**: ${range} (${ddStr})`);
    }
    if (g.applyTargets.length) meta.push(`- **신청 대상**: ${g.applyTargets.join(', ')}`);
    if (g.bizYears.length) meta.push(`- **창업 기간**: ${g.bizYears.join(', ')}`);
    if (g.targetAges.length) meta.push(`- **대상 연령**: ${g.targetAges.join(', ')}`);
    if (g.contact) meta.push(`- **문의**: ${g.contact}`);
    if (g.detailUrl) meta.push(`- **detail**: ${g.detailUrl}`);

    out.push(...meta);

    const content = normalize(g.content);
    if (content) {
      out.push('');
      out.push(truncate(content, 1200));
    }

    const detail = normalize(g.applyTargetDetail);
    if (detail) {
      out.push('');
      out.push(`**신청 대상 상세**: ${truncate(detail, 500)}`);
    }
    const pref = normalize(g.preferential);
    if (pref) {
      out.push('');
      out.push(`**우대 사항**: ${truncate(pref, 400)}`);
    }
    const excl = normalize(g.excludeTarget);
    if (excl) {
      out.push('');
      out.push(`**제외 대상**: ${truncate(excl, 300)}`);
    }

    out.push('');
  });

  return out.join('\n');
}
