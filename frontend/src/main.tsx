import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { BackgroundTaskProvider } from './app/background/BackgroundTaskContext.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BackgroundTaskProvider>
      <App />
    </BackgroundTaskProvider>
  </StrictMode>,
)
