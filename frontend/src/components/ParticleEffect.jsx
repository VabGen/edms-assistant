import { useEffect, useRef } from 'react';

export default function ParticleEffect({ isActive, onComplete }) {
  const containerRef = useRef(null);

  useEffect(() => {
    if (!isActive || !containerRef.current) return;

    document.body.style.overflow = 'hidden';

    const container = containerRef.current;
    container.innerHTML = '';

    const particleCount = 1200;

    const maxDuration = 0.8;
    const maxDelay = 0.1;

    for (let i = 0; i < particleCount; i++) {
      const dx = (Math.random() - 0.5) * 2000;
      const dy = (Math.random() - 0.5) * 2000;
      const delay = Math.random() * maxDelay;
      const duration = 0.4 + Math.random() * 0.4; // 0.4–0.8 сек

      const particle = document.createElement('div');

      const colors = [
        '#ffffff',
        '#e0f7fa',
        '#81d4fa',
        '#4fc3f7',
        '#29b6f6',
        '#03a9f4',
        '#0288d1',
        '#01579b',
        '#0d47a1',
      ];
      const randomColor = colors[Math.floor(Math.random() * colors.length)];
      const size = 0.5 + Math.random() * 2.5;

      particle.className = 'absolute rounded-full pointer-events-none';
      particle.style.width = `${size}px`;
      particle.style.height = `${size}px`;
      particle.style.setProperty('--dx', `${dx}px`);
      particle.style.setProperty('--dy', `${dy}px`);
      particle.style.backgroundColor = randomColor;
      particle.style.boxShadow = `0 0 ${size * 2}px ${randomColor}40`;
      particle.style.animation = `particleExplode ${duration}s cubic-bezier(0.16, 1, 0.3, 1) ${delay}s forwards`;

      container.appendChild(particle);
    }

    const timer = setTimeout(() => {
      onComplete();
      document.body.style.overflow = '';
    }, 1300);

    return () => {
      clearTimeout(timer);
      document.body.style.overflow = '';
    };
  }, [isActive, onComplete]);

  if (!isActive) return null;

  return (
    <div
      ref={containerRef}
      className="absolute inset-0 pointer-events-none z-10"
      aria-hidden="true"
    />
  );
}