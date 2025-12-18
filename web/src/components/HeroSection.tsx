export function HeroSection() {
  return (
    <section className="py-16 px-6 max-w-7xl mx-auto w-full">
      <div className="max-w-3xl">
        <h1 className="font-heading text-4xl md:text-5xl font-normal leading-tight mb-4 text-[var(--text-primary)]">
          Extract insights from{' '}
          <span className="bg-gradient-to-br from-[var(--accent-light)] to-[var(--accent)] bg-clip-text text-transparent">
            any video
          </span>
        </h1>
        <p className="font-heading text-lg md:text-xl italic text-[var(--text-secondary)] leading-relaxed">
          Transform YouTube videos into searchable transcripts and AI-powered summaries
        </p>
      </div>
    </section>
  );
}

