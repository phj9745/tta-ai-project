import { useEffect, useRef, useState } from 'react'

interface GoogleCredentialResponse {
  credential: string
  select_by: string
}

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string
            callback: (response: GoogleCredentialResponse) => void
            ux_mode?: 'popup' | 'redirect'
            auto_select?: boolean
          }) => void
          renderButton: (
            parent: HTMLElement,
            options: Record<string, unknown>,
          ) => void
          prompt: () => void
        }
      }
    }
  }
}

const GOOGLE_SCRIPT_ID = 'google-identity-services'

export function GoogleLoginCard() {
  const buttonRef = useRef<HTMLDivElement | null>(null)
  const [credential, setCredential] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isReady, setIsReady] = useState(false)

  useEffect(() => {
    const buttonElement = buttonRef.current
    if (!buttonElement) return

    let isCancelled = false
    let scriptElement: HTMLScriptElement | null = document.getElementById(
      GOOGLE_SCRIPT_ID,
    ) as HTMLScriptElement | null

    const initializeGoogleButton = () => {
      if (isCancelled || !buttonRef.current) {
        return
      }

      const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID
      if (!clientId) {
        setError(
          'Google OAuth 클라이언트 ID가 설정되어 있지 않습니다. .env 파일에 VITE_GOOGLE_CLIENT_ID를 추가하세요.',
        )
        return
      }

      if (!window.google?.accounts?.id) {
        setError('Google Identity Services를 불러오지 못했습니다. 잠시 후 다시 시도하세요.')
        return
      }

      buttonRef.current.innerHTML = ''

      window.google.accounts.id.initialize({
        client_id: clientId,
        callback: (response: GoogleCredentialResponse) => {
          setCredential(response.credential)
          setError(null)
        },
      })

      window.google.accounts.id.renderButton(buttonRef.current, {
        type: 'standard',
        theme: 'filled_blue',
        text: 'signin_with',
        shape: 'pill',
        width: 320,
        locale: 'ko',
      })

      window.google.accounts.id.prompt()
      setIsReady(true)
    }

    const handleScriptError = () => {
      if (!isCancelled) {
        setError('Google 로그인 스크립트를 불러오는 데 실패했습니다.')
      }
    }

    if (scriptElement) {
      if (window.google?.accounts?.id) {
        initializeGoogleButton()
      } else {
        scriptElement.addEventListener('load', initializeGoogleButton)
        scriptElement.addEventListener('error', handleScriptError)
      }
    } else {
      scriptElement = document.createElement('script')
      scriptElement.id = GOOGLE_SCRIPT_ID
      scriptElement.src = 'https://accounts.google.com/gsi/client'
      scriptElement.async = true
      scriptElement.defer = true
      scriptElement.addEventListener('load', initializeGoogleButton)
      scriptElement.addEventListener('error', handleScriptError)
      document.head.appendChild(scriptElement)
    }

    return () => {
      isCancelled = true
      if (scriptElement) {
        scriptElement.removeEventListener('load', initializeGoogleButton)
        scriptElement.removeEventListener('error', handleScriptError)
      }
    }
  }, [])

  return (
    <section className="google-card">
      <div className="google-card__content">
        <h2 className="google-card__title">Google 로그인</h2>
        <p className="google-card__description">
          Google 계정으로 로그인하면 프로젝트가 Google Drive API 접근 권한을 요청할 수 있습니다.
          로그인 후 발급된 토큰은 안전하게 저장하세요.
        </p>
      </div>

      <div className="google-card__button" ref={buttonRef} aria-live="polite" />

      {!isReady && !error && (
        <p className="google-card__helper">Google 로그인 버튼을 불러오는 중입니다…</p>
      )}

      {credential && !error && (
        <div className="google-card__status" role="status">
          <strong>인증 완료!</strong>
          <span>발급된 토큰은 다음 단계에서 사용할 수 있습니다.</span>
        </div>
      )}

      {error && (
        <div className="google-card__status google-card__status--error" role="alert">
          <strong>문제가 발생했습니다.</strong>
          <span>{error}</span>
        </div>
      )}
    </section>
  )
}
