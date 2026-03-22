# Application Shell Specification

## Layout Pattern
**Sidebar Navigation** — Collapsible left sidebar with icon + label navigation, suitable for multi-section dashboard applications.

## Navigation Structure

### Primary Navigation (Sidebar)
| Icon | Label | Route | Description |
|------|-------|-------|-------------|
| Play | Video Player | `/player` | Watch videos with face overlays |
| Users | Contestants | `/contestants` | Browse contestant directory |
| BarChart3 | Analytics | `/analytics` | View screen time and stats |
| Upload | Ingestion | `/ingestion` | Submit and manage videos |
| Flag | Flagging | `/flagging` | Review and correct identifications |

### User Menu
- Profile avatar/initials
- Theme toggle (dark mode default, light mode option)
- Language selector (Traditional Chinese / English)
- Sign out

## Visual Specifications

### Sidebar
- **Width**: 240px expanded, 64px collapsed
- **Background**: `slate-900` (dark mode)
- **Border**: `slate-800` right border
- **Logo**: App name "MV Face" with icon at top
- **Collapse button**: Bottom of sidebar

### Navigation Items
- **Default**: `slate-400` text, transparent background
- **Hover**: `slate-300` text, `slate-800` background
- **Active**: `blue-400` text, `blue-500/10` background, `blue-500` left border accent
- **Icon size**: 20px
- **Spacing**: 12px padding, 8px gap between icon and label

### Content Area
- **Background**: `slate-950`
- **Header**: Section title, breadcrumbs if needed
- **Padding**: 24px on desktop, 16px on mobile

### Responsive Behavior
- **Desktop (lg+)**: Full sidebar visible
- **Tablet (md)**: Collapsed sidebar (icons only)
- **Mobile (sm)**: Bottom navigation bar with 5 icons

## Typography
- **Logo**: Noto Sans TC, 600 weight, 18px
- **Nav labels**: Noto Sans TC, 500 weight, 14px
- **Section headers**: Noto Sans TC, 600 weight, 24px

## Accessibility
- All navigation items keyboard accessible
- ARIA labels for collapsed state
- Focus indicators using `ring-2 ring-blue-500`
- Skip to main content link
