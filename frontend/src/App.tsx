import './App.css'
import { GoogleLoginCard } from './components/GoogleLoginCard'

function App() {
  return (
    <div className="page">
      <header className="page__header">
        <span className="page__eyebrow">Google Drive 연결</span>
        <h1 className="page__title">먼저 구글 계정으로 로그인하세요</h1>
        <p className="page__subtitle">
          프로젝트에서 Google Drive 권한을 사용하려면 Google 계정을 통해 인증을 완료해야
          합니다. 아래 버튼을 눌러 안전하게 로그인하세요.
        </p>
      </header>

      <GoogleLoginCard />
    </div>
  )
}

export default App
