import type { Grant, KStartupApiResponse, KStartupRawItem } from './types';
import { ensureHttps, parseKstartupDate, splitCsv } from './utils';

const API_URL =
  'https://apis.data.go.kr/B552735/kisedKstartupService01/getAnnouncementInformation01';

const PER_PAGE = 1000;
const MAX_PAGES = 10;          // 안전장치 (실측: 4페이지면 모집중 전체 커버)
const STOP_AFTER_EMPTY = 2;    // 모집중 0건이 연속 N페이지면 중단
const DELAY_MS = 100;

function getKey(): string {
  const key = process.env.KSTARTUP_API_KEY;
  if (!key) {
    throw new Error('KSTARTUP_API_KEY 환경변수가 설정되지 않았습니다.');
  }
  return key;
}

async function fetchPage(page: number, key: string): Promise<KStartupApiResponse> {
  const url = `${API_URL}?serviceKey=${encodeURIComponent(key)}&page=${page}&perPage=${PER_PAGE}&returnType=json`;
  // 페이지 단위 ISR(export const revalidate)이 갱신 주기를 관리.
  // fetch 응답이 2MB를 넘어 Next.js data cache는 어차피 못 담으므로 명시적으로 끔.
  const res = await fetch(url, { cache: 'no-store' });
  if (!res.ok) {
    throw new Error(`K-Startup API 응답 오류: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as KStartupApiResponse;
}

function todayYyyymmdd(): string {
  const d = new Date();
  // KST 자정 기준 비교를 위해 UTC+9 적용
  const kst = new Date(d.getTime() + 9 * 60 * 60_000);
  const y = kst.getUTCFullYear();
  const m = String(kst.getUTCMonth() + 1).padStart(2, '0');
  const day = String(kst.getUTCDate()).padStart(2, '0');
  return `${y}${m}${day}`;
}

function transform(raw: KStartupRawItem): Grant {
  return {
    pbancSn: raw.pbanc_sn,
    title: raw.biz_pbanc_nm ?? '(제목 없음)',
    organization: raw.pbanc_ntrp_nm ?? raw.sprv_inst ?? '',
    sprvInst: raw.sprv_inst,
    category: raw.supt_biz_clsfc,
    region: raw.supt_regin,
    applyTargets: splitCsv(raw.aply_trgt),
    bizYears: splitCsv(raw.biz_enyy),
    targetAges: splitCsv(raw.biz_trgt_age),
    startDate: parseKstartupDate(raw.pbanc_rcpt_bgng_dt),
    endDate: parseKstartupDate(raw.pbanc_rcpt_end_dt),
    detailUrl: ensureHttps(raw.detl_pg_url),
    guideUrl: ensureHttps(raw.biz_gdnc_url),
    applyUrl: ensureHttps(raw.biz_aply_url),
    content: raw.pbanc_ctnt,
    applyTargetDetail: raw.aply_trgt_ctnt,
    excludeTarget: raw.aply_excl_trgt_ctnt,
    preferential: raw.prfn_matr,
    contact: raw.prch_cnpl_no,
  };
}

export type GrantsResult = {
  grants: Grant[];
  totalCount: number;     // API totalCount (전체 누적 공고 수, 모집중 외 포함)
  pagesFetched: number;
  fetchedAt: Date;
};

export async function fetchAllActiveGrants(): Promise<GrantsResult> {
  const key = getKey();
  const today = todayYyyymmdd();
  const collected: KStartupRawItem[] = [];
  let totalCount = 0;
  let emptyStreak = 0;
  let pagesFetched = 0;

  for (let page = 1; page <= MAX_PAGES; page++) {
    const resp = await fetchPage(page, key);
    pagesFetched = page;
    totalCount = resp.totalCount;

    const active = resp.data.filter(
      (it) =>
        it.rcrt_prgs_yn === 'Y' &&
        it.pbanc_rcpt_end_dt !== null &&
        it.pbanc_rcpt_end_dt >= today
    );

    collected.push(...active);

    if (active.length === 0) {
      emptyStreak++;
      if (emptyStreak >= STOP_AFTER_EMPTY) break;
    } else {
      emptyStreak = 0;
    }

    // 마지막 페이지에 도달했으면 중단
    if (resp.data.length < PER_PAGE) break;

    if (page < MAX_PAGES) {
      await new Promise((r) => setTimeout(r, DELAY_MS));
    }
  }

  if (pagesFetched === MAX_PAGES) {
    console.warn(
      `[kstartup-api] MAX_PAGES(${MAX_PAGES})에 도달. 일부 공고가 누락될 수 있음.`
    );
  }

  // pbanc_sn 기준 중복 제거 (방어적)
  const dedup = new Map<number, KStartupRawItem>();
  for (const it of collected) dedup.set(it.pbanc_sn, it);

  const grants = Array.from(dedup.values())
    .map(transform)
    .sort((a, b) => {
      // 마감일 가까운 순 (null은 뒤로)
      if (a.endDate && b.endDate) return a.endDate.getTime() - b.endDate.getTime();
      if (a.endDate) return -1;
      if (b.endDate) return 1;
      return 0;
    });

  return {
    grants,
    totalCount,
    pagesFetched,
    fetchedAt: new Date(),
  };
}
