# Design System Usage Guide

## Overview

The MV Face Recognition frontend uses a comprehensive, UX-focused design system with design tokens, reusable components, and consistent patterns.

**Documentation**: See `DESIGN.md` - "Frontend Design System" section for full specification.

---

## Quick Start

### 1. Using Design Tokens

Design tokens are automatically available in all components via CSS variables:

```svelte
<style>
  .my-component {
    /* Colors - Use semantic tokens */
    background-color: var(--bg-secondary);
    color: var(--text-primary);
    border: 1px solid var(--border-default);

    /* Spacing - Use spacing scale */
    padding: var(--space-4);
    margin: var(--space-2) var(--space-6);
    gap: var(--space-3);

    /* Typography - Use type scale */
    font-size: var(--text-body-size);
    font-weight: var(--text-label-weight);
    line-height: var(--text-body-line);

    /* Border Radius - Use radius tokens */
    border-radius: var(--radius-md);

    /* Shadows - Use shadow tokens */
    box-shadow: var(--shadow);

    /* Transitions - Use transition presets */
    transition: var(--transition-colors);
  }
</style>
```

### 2. Using Components

Import components from the component library:

```svelte
<script lang="ts">
  import { Button, Card, Input } from '$lib/components';

  let email = '';
  let emailError = '';

  function handleSubmit() {
    // Handle form submission
  }
</script>

<Card variant="elevated" padding="lg">
  <h2>Login Form</h2>

  <Input
    label="Email"
    type="email"
    bind:value={email}
    error={emailError}
    placeholder="Enter your email"
    required
  />

  <Button variant="primary" size="md" on:click={handleSubmit}>
    Sign In
  </Button>
</Card>
```

---

## Design Token Reference

### Color Tokens

**Use semantic colors** for context-aware theming:

```css
/* Background Colors */
--bg-primary     /* Main background */
--bg-secondary   /* Cards, panels */
--bg-tertiary    /* Elevated surfaces */
--bg-elevated    /* Floating elements */

/* Text Colors */
--text-primary   /* Main text */
--text-secondary /* Secondary text */
--text-tertiary  /* Muted text */
--text-disabled  /* Disabled text */

/* Border Colors */
--border-subtle
--border-default
--border-strong

/* Semantic State Colors */
--color-primary-500   /* Primary actions */
--color-success-500   /* Success states */
--color-warning-500   /* Warning states */
--color-error-500     /* Error states */
--color-info-500      /* Info states */
```

### Typography Tokens

```css
/* Headings */
--text-h1-size, --text-h1-weight, --text-h1-line
--text-h2-size, --text-h2-weight, --text-h2-line
--text-h3-size, --text-h3-weight, --text-h3-line
--text-h4-size, --text-h4-weight, --text-h4-line

/* Body Text */
--text-body-lg-size   /* 18px */
--text-body-size      /* 16px */
--text-body-sm-size   /* 14px */
--text-body-xs-size   /* 12px */
--text-body-line      /* Line height */

/* UI Text */
--text-label-size, --text-label-weight
--text-caption-size, --text-caption-weight
```

### Spacing Tokens (8px grid)

```css
--space-1   /* 4px  - Minimal */
--space-2   /* 8px  - Tight */
--space-3   /* 12px - Comfortable */
--space-4   /* 16px - Default */
--space-5   /* 20px - Medium */
--space-6   /* 24px - Large */
--space-8   /* 32px - Section */
--space-10  /* 40px - Large section */
--space-12  /* 48px - Major section */
--space-16  /* 64px - Page section */
```

---

## Component API

### Button

```svelte
<Button
  variant="primary"      {/* primary | secondary | success | danger | ghost */}
  size="md"              {/* sm | md | lg */}
  disabled={false}
  loading={false}
  fullWidth={false}
  type="button"          {/* button | submit | reset */}
  href={undefined}       {/* Optional link URL */}
  on:click={handleClick}
>
  Click Me
</Button>
```

### Card

```svelte
<Card
  variant="elevated"     {/* surface | elevated | bordered | interactive */}
  padding="md"           {/* none | sm | md | lg | xl */}
  href={undefined}       {/* Optional link URL */}
  clickable={false}      {/* Make non-link card clickable */}
  on:click={handleClick}
>
  Card content
</Card>
```

### Input

