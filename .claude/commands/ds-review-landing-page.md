# Review & Improve Landing Page

**Goal**: Audit `docs/landing/index.html` from Staff UX Designer and Web Developer perspective, then implement approved improvements.

## Review Dimensions

| Dimension | Focus Areas |
|-----------|-------------|
| UX Design | Visual hierarchy, cognitive load, CTAs, whitespace, cross-device readability (desktop + mobile) |
| Accessibility | WCAG 2.1 AA compliance, keyboard navigation, screen reader support, color contrast |
| Performance | Asset loading, CSS efficiency, render-blocking resources, image optimization |
| SEO | Meta tags, semantic HTML, structured data, Open Graph |
| Code Quality | HTML semantics, CSS organization, JS patterns, maintainability |

## Review Checklist

| Category | Check For |
|----------|-----------|
| Visual hierarchy | Clear F-pattern or Z-pattern flow, proper heading levels |
| CTAs | Prominent, actionable, appropriate contrast ratios |
| Mobile | Touch targets ≥44px, no horizontal scroll, readable without zoom, tested for iPhone/Android viewports |
| Readability | Font sizes, line lengths, contrast readable on both desktop and mobile devices |
| Accessibility | Alt text, ARIA labels, focus states, skip links, landmark regions |
| Performance | Inline critical CSS, lazy loading images, minification opportunity |
| Semantics | Appropriate HTML5 elements, no div-soup, logical document outline |
| CSS | No unused rules, consistent naming, efficient selectors |
| Interactive | Keyboard accessible, visible focus, no motion for reduced-motion users |

## Approach

| Step | Action |
|------|--------|
| Audit | Read page, identify issues across all dimensions |
| Prioritize | Rank findings by impact (Critical → High → Medium → Low) |
| Present | Show findings with specific line references |
| Confirm | Use `AskUserQuestion` to approve implementation scope |
| Implement | Apply approved changes |
| Verify | Confirm changes don't break existing functionality |

## Output Format

Present findings as:

```
## [Dimension] Issues

| Priority | Issue | Location | Fix |
|----------|-------|----------|-----|
| Critical | ... | Line X | ... |

**Summary**: 1-2 sentence description of what changes will be made.
```

After all dimensions reviewed, provide:

```
## Implementation Summary

[Concise list of all fixes to be applied, grouped by type]
```

## Constraints

- Read the file before making any suggestions
- Preserve existing visual design intent
- No framework additions (keep vanilla HTML/CSS/JS)
- Ask before implementing changes
