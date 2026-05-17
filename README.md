# startup-programs

K-Startup(창업진흥원) 모집중 창업지원 공고를 매일 KST 02:00에 자동 수집해 `grants.md` / `grants.json`으로 발행합니다. 각 공고에는 API 메타데이터와 K-Startup 상세 페이지 본문, 첨부파일 링크가 포함됩니다.

## 사용법 (AI 큐레이션)

ChatGPT / Claude 등 AI 챗봇에 아래 한 줄을 그대로 던지면 됩니다:

```
다음 프롬프트의 지시를 따라 큐레이션해줘:
https://raw.githubusercontent.com/sisolab/startup-programs/main/kstartup-curation-prompt.md
```

AI가 프롬프트를 fetch한 뒤 사용자 프로필을 물어보고, `grants.json`을 직접 읽어 적합한 공고를 카테고리별로 추천합니다.