```svelte
<Input
  bind:value={inputValue}
  type="text"            {/* text | email | password | number | tel | url | search */}
  label="Field Label"
  placeholder="Enter value"
  helperText="Optional helper text"
  error={errorMessage}   {/* Error message string or undefined */}
  size="md"              {/* sm | md | lg */}
  disabled={false}
  required={false}
  readonly={false}
  on:input={handleInput}
  on:change={handleChange}
/>
```

---

## Usage Patterns

### Creating a Form

```svelte
<script lang="ts">
  import { Button, Card, Input } from '$lib/components';

  let formData = {
    name: '',
    email: '',
    password: ''
  };

  let errors = {
    name: '',
    email: '',
    password: ''
  };

  function handleSubmit() {
    // Validate and submit
  }
</script>

<Card variant="elevated" padding="lg">
  <h2 style="margin-bottom: var(--space-6)">Registration</h2>

  <div style="display: flex; flex-direction: column; gap: var(--space-4);">
    <Input
      label="Full Name"
      bind:value={formData.name}
      error={errors.name}
      required
    />

    <Input
      type="email"
      label="Email"
      bind:value={formData.email}
      error={errors.email}
      helperText="We'll never share your email"
      required
    />

    <Input
      type="password"
      label="Password"
      bind:value={formData.password}
      error={errors.password}
      helperText="Must be at least 8 characters"
      required
    />

    <Button
      variant="primary"
      size="lg"
      fullWidth
      on:click={handleSubmit}
    >
      Create Account
    </Button>
  </div>
</Card>
```

### Creating a Dashboard Card

```svelte
<script lang="ts">
  import { Card, Button } from '$lib/components';
</script>

<Card variant="bordered" padding="md" clickable on:click={() => console.log('Card clicked')}>
  <div style="display: flex; justify-content: space-between; align-items: center; gap: var(--space-4);">
    <div>
      <h3 style="font-size: var(--text-h4-size); margin-bottom: var(--space-2);">
        Video Processing
      </h3>
      <p style="color: var(--text-secondary); font-size: var(--text-body-sm-size);">
        15 videos processed today
      </p>
    </div>

    <Button variant="ghost" size="sm">
      View Details
    </Button>
  </div>
</Card>
```

---

## Best Practices

### ✅ DO

- **Use design tokens** for all styling (colors, spacing, typography)
- **Use semantic color names** (`--color-error-500` instead of `#ef4444`)
- **Follow spacing scale** (var(--space-4), not `padding: 16px`)
- **Use component props** for variants instead of custom styling
- **Maintain accessibility** (proper labels, ARIA attributes, keyboard navigation)

### ❌ DON'T

- **Hardcode values** (use tokens: `var(--space-4)` not `16px`)
- **Use arbitrary colors** (use palette: `var(--color-primary-500)` not `#3b82f6`)
- **Override component internals** (use props and variants instead)
- **Ignore responsive design** (test at all breakpoints)
- **Skip accessibility** (labels, focus states, ARIA are required)

---

## Theme Switching

The design system supports light and dark themes via the `data-theme` attribute:

```typescript
// Toggle theme
function toggleTheme() {
  const currentTheme = document.documentElement.getAttribute('data-theme');
  const newTheme = currentTheme === 'light' ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', newTheme);
}
```

Default is dark theme. All tokens automatically adapt.

---

## Next Steps

### Extending the Component Library

Create new components following the established patterns:

1. Use design tokens exclusively
2. Support size variants (sm/md/lg)
3. Include proper TypeScript types
4. Add accessibility features (ARIA, keyboard navigation)
5. Export from `$lib/components/index.ts`

### Additional Components to Build

Recommended next components:
- **Badge**: Status indicators
- **Toast**: Notifications
- **Modal**: Dialog boxes
- **Select**: Dropdown menus
- **Checkbox/Radio**: Form controls
- **Toggle**: Switch controls
- **Tooltip**: Hover information
- **Spinner**: Loading states
- **Progress**: Progress bars
- **Avatar**: User images

---

## Resources

- **Design Specification**: `/DESIGN.md` - "Frontend Design System" section
- **Design Tokens**: `/mvp-processor/src/lib/styles/design-tokens.css`
- **Components**: `/mvp-processor/src/lib/components/`
- **WCAG Guidelines**: https://www.w3.org/WAI/WCAG21/quickref/

---

*Last Updated: January 2025*
