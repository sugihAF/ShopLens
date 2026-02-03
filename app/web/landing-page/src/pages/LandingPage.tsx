import {
  Navigation,
  Background,
  Hero,
  TrustedBy,
  Features,
  HowItWorks,
  DemoChat,
  CTA,
  Footer,
} from '@/components/sections'

export function LandingPage() {
  return (
    <>
      <Background />
      <Navigation />
      <main>
        <Hero />
        <DemoChat />
        <TrustedBy />
        <Features />
        <HowItWorks />
        <CTA />
      </main>
      <Footer />
    </>
  )
}
