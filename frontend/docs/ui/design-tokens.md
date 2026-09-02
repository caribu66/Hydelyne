# Hydenlyne UI design tokens

These values are the default visual language for the talent workspace. A new value should be added here before being introduced in a component.

## Color roles

| Role | Dark | Light | Usage |
| --- | --- | --- | --- |
| Page background | `zinc-950` | white | Application canvas |
| Surface | `zinc-900` | `slate-50` | Cards, controls, panels |
| Elevated surface | `zinc-850` | `slate-100` | Hover and raised content |
| Border | `zinc-800` | `slate-200` | Default separation |
| Primary text | `zinc-100` | `slate-950` | Headings and important values |
| Secondary text | `zinc-400` | `slate-600` | Supporting information |
| Muted text | `zinc-500` | `slate-500` | Metadata only |
| Primary action | `blue-600` | `blue-600` | Main calls to action |
| Success | `emerald-500` | `emerald-600` | Availability and completed actions |
| Warning | `amber-500` | `amber-600` | Demo or attention states |
| Error | `rose-500` | `rose-600` | Failures and destructive actions |

## Type scale

- Page title: 32–40px
- Section title: 18–24px
- Card title: 15–18px
- Body: 14–16px
- Metadata: 12–13px
- Minimum text: 11px, metadata only

## Badge roles

Badges use theme-aware role tokens rather than fixed blue, green, or zinc text/background pairs:

- Neutral: general metadata and certifications
- Accent: discipline, verification, and selected states
- Positive: availability and completed actions

Search matches use a solid, theme-aware highlight background with high-contrast text. Avoid translucent highlight colors for essential text.

## Layout scale

- Page max width: 1152px
- Spacing: 4, 8, 12, 16, 24, 32, 48px
- Card radius: 16px
- Modal radius: 16–24px
- Standard control height: 40–44px
- Minimum touch target: 44×44px

## Motion

- Use short, purposeful transitions for state changes.
- Avoid animation for essential information.
- Always preserve the global reduced-motion override.
