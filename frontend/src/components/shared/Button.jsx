export function Button({ 
  children, 
  onClick, 
  variant = 'primary', 
  size = 'md', 
  disabled = false, 
  style = {},
  ...props
}) {
  const baseStyle = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    borderRadius: 8,
    fontWeight: 600,
    cursor: disabled ? 'not-allowed' : 'pointer',
    transition: 'all 0.2s',
    border: variant === 'secondary' ? '1px solid var(--border)' : 'none',
    opacity: disabled ? 0.5 : 1,
    outline: 'none',
  }

  const variants = {
    primary: { background: 'var(--accent)', color: 'var(--bg-primary)' },
    secondary: { background: 'var(--bg-tertiary)', color: 'var(--text-primary)' },
    danger: { background: 'var(--danger)', color: 'white' },
    ghost: { background: 'transparent', color: 'var(--text-secondary)' },
  }

  const sizes = {
    sm: { padding: '4px 10px', fontSize: 11 },
    md: { padding: '8px 16px', fontSize: 13 },
    lg: { padding: '12px 24px', fontSize: 15 },
  }

  const v = variants[variant] || variants.primary
  const s = sizes[size] || sizes.md

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{ ...baseStyle, ...v, ...s, ...style }}
      {...props}
    >
      {children}
    </button>
  )
}
export default Button
