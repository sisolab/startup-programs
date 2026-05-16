"""K-Startup 모집중 공고를 받아 detail 페이지까지 fetch해서 grants.md + grants.json 생성.

환경변수:
  KSTARTUP_API_KEY   (필수) 공공데이터포털 인증키
  SAMPLE_LIMIT       (옵션) 처음 N건만 detail fetch — 로컬 테스트용
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

API_URL = (
    "https://apis.data.go.kr/B552735/kisedKstartupService01/"
    "getAnnouncementInformation01"
)
DETAIL_BASE = "https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do"

PER_PAGE = 1000
MAX_API_PAGES = 10
STOP_AFTER_EMPTY = 2
API_DELAY = 0.1
DETAIL_DELAY = 0.5
DETAIL_TIMEOUT = 20
FAILURE_ABORT_THRESHOLD = 0.5  # 실패율 50% 초과 시 abort

KST = timezone(timedelta(hours=9))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    "Referer": DETAIL_BASE,
}

# 페이지 검증용 키워드 — 페이지가 정상 detail인지 확인하는 용도
VERIFY_KEYWORDS = {
    "신청방법": ["신청방법"],
    "신청대상": ["신청대상", "신청 대상"],
    "제출서류": ["제출서류"],
    "선정절차": ["선정절차", "선정 절차", "평가방법"],
    "지원내용": ["지원내용", "지원 내용", "교육안내", "사업내용"],
    "문의처": ["문의처", "문의"],
}

# 본문 종료 추정용 푸터/공통 안내 마커 (이 중 가장 앞에 나오는 것이 본문 종료)
FOOTER_MARKERS = (
    "본 저작물은",
    "공공누리",
    "첨부파일 일괄 다운로드",
    "K-Startup에 공고되는 정보는",
    "사업신청 바로가기",
    "개인정보처리방침",
    "이용약관",
    "뉴스레터",
    "©",
    "K-Startup회원",
    "ALL RIGHTS RESERVED",
    "주소 : 우)",
    "창닫기",
    "이메일 아이디",
    "이메일 도메인",
    "※(유의)",
    "(유의)해당 공고는",
)

# 첨부파일 파일명 패턴 (공백 포함 허용, 줄바꿈/탭/파일시스템 금지문자만 제외)
ATTACHMENT_NAME_RE = re.compile(
    r"([^\n\r\t/\\<>|:*?\"]+?\."
    r"(?:hwpx?|pdf|docx?|xlsx?|pptx?|zip|jpe?g|png|gif|tiff?|bmp|txt|csv|tsv))",
    re.IGNORECASE,
)
ATTACHMENT_NOISE_RE = re.compile(r"(?:바로보기|다운로드|다운|preview|view|download)", re.IGNORECASE)


# ─── 환경변수 ───
def load_env_local() -> None:
    """로컬 개발 시 .env.local 파싱 (dotenv 없이)."""
    env_path = Path(".env.local")
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


def get_api_key() -> str:
    key = os.environ.get("KSTARTUP_API_KEY")
    if not key:
        raise SystemExit("KSTARTUP_API_KEY 환경변수가 설정되지 않았습니다.")
    return key


# ─── K-Startup API ───
def fetch_api_page(key: str, page: int) -> dict:
    params = {
        "serviceKey": key,
        "page": page,
        "perPage": PER_PAGE,
        "returnType": "json",
    }
    url = f"{API_URL}?{urlencode(params)}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


def today_yyyymmdd() -> str:
    return datetime.now(KST).strftime("%Y%m%d")


def fetch_all_active() -> list[dict]:
    """전체 모집중 공고 수집. 마감일 < 오늘은 제외. pbanc_sn dedup, 마감일 가까운 순."""
    key = get_api_key()
    today = today_yyyymmdd()
    collected: list[dict] = []
    empty_streak = 0

    for page in range(1, MAX_API_PAGES + 1):
        data = fetch_api_page(key, page)
        items = data.get("data", []) or []
        active = [
            it
            for it in items
            if it.get("rcrt_prgs_yn") == "Y"
            and it.get("pbanc_rcpt_end_dt")
            and str(it["pbanc_rcpt_end_dt"]) >= today
        ]
        print(
            f"[api] page {page}: {len(items)}건 중 모집중·미마감 {len(active)}건",
            flush=True,
        )
        collected.extend(active)

        if not active:
            empty_streak += 1
            if empty_streak >= STOP_AFTER_EMPTY:
                break
        else:
            empty_streak = 0

        if len(items) < PER_PAGE:
            break
        time.sleep(API_DELAY)
    else:
        print(
            f"[api] WARNING: MAX_API_PAGES({MAX_API_PAGES}) 도달. 일부 공고 누락 가능.",
            file=sys.stderr,
        )

    # pbanc_sn 기준 dedup
    by_sn: dict = {}
    for it in collected:
        by_sn[it["pbanc_sn"]] = it
    items = list(by_sn.values())
    items.sort(key=lambda x: str(x.get("pbanc_rcpt_end_dt") or "99999999"))
    return items


# ─── Detail fetch ───
def make_detail_url(pbanc_sn) -> str:
    params = {"schM": "view", "pbancSn": str(pbanc_sn)}
    return f"{DETAIL_BASE}?{urlencode(params)}"


def extract_raw_body(soup: BeautifulSoup) -> str:
    """페이지의 본문 텍스트를 그대로 추출.

    헤더(전역 메뉴 + 공유 버튼들)와 푸터(공공누리/개인정보처리방침 등)만 잘라내고
    본문은 그대로 둔다. 섹션 분리/정규화는 하지 않음 — AI가 자체 분석.

    K-Startup 페이지의 공유 버튼 영역은 "닫기"라는 토큰으로 끝남.
    "닫기" 이후 첫 줄바꿈부터 본문 시작으로 본다.
    """
    for tag in soup.find_all(
        ["script", "style", "noscript", "nav", "header", "footer"]
    ):
        tag.decompose()

    text = soup.get_text("\n", strip=True)

    # 본문 시작: "닫기"(공유 영역 끝 마커) 이후 — 없으면 처음부터
    cut_close = text.find("닫기")
    start_idx = cut_close + len("닫기") if cut_close >= 0 else 0

    # 본문 종료: 푸터 마커 중 가장 앞 (시작 + 50자 이후에서 탐색해 오탐 방지)
    end_idx = len(text)
    for marker in FOOTER_MARKERS:
        i = text.find(marker, start_idx + 50)
        if i >= 0 and i < end_idx:
            end_idx = i

    body = text[start_idx:end_idx]
    body = re.sub(r"[ \t]+", " ", body)
    body = re.sub(r" *\n *", "\n", body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip()


def extract_attachments(soup: BeautifulSoup) -> list[dict]:
    """첨부파일 a 태그에서 URL + 파일명 추출. 같은 URL은 dedup."""
    seen: set[str] = set()
    attachments: list[dict] = []
    for a in soup.find_all("a", href=re.compile(r"/afile/fileDownload/")):
        href = a.get("href") or ""
        full = (
            "https://www.k-startup.go.kr" + href if href.startswith("/") else href
        )
        if full in seen:
            continue
        seen.add(full)

        # 파일명 탐색: a 태그 텍스트가 "다운로드/바로보기"라 빈약하므로
        # 가장 가까운 li/td 부모에서 확장자 패턴을 가진 토큰 추출
        name: str | None = None
        for parent in a.parents:
            if parent.name in ("li", "td", "tr"):
                ptext = parent.get_text(" ", strip=True)
                # "바로보기/다운로드" 노이즈 제거
                ptext = ATTACHMENT_NOISE_RE.sub(" ", ptext)
                ptext = re.sub(r"\s+", " ", ptext).strip()
                m = ATTACHMENT_NAME_RE.search(ptext)
                if m:
                    name = m.group(1).strip(" .·-")
                    break
            if parent.name in ("body", "html"):
                break
        if not name:
            name = a.get_text(strip=True) or "첨부파일"

        attachments.append({"name": name, "url": full})
    return attachments


def fetch_detail(session: requests.Session, pbanc_sn) -> dict:
    url = make_detail_url(pbanc_sn)
    try:
        resp = session.get(
            url, headers=HEADERS, timeout=DETAIL_TIMEOUT, allow_redirects=True
        )
    except requests.RequestException as e:
        return {"status": "error", "error": str(e), "url": url}

    html = resp.text
    soup = BeautifulSoup(html, "html.parser")
    text = re.sub(r"\s+", " ", soup.get_text(" ")).strip()

    sections_present = {
        name: any(kw in text for kw in kws) for name, kws in VERIFY_KEYWORDS.items()
    }
    section_count = sum(sections_present.values())
    is_list_page = "go_view(" in html and section_count < 3

    attachments = extract_attachments(soup)

    if section_count < 3 or is_list_page:
        return {
            "status": "failed",
            "error": "missing_sections_or_list_page",
            "http_status": resp.status_code,
            "url": url,
            "sections_found": sections_present,
            "section_count": section_count,
        }

    return {
        "status": "success",
        "http_status": resp.status_code,
        "url": url,
        "sections_found": sections_present,
        "section_count": section_count,
        "raw_body": extract_raw_body(soup),
        "attachments": attachments,
        "text_length": len(text),
    }


# ─── 변환·포맷 유틸 ───
def split_csv(s) -> list[str]:
    if not s:
        return []
    return [x.strip() for x in str(s).split(",") if x.strip()]


def parse_date(s) -> date | None:
    if not s:
        return None
    m = re.match(r"^(\d{4})(\d{2})(\d{2})", str(s).strip())
    if not m:
        return None
    try:
        return date(int(m[1]), int(m[2]), int(m[3]))
    except ValueError:
        return None


def fmt_date(d: date | None) -> str:
    return d.strftime("%Y-%m-%d") if d else ""


def dday(end: date | None) -> int | None:
    if not end:
        return None
    today = datetime.now(KST).date()
    return (end - today).days


def fmt_dday(n: int | None) -> str:
    if n is None:
        return ""
    if n < 0:
        return "마감"
    if n == 0:
        return "D-day"
    return f"D-{n}"


def normalize_text(s) -> str:
    if not s:
        return ""
    t = str(s).replace("\r\n", "\n").replace("\r", "\n")
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def truncate(s: str, n: int) -> str:
    if len(s) <= n:
        return s
    return s[:n].rstrip() + "…"


def safe_title(s: str) -> str:
    return re.sub(r"[\[\]]", "", s).strip()


# ─── 출력 빌더 ───
def build_item(api_item: dict, detail: dict) -> dict:
    start = parse_date(api_item.get("pbanc_rcpt_bgng_dt"))
    end = parse_date(api_item.get("pbanc_rcpt_end_dt"))
    return {
        "pbanc_sn": api_item.get("pbanc_sn"),
        "title": api_item.get("biz_pbanc_nm") or "(제목 없음)",
        "organization": api_item.get("pbanc_ntrp_nm")
        or api_item.get("sprv_inst")
        or "",
        "supervising_institution": api_item.get("sprv_inst"),
        "category": api_item.get("supt_biz_clsfc"),
        "region": api_item.get("supt_regin"),
        "application_period": {
            "start": fmt_date(start),
            "end": fmt_date(end),
            "d_day": fmt_dday(dday(end)),
        },
        "target": split_csv(api_item.get("aply_trgt")),
        "startup_period": split_csv(api_item.get("biz_enyy")),
        "age": split_csv(api_item.get("biz_trgt_age")),
        "contact": api_item.get("prch_cnpl_no"),
        "summary": normalize_text(api_item.get("pbanc_ctnt")),
        "application_target_detail": normalize_text(api_item.get("aply_trgt_ctnt")),
        "exclusion_target": normalize_text(api_item.get("aply_excl_trgt_ctnt")),
        "preferential": normalize_text(api_item.get("prfn_matr")),
        "detail_url": detail.get("url") or make_detail_url(api_item.get("pbanc_sn")),
        "detail_fetch_status": detail.get("status"),
        "detail_fetch_error": detail.get("error"),
        "detail_raw": detail.get("raw_body") or "",
        "attachments": detail.get("attachments") or [],
    }


def build_markdown(
    items: list[dict], fetched_at: datetime, stats: dict
) -> str:
    fetched_at_kst = fetched_at.astimezone(KST)
    out: list[str] = []

    out += [
        "---",
        "title: K-Startup 모집중 공고",
        f"total: {len(items)}",
        f"fetched_at: {fetched_at.isoformat()}",
        f'fetched_at_kst: "{fetched_at_kst.strftime("%Y-%m-%d %H:%M KST")}"',
        f"detail_fetch_success: {stats['success']}",
        f"detail_fetch_failed: {stats['failed']}",
        "source: https://www.data.go.kr/data/15125364/openapi.do",
        "refresh: 매일 KST 02:00",
        "---",
        "",
        f"# K-Startup 모집중 공고 ({len(items)}건)",
        "",
        "> 창업진흥원 K-Startup 공공데이터 API + 상세 페이지 파싱 결과. "
        "마감일 가까운 순. 매일 KST 02:00 갱신.",
        "",
        f"상세 페이지 파싱 성공 **{stats['success']}건** / 실패 **{stats['failed']}건**. "
        "구조화 데이터는 [grants.json](./grants.json) 참고.",
        "",
        "**AI 사용 가이드:** 이 문서를 컨텍스트에 넣고 본인 프로필"
        "(예비/창업기업, 업력, 연령, 지역, 분야)에 맞는 공고를 추천하도록 요청하세요.",
        "",
        "---",
        "",
    ]

    for i, g in enumerate(items, 1):
        title = safe_title(g["title"])
        url = g["detail_url"]
        out.append(f"## {i}. [{title}]({url})" if url else f"## {i}. {title}")
        out.append("")

        if g["organization"]:
            out.append(f"- **기관**: {g['organization']}")
        meta = []
        if g["supervising_institution"]:
            meta.append(f"주관 {g['supervising_institution']}")
        if g["category"]:
            meta.append(f"분야 {g['category']}")
        if g["region"]:
            meta.append(f"지역 {g['region']}")
        if meta:
            out.append(f"- {' · '.join(meta)}")

        ap = g["application_period"]
        if ap["end"]:
            range_str = (ap["start"] + " ~ " if ap["start"] else "~ ") + ap["end"]
            out.append(f"- **접수**: {range_str} ({ap['d_day']})")

        if g["target"]:
            out.append(f"- **신청 대상**: {', '.join(g['target'])}")
        if g["startup_period"]:
            out.append(f"- **창업 기간**: {', '.join(g['startup_period'])}")
        if g["age"]:
            out.append(f"- **대상 연령**: {', '.join(g['age'])}")
        if g["contact"]:
            out.append(f"- **문의**: {g['contact']}")

        if g["summary"]:
            out.append("")
            out.append(truncate(g["summary"], 1000))

        if g["application_target_detail"]:
            out.append("")
            out.append(
                f"**신청 대상 상세**: {truncate(g['application_target_detail'], 500)}"
            )
        if g["preferential"]:
            out.append("")
            out.append(f"**우대 사항**: {truncate(g['preferential'], 400)}")
        if g["exclusion_target"]:
            out.append("")
            out.append(f"**제외 대상**: {truncate(g['exclusion_target'], 300)}")

        # Detail section: 원문 본문 그대로 (헤더·푸터만 제거)
        out.append("")
        out.append("### 상세 페이지 본문 (K-Startup 원문)")
        out.append("")
        if g["detail_fetch_status"] == "success" and g["detail_raw"]:
            out.append(g["detail_raw"])
        else:
            err = g.get("detail_fetch_error") or "알 수 없는 오류"
            out.append(
                f"⚠️ 원문 fetch 실패 ({err}). "
                f"[공식 페이지]({g['detail_url']})에서 직접 확인하세요."
            )

        if g["attachments"]:
            out.append("")
            out.append("**첨부파일**:")
            for att in g["attachments"]:
                out.append(f"- [{att['name']}]({att['url']})")
        out.append("")

    return "\n".join(out)


# ─── 메인 ───
def main() -> None:
    load_env_local()
    fetched_at = datetime.now(timezone.utc)
    fetched_kst = fetched_at.astimezone(KST).strftime("%Y-%m-%d %H:%M:%S KST")
    print(f"[main] 시작 ({fetched_kst})", flush=True)

    api_items = fetch_all_active()
    print(f"[main] API 결과: 모집중 {len(api_items)}건", flush=True)

    limit = os.environ.get("SAMPLE_LIMIT")
    if limit:
        api_items = api_items[: int(limit)]
        print(
            f"[main] SAMPLE_LIMIT={limit} 적용 → {len(api_items)}건만 detail fetch",
            flush=True,
        )

    session = requests.Session()
    try:
        session.get(DETAIL_BASE, headers=HEADERS, timeout=15)  # 쿠키 확보
    except requests.RequestException as e:
        print(f"[main] 세션 초기화 실패 (계속 진행): {e}", file=sys.stderr)

    stats = {"success": 0, "failed": 0, "error": 0}
    items: list[dict] = []
    total = len(api_items)

    for idx, api_item in enumerate(api_items, 1):
        sn = api_item.get("pbanc_sn")
        if idx == 1 or idx % 25 == 0 or idx == total:
            print(f"[detail] {idx}/{total} (pbanc_sn={sn})", flush=True)
        detail = fetch_detail(session, sn)
        st = detail.get("status", "error")
        stats[st] = stats.get(st, 0) + 1
        items.append(build_item(api_item, detail))
        time.sleep(DETAIL_DELAY)

    failed_total = stats["failed"] + stats["error"]
    print(
        f"[detail] 완료: success={stats['success']} "
        f"failed={stats['failed']} error={stats['error']}",
        flush=True,
    )

    if total > 0 and failed_total / total > FAILURE_ABORT_THRESHOLD:
        print(
            f"[main] FATAL: 실패율 {failed_total / total:.0%} > "
            f"{FAILURE_ABORT_THRESHOLD:.0%}. 기존 결과물 유지 위해 abort.",
            file=sys.stderr,
        )
        sys.exit(2)

    md_stats = {"success": stats["success"], "failed": failed_total}

    json_payload = {
        "fetched_at": fetched_at.isoformat(),
        "fetched_at_kst": fetched_at.astimezone(KST).strftime(
            "%Y-%m-%d %H:%M KST"
        ),
        "source": "K-Startup 공공데이터 API + detail page",
        "total": len(items),
        "detail_fetch_success_count": stats["success"],
        "detail_fetch_failed_count": failed_total,
        "items": items,
    }
    Path("grants.json").write_text(
        json.dumps(json_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[main] grants.json 작성 완료", flush=True)

    md = build_markdown(items, fetched_at, md_stats)
    Path("grants.md").write_text(md, encoding="utf-8")
    print(f"[main] grants.md 작성 완료 ({len(md):,} chars)", flush=True)


if __name__ == "__main__":
    main()
