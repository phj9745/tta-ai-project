import { useEffect, useState } from 'react'

type AuthStatus = 'success' | 'error' | null

const DEFAULT_BACKEND_URL = 'http://localhost:8000'

const SCOPES = [
  'Google Drive 전체 읽기 및 쓰기 권한',
  '사용자가 만든 파일 관리 (생성/수정/삭제)',
]

export function GoogleLoginCard() {
  const [status, setStatus] = useState<AuthStatus>(null)
  const [message, setMessage] = useState<string>('')
  const [isRedirecting, setIsRedirecting] = useState(false)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const authStatus = params.get('auth')
    const statusMessage = params.get('message')

    if (authStatus === 'success') {
      setStatus('success')
      setMessage('Google Drive 권한이 성공적으로 연결되었습니다.')
    } else if (authStatus === 'error') {
      setStatus('error')
      setMessage(statusMessage ?? 'Google 인증이 취소되었습니다.')
    }

    if (authStatus) {
      window.history.replaceState({}, '', window.location.pathname)
    }
  }, [])

  const handleLogin = () => {
    const backendUrl = (import.meta.env.VITE_BACKEND_URL as string | undefined) ?? DEFAULT_BACKEND_URL
    const loginUrl = `${backendUrl.replace(/\/$/, '')}/auth/google/login`
    setIsRedirecting(true)
    window.location.href = loginUrl
  }

  return (
    <section className="google-card">
      <div className="google-card__content">
        <h2 className="google-card__title">Google 로그인</h2>
        <p className="google-card__description">
          Google 계정을 인증하면 프로젝트가 아래의 Drive 권한을 요청하여 파일을 읽고, 생성하고,
          수정하거나 삭제할 수 있습니다. 승인된 액세스/리프레시 토큰은 안전하게 백엔드에 저장됩니다.
        </p>

        <ul className="google-card__scopes">
          {SCOPES.map((scope) => (
            <li key={scope}>{scope}</li>
          ))}
        </ul>
      </div>

      <div className="google-card__button">
        <button
          type="button"
          className="google-card__signin"
          onClick={handleLogin}
          disabled={isRedirecting}
        >
          {isRedirecting ? 'Google으로 이동 중…' : 'Google 계정으로 로그인'}
        </button>
      </div>

      {status === null && !isRedirecting && (
        <p className="google-card__helper">로그인 버튼을 누르면 Google 인증 화면으로 이동합니다.</p>
      )}

      {status !== null && (
        <div
          className={`google-card__status${status === 'error' ? ' google-card__status--error' : ''}`}
          role="status"
        >
          <strong>{status === 'success' ? '인증 완료!' : '인증에 실패했습니다.'}</strong>
          <span>{message}</span>
        </div>
      )}
    </section>
  )
}
