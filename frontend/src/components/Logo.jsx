export default function Logo({ size = 24 }) {
  return (
    <svg
      className="logo-mark"
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      aria-hidden="true"
    >
      <rect x="0"    y="20" width="7" height="12" fill="currentColor" />
      <rect x="12.5" y="11" width="7" height="21" fill="currentColor" />
      <rect x="25"   y="2"  width="7" height="30" fill="currentColor" />
      <polyline
        points="3.5,20 16,11 28.5,2"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}
