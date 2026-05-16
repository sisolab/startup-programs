// K-Startup API 응답의 단일 공고 원본 (snake_case)
// 실측: 명세서와 일부 필드명이 다름 (rcrt_prgs_yn 소문자, aply_excl_trgt_ctnt 등)
export type KStartupRawItem = {
  id: number;
  pbanc_sn: number;
  biz_pbanc_nm: string | null;
  intg_pbanc_yn: 'Y' | 'N' | null;
  intg_pbanc_biz_nm: string | null;
  pbanc_ctnt: string | null;
  supt_biz_clsfc: string | null;
  aply_trgt_ctnt: string | null;
  aply_trgt: string | null;
  biz_enyy: string | null;
  biz_trgt_age: string | null;
  supt_regin: string | null;
  pbanc_rcpt_bgng_dt: string | null; // YYYYMMDD
  pbanc_rcpt_end_dt: string | null;  // YYYYMMDD
  pbanc_ntrp_nm: string | null;
  sprv_inst: string | null;
  biz_prch_dprt_nm: string | null;
  biz_gdnc_url: string | null;
  biz_aply_url: string | null;
  prch_cnpl_no: string | null;
  detl_pg_url: string | null;
  aply_mthd_vst_rcpt_istc: string | null;
  aply_mthd_pssr_rcpt_istc: string | null;
  aply_mthd_fax_rcpt_istc: string | null;
  aply_mthd_eml_rcpt_istc: string | null;
  aply_mthd_onli_rcpt_istc: string | null;
  aply_mthd_etc_istc: string | null;
  aply_excl_trgt_ctnt: string | null;
  prfn_matr: string | null;
  rcrt_prgs_yn: 'Y' | 'N' | null;
};

export type KStartupApiResponse = {
  currentCount: number;
  matchCount: number;
  totalCount: number;
  page: number;
  perPage: number;
  data: KStartupRawItem[];
};

// 가공된 공고 (UI에서 직접 사용)
export type Grant = {
  pbancSn: number;
  title: string;
  organization: string;       // pbanc_ntrp_nm 우선, 없으면 sprv_inst
  sprvInst: string | null;    // 주관 기관 분류 (공공기관/민간/교육기관/지자체)
  category: string | null;    // supt_biz_clsfc
  region: string | null;
  applyTargets: string[];     // aply_trgt split
  bizYears: string[];         // biz_enyy split
  targetAges: string[];       // biz_trgt_age split
  startDate: Date | null;
  endDate: Date | null;
  detailUrl: string | null;
  guideUrl: string | null;
  applyUrl: string | null;
  content: string | null;
  applyTargetDetail: string | null;
  excludeTarget: string | null;
  preferential: string | null;
  contact: string | null;
};
