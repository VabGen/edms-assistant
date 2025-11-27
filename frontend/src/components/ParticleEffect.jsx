import { useEffect, useRef } from 'react';

export default function ParticleEffect({ isActive, onComplete }) {
  const containerRef = useRef(null);

  useEffect(() => {
    if (!isActive || !containerRef.current) return;

    document.body.style.overflow = 'hidden';

    const container = containerRef.current;
    container.innerHTML = '';

    for (let i = 0; i < 500; i++) {
      const dx = (Math.random() - 0.5) * 1500;
      const dy = (Math.random() - 0.5) * 1500;
      const delay = Math.random() * 0.3;
      const duration = 0.5 + Math.random() * 0.5;

      const particle = document.createElement('div');
      const colors = ['#6b7280', '#4b5563', '#374151', '#ffffff'];
      const randomColor = colors[Math.floor(Math.random() * colors.length)];

      particle.className = 'absolute w-1 h-1 rounded-full pointer-events-none';
      particle.style.setProperty('--dx', `${dx}px`);
      particle.style.setProperty('--dy', `${dy}px`);
      particle.style.backgroundColor = randomColor;
      particle.style.animation = `particleExplode ${duration}s cubic-bezier(0.16, 1, 0.3, 1) ${delay}s forwards`;

      container.appendChild(particle);
    }

    const timer = setTimeout(() => {
      onComplete();
      document.body.style.overflow = '';
    }, 1000);

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