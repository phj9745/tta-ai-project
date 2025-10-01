import { GoogleLoginCard } from '../components/GoogleLoginCard'
import { PageHeader } from '../components/layout/PageHeader'
import { PageLayout } from '../components/layout/PageLayout'

export function LoginPage() {
  return (
    <PageLayout>
      <PageHeader
        eyebrow="Google Drive 연결"
        title="먼저 구글 계정으로 로그인하세요"
        subtitle="프로젝트에서 Google Drive 권한을 사용하려면 Google 계정을 통해 인증을 완료해야 합니다. 아래 버튼을 눌러 안전하게 로그인하세요."
      />
      <GoogleLoginCard />
    </PageLayout>
  )
}
