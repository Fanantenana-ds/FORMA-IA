import React, { useCallback, useState } from 'react';
import { LandingNavbar } from './LandingNavbar';
import { HeroSection } from './HeroSection';
import { FeaturesSection } from './FeaturesSection';
import { ModulesSection } from './ModulesSection';
import { MetricsSection } from './MetricsSection';
import { HowItWorksSection } from './HowItWorksSection';
import { TestimonialsSection } from './TestimonialsSection';
import { FinalCtaSection } from './FinalCtaSection';
import { LandingFooter } from './LandingFooter';
import { DemoRequestModal } from './DemoRequestModal';

interface LandingPageProps {
  /** Ouvre l'écran de connexion / inscription. */
  onLogin: () => void;
}

export const LandingPage: React.FC<LandingPageProps> = ({ onLogin }) => {
  const [demoOpen, setDemoOpen] = useState(false);
  const openDemo = useCallback(() => setDemoOpen(true), []);
  const closeDemo = useCallback(() => setDemoOpen(false), []);

  return (
    <div className="forma-landing antialiased selection:bg-brand-gold selection:text-brand-darkNavy">
      <LandingNavbar onLogin={onLogin} onOpenDemo={openDemo} />
      <main>
        <HeroSection />
        <FeaturesSection />
        <ModulesSection />
        <MetricsSection />
        <HowItWorksSection />
        <TestimonialsSection />
        <FinalCtaSection onOpenDemo={openDemo} onLogin={onLogin} />
      </main>
      <LandingFooter />
      <DemoRequestModal open={demoOpen} onClose={closeDemo} />
    </div>
  );
};

export default LandingPage;
