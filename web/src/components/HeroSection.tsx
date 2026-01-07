export function HeroSection() {
  return (
    <section className="py-[clamp(2.5rem,8vw,6rem)] px-6 max-w-7xl mx-auto w-full">
      <div className="max-w-3xl mx-auto text-center">
        <h1 className="font-display text-[clamp(2rem,5vw,3.5rem)] font-normal leading-[1.15] mb-4 text-[var(--text-primary)]">
          Extract insights from{' '}
          <span className="bg-gradient-to-br from-[var(--accent-light)] to-[var(--accent)] bg-clip-text text-transparent">
            any video
          </span>
        </h1>
        <p className="font-display text-[clamp(1rem,2.5vw,1.25rem)] italic text-[var(--text-secondary)] leading-relaxed">
          Transform YouTube videos into searchable transcripts and AI-powered summaries
        </p>
      </div>
    </section>
  );
}

