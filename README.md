<<<<<<< codex/clone-and-migrate-personal-wiki-ggo3ga
# Personal Wiki (Flask)

요청하신 외부 사이트를 그대로 복제하거나 권한 없는 DB를 이전하는 작업은 도와드릴 수 없습니다.
대신 **개인 위키를 직접 운영**할 수 있도록, 나무마크 기반 렌더링 + 데이터 임포트 엔드포인트를 제공하는 앱을 구성했습니다.

## 기능
- 문서 생성/조회/수정
- 리비전 저장 및 조회
- JSON 기반 데이터 임포트 (`POST /import`)
- 나무마크 스타일 렌더링 지원
  - 문단/제목 (`= 제목 =`)
  - 강조 (`'''굵게'''`, `''기울임''`, `~~취소선~~`, `__밑줄__`)
  - 링크 (`[[문서]]`, `[[문서|표시텍스트]]`, `[[https://example.com|외부링크]]`)
  - 목록 (`* 항목`, `1. 항목`)
  - 인용문 (`> 인용`)
  - 코드 블록 (`{{{` ... `}}}`)
  - 수식 (`[math(a^2+b^2=c^2)]`, KaTeX 렌더링)

## 실행
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

## 데이터 임포트 형식
`POST /import` 에 아래 형태 JSON 전송:

```json
{
  "pages": [
    {"title": "대문", "slug": "대문", "content": "= 환영합니다 =\n[[치즈비]]"},
    {"title": "치즈비", "content": "'''테스트''' [math(E=mc^2)]"}
  ]
}
```

> 주의: 본인 소유 또는 이전 권한이 있는 데이터만 임포트하세요.
=======

>>>>>>> main

