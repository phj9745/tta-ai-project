# TestMate Frontend

TestMate 프론트엔드는 **React 19 + TypeScript 5.8 + Vite 7** 기반의 단일 페이지 애플리케이션입니다.

## 기술 스택

| 항목 | 기술 |
| --- | --- |
| UI 라이브러리 | React 19 |
| 언어 | TypeScript 5.8 |
| 빌드 도구 | Vite 7 |
| 스타일링 | Vanilla CSS |
| 아이콘 | Lucide React |
| 테스트 | Vitest + Testing Library |
| Lint | ESLint + typescript-eslint |

## 디렉터리 구조

```
src/
├── app/           # 공용 레이아웃, 훅, 라우팅 로직
├── assets/        # 정적 리소스
├── components/    # 도메인별 UI 컴포넌트
├── pages/         # 페이지 엔트리
├── test/          # 테스트 유틸리티
├── types/         # 타입 정의
├── App.tsx        # 루트 컴포넌트 (인증·라우팅)
├── auth.ts        # OAuth 토큰 관리 유틸
├── config.ts      # API 엔드포인트 설정
├── constants.ts   # 공용 상수
├── drive.ts       # Drive 관련 유틸
├── navigation.ts  # 네비게이션 유틸
└── main.tsx       # 앱 진입점
```

## 스크립트

```bash
# 개발 서버 실행
npm run dev

# 프로덕션 빌드
npm run build

# 린트 검사
npm run lint

# 테스트 실행
npm run test

# 빌드 미리보기
npm run preview
```

## 환경 변수

| 변수 | 설명 |
| --- | --- |
| `VITE_API_BASE_URL` | 백엔드 API 엔드포인트 |

`.env.local` 파일에 설정하거나 Doppler를 통해 주입할 수 있습니다.

## 추가 정보

- 프로젝트 전체 README: [README.md](../README.md)
- 협업 가이드: [COLLABORATION_GUIDE.md](../docs/COLLABORATION_GUIDE.md)
- Doppler 사용 가이드: [DOPPLER_GUIDE.md](../docs/DOPPLER_GUIDE.md)
