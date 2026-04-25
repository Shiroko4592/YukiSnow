# Personal Wiki (Flask)

## 기능
- 문서 생성/조회/수정
- 리비전 저장 및 조회
- JSON 기반 데이터 임포트 (`POST /import`)

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
    {"title": "대문", "slug": "대문", "content": "환영합니다"},
    {"title": "치즈비", "content": "내용"}
  ]
}
```

> 주의: 본인 소유 또는 이전 권한이 있는 데이터만 임포트하세요.
