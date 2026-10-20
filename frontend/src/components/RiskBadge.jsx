import { ShieldAlert, ShieldCheck, ShieldQuestion } from 'lucide-react'

const CONFIG = {
  Low: { cls: 'risk-badge-low', Icon: ShieldCheck, label: 'Low Risk' },
  Medium: { cls: 'risk-badge-medium', Icon: ShieldQuestion, label: 'Medium Risk' },
  High: { cls: 'risk-badge-high', Icon: ShieldAlert, label: 'High Risk' },
}

export default function RiskBadge({ category, size = 'md' }) {
  const cfg = CONFIG[category] || CONFIG.Medium
  const { cls, Icon, label } = cfg
  const sizeCls = size === 'lg' ? 'text-sm px-4 py-2' : 'text-xs px-3 py-1.5'

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full font-semibold ${cls} ${sizeCls}`}>
      <Icon size={size === 'lg' ? 16 : 14} />
      {label}
    </span>
  )
}
