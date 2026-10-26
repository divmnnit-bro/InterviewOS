import gsap from 'gsap';

export const prefersReducedMotion = (): boolean => {
  if (typeof window === 'undefined') return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
};

/**
 * Animate page or container entrance with smooth fade & subtle slide-up
 */
export const animatePageIn = (target: string | Element | null): gsap.core.Tween | null => {
  if (!target || prefersReducedMotion()) return null;
  return gsap.fromTo(
    target,
    { opacity: 0, y: 14 },
    { opacity: 1, y: 0, duration: 0.35, ease: 'power2.out' }
  );
};

/**
 * Animate staggered child elements (cards, table rows, pipeline columns)
 */
export const animateStaggerIn = (
  targets: string | Element[] | NodeListOf<Element>,
  stagger = 0.05
): gsap.core.Tween | null => {
  if (!targets || prefersReducedMotion()) return null;
  return gsap.fromTo(
    targets,
    { opacity: 0, y: 12 },
    { opacity: 1, y: 0, duration: 0.3, stagger, ease: 'power2.out' }
  );
};

/**
 * Modal dialog reveal animation
 */
export const animateModalIn = (backdrop: Element | null, content: Element | null): gsap.core.Timeline | null => {
  if (!content || prefersReducedMotion()) return null;
  const tl = gsap.timeline();
  if (backdrop) {
    tl.fromTo(backdrop, { opacity: 0 }, { opacity: 1, duration: 0.2, ease: 'power1.out' }, 0);
  }
  tl.fromTo(
    content,
    { opacity: 0, scale: 0.95, y: -10 },
    { opacity: 1, scale: 1, y: 0, duration: 0.25, ease: 'back.out(1.4)' },
    0.05
  );
  return tl;
};

/**
 * Drawer slide animation
 */
export const animateDrawerIn = (drawer: Element | null): gsap.core.Tween | null => {
  if (!drawer || prefersReducedMotion()) return null;
  return gsap.fromTo(
    drawer,
    { x: '-100%' },
    { x: '0%', duration: 0.28, ease: 'power3.out' }
  );
};

/**
 * Dropdown / popover reveal animation
 */
export const animateDropdownIn = (menu: Element | null): gsap.core.Tween | null => {
  if (!menu || prefersReducedMotion()) return null;
  return gsap.fromTo(
    menu,
    { opacity: 0, scale: 0.96, y: -6 },
    { opacity: 1, scale: 1, y: 0, duration: 0.18, ease: 'power2.out' }
  );
};
