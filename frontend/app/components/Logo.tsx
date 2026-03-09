export default function Logo({ className = "h-8 w-8" }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 40 40"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
    >
      <defs>
        <linearGradient id="logoGrad" x1="0%" y1="100%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#0d9488" />
          <stop offset="100%" stopColor="#6366f1" />
        </linearGradient>
      </defs>
      {/* Circle */}
      <circle cx="20" cy="20" r="18" stroke="url(#logoGrad)" strokeWidth="2" fill="none" />
      {/* Letter "B" for Byte — stem + top and bottom bowls */}
      <path
        d="M14 10v20 M14 10c6 0 10 2.5 10 5s-4 5-10 5 M14 20c6 0 10 2.5 10 5s-4 5-10 5"
        stroke="url(#logoGrad)"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
      {/* Accent dot (byte) */}
      <circle cx="28" cy="28" r="2" fill="url(#logoGrad)" />
    </svg>
  );
}
