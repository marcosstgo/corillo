export default function CorrilloLogo({ height = 36 }: { height?: number }) {
  return (
    <svg viewBox="0 0 304 88" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ height, width: 'auto' }}>
      <defs>
        <radialGradient id="lg" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#00bfff" stopOpacity="0.18" />
          <stop offset="100%" stopColor="#00bfff" stopOpacity="0" />
        </radialGradient>
      </defs>
      <text x="0" y="74" fontFamily="Bebas Neue, cursive" fontSize="82" fill="#e8f6ff">C</text>
      <circle cx="72" cy="42" r="36" fill="url(#lg)" />
      <circle cx="72" cy="42" r="34" stroke="#e8f6ff" strokeWidth="9" fill="none" />
      <circle cx="72" cy="42" r="20" stroke="#00bfff" strokeWidth="6" fill="none" />
      <circle cx="72" cy="42" r="8" fill="#00bfff" />
      <circle cx="72" cy="42" r="3.5" fill="#00ff9d" />
      <text x="114" y="74" fontFamily="Bebas Neue, cursive" fontSize="82" fill="#e8f6ff">RILLO</text>
    </svg>
  );
}
