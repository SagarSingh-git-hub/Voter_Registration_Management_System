/**
 * VRMS — Cinematic Scroll Experience
 * Parallax Scrolling + Scroll-Triggered Reveals + Counter Animations
 * Powered by GSAP 3 + ScrollTrigger
 */

document.addEventListener('DOMContentLoaded', () => {
    if (typeof gsap === 'undefined' || typeof ScrollTrigger === 'undefined') return;

    gsap.registerPlugin(ScrollTrigger);

    // ─────────────────────────────────────────────────────────
    // HELPER: is element inside the hero section?
    // ─────────────────────────────────────────────────────────
    const heroSection = document.querySelector('[class*="min-h-"]');  // the hero wrapper div
    function inHero(el) {
        if (!heroSection) return false;
        return heroSection.contains(el) || el === heroSection;
    }

    // ─────────────────────────────────────────────────────────
    // 0. SCROLL PROGRESS BAR
    // ─────────────────────────────────────────────────────────
    const progressBar = document.createElement('div');
    progressBar.id = 'scroll-progress';
    progressBar.style.cssText = `
        position: fixed;
        top: 0; left: 0;
        height: 3px;
        width: 0%;
        background: linear-gradient(90deg, #0F4C75, #00B4FF, #00E676);
        z-index: 9999;
        box-shadow: 0 0 12px rgba(0,180,255,0.6);
        pointer-events: none;
    `;
    document.body.appendChild(progressBar);

    gsap.to(progressBar, {
        width: '100%',
        ease: 'none',
        scrollTrigger: {
            trigger: document.body,
            start: 'top top',
            end: 'bottom bottom',
            scrub: 0.4,
        }
    });

    // ─────────────────────────────────────────────────────────
    // 1. AMBIENT BLOB PARALLAX (fixed background blobs)
    // ─────────────────────────────────────────────────────────
    const blobSpeeds = [-0.15, 0.12];
    document.querySelectorAll('.parallax-bg').forEach((el, i) => {
        const speed = blobSpeeds[i] ?? -0.1;
        gsap.to(el, {
            y: () => window.innerHeight * speed * 1.5,
            ease: 'none',
            scrollTrigger: {
                trigger: document.body,
                start: 'top top',
                end: 'bottom bottom',
                scrub: true,
            }
        });
    });

    // ─────────────────────────────────────────────────────────
    // 2. HERO ENTRANCE (text only — card stays always visible)
    // ─────────────────────────────────────────────────────────
    // ⚠️ We deliberately do NOT animate the tilt-card or its
    // parent container with opacity:0 to prevent it disappearing.
    const heroBadge     = document.querySelector('.inline-flex.items-center.gap-2.px-3');
    const heroH1        = document.querySelector('h1');
    const heroP         = heroH1 ? heroH1.nextElementSibling : null;
    const heroBtns      = document.querySelector('.flex.flex-col.sm\\:flex-row.gap-4');
    const heroBadgeNote = document.querySelector('.pt-4.flex.items-center');

    const heroTl = gsap.timeline({ defaults: { ease: 'power4.out' } });
    if (heroBadge)     heroTl.from(heroBadge,     { y: 20, opacity: 0, duration: 0.7 }, 0.2);
    if (heroH1)        heroTl.from(heroH1,        { y: 50, opacity: 0, duration: 1.0 }, 0.35);
    if (heroP)         heroTl.from(heroP,         { y: 30, opacity: 0, duration: 0.8 }, 0.6);
    if (heroBtns)      heroTl.from(heroBtns,      { y: 20, opacity: 0, duration: 0.7 }, 0.75);
    if (heroBadgeNote) heroTl.from(heroBadgeNote, { y: 15, opacity: 0, duration: 0.6 }, 0.9);

    // Hero card — only a subtle x-slide, NO opacity change
    const heroCard = document.querySelector('.tilt-card');
    if (heroCard) {
        gsap.from(heroCard, {
            x: 60,
            duration: 1.0,
            ease: 'power3.out',
            delay: 0.4,
        });
    }

    // ─────────────────────────────────────────────────────────
    // 3. HEADING REVEALS (clip-path sweep) — skip hero headings
    // ─────────────────────────────────────────────────────────
    document.querySelectorAll('h2, h3').forEach(h => {
        if (inHero(h)) return;              // skip hero headings
        if (h.closest('.tilt-card')) return; // skip card inner headings

        gsap.fromTo(h,
            { clipPath: 'inset(0 100% 0 0)', opacity: 0, x: -15 },
            {
                clipPath: 'inset(0 0% 0 0)',
                opacity: 1,
                x: 0,
                duration: 0.9,
                ease: 'power3.out',
                scrollTrigger: {
                    trigger: h,
                    start: 'top 88%',
                    toggleActions: 'play none none none',
                }
            }
        );
    });

    // ─────────────────────────────────────────────────────────
    // 4. SERVICE CARDS (6-grid below hero) — staggered reveal
    // ─────────────────────────────────────────────────────────
    // Target only the services grid, not the hero grid
    document.querySelectorAll('.grid').forEach(grid => {
        if (inHero(grid)) return;           // skip hero area entirely
        if (grid.contains(heroCard)) return; // extra safety

        const children = Array.from(grid.children).filter(c => c.tagName !== 'SCRIPT');
        if (!children.length) return;

        gsap.fromTo(children,
            { y: 50, opacity: 0, scale: 0.96 },
            {
                y: 0, opacity: 1, scale: 1,
                duration: 0.65,
                stagger: { each: 0.1, ease: 'power2.inOut' },
                ease: 'back.out(1.2)',
                scrollTrigger: {
                    trigger: grid,
                    start: 'top 83%',
                    toggleActions: 'play none none none',
                }
            }
        );
    });

    // ─────────────────────────────────────────────────────────
    // 5. BENEFIT ITEMS — slide from left
    // ─────────────────────────────────────────────────────────
    const benefitItems = Array.from(document.querySelectorAll('.flex.items-start.gap-4'))
        .filter(el => !inHero(el));

    if (benefitItems.length) {
        gsap.fromTo(benefitItems,
            { x: -45, opacity: 0 },
            {
                x: 0, opacity: 1,
                duration: 0.8, stagger: 0.15, ease: 'power3.out',
                scrollTrigger: {
                    trigger: benefitItems[0],
                    start: 'top 85%',
                    toggleActions: 'play none none none',
                }
            }
        );
    }

    // ─────────────────────────────────────────────────────────
    // 6. GLASS PANELS — fade + scale (EXCLUDE tilt-card & hero)
    // ─────────────────────────────────────────────────────────
    document.querySelectorAll('.glass-panel').forEach(panel => {
        if (inHero(panel)) return;           // skip hero panels
        if (panel.classList.contains('tilt-card')) return;
        if (panel.closest('.tilt-card')) return; // skip nested inside tilt

        gsap.fromTo(panel,
            { opacity: 0, scale: 0.97, y: 25 },
            {
                opacity: 1, scale: 1, y: 0,
                duration: 0.85, ease: 'power2.out',
                scrollTrigger: {
                    trigger: panel,
                    start: 'top 90%',
                    toggleActions: 'play none none none',
                }
            }
        );
    });

    // ─────────────────────────────────────────────────────────
    // 7. HOW IT WORKS — connector grow + step bounce
    // ─────────────────────────────────────────────────────────
    const stepsGrid = document.querySelector('.grid-cols-1.md\\:grid-cols-4, [class*="grid-cols-4"]');
    if (stepsGrid && !inHero(stepsGrid)) {
        const steps      = stepsGrid.querySelectorAll('.relative.text-center');
        const connectors = stepsGrid.querySelectorAll('.absolute.top-10.left-1\\/2');

        if (connectors.length) {
            gsap.fromTo(connectors,
                { scaleX: 0, transformOrigin: 'left center' },
                {
                    scaleX: 1, duration: 1.2, stagger: 0.3, ease: 'power2.inOut',
                    scrollTrigger: { trigger: stepsGrid, start: 'top 75%', toggleActions: 'play none none none' }
                }
            );
        }

        gsap.fromTo(steps,
            { y: 40, opacity: 0, scale: 0.82 },
            {
                y: 0, opacity: 1, scale: 1,
                duration: 0.65, stagger: 0.18, ease: 'back.out(1.7)',
                scrollTrigger: { trigger: stepsGrid, start: 'top 80%', toggleActions: 'play none none none' }
            }
        );
    }

    // ─────────────────────────────────────────────────────────
    // 8. TRUST STRIP
    // ─────────────────────────────────────────────────────────
    const trustStrip = document.querySelector('.border-y');
    if (trustStrip && !inHero(trustStrip)) {
        const trustItems = trustStrip.querySelectorAll('.flex.items-center');
        gsap.fromTo(trustItems,
            { y: 20, opacity: 0 },
            {
                y: 0, opacity: 1, duration: 0.55, stagger: 0.09, ease: 'power2.out',
                scrollTrigger: { trigger: trustStrip, start: 'top 92%', toggleActions: 'play none none none' }
            }
        );
    }

    // ─────────────────────────────────────────────────────────
    // 9. FAQ PANELS — 3D flip reveal (SKIP tilt-card panels)
    // ─────────────────────────────────────────────────────────
    const faqPanels = Array.from(document.querySelectorAll('.glass-panel')).filter(p => {
        if (inHero(p)) return false;
        if (p.classList.contains('tilt-card')) return false;
        if (p.closest('.tilt-card')) return false;
        // Only FAQ-area panels (inside .space-y-4 that's NOT the services grid)
        const parent = p.parentElement;
        return parent && parent.classList.contains('space-y-4') && !parent.closest('.grid');
    });

    if (faqPanels.length) {
        gsap.fromTo(faqPanels,
            { x: 35, opacity: 0, rotateY: 4 },
            {
                x: 0, opacity: 1, rotateY: 0,
                duration: 0.75, stagger: 0.18, ease: 'power3.out',
                scrollTrigger: {
                    trigger: faqPanels[0].parentElement,
                    start: 'top 87%',
                    toggleActions: 'play none none none',
                }
            }
        );
    }

    // ─────────────────────────────────────────────────────────
    // 10. STAT COUNTERS — animate numbers on scroll
    // ─────────────────────────────────────────────────────────
    document.querySelectorAll('.text-2xl.font-bold').forEach(el => {
        const text = el.textContent.trim();
        const match = text.match(/^([\d.]+)\s*(.*)$/);
        if (!match) return;

        const endVal  = parseFloat(match[1]);
        const suffix  = match[2] || '';
        const decimals = (match[1].split('.')[1] || '').length;
        const obj = { val: 0 };

        gsap.to(obj, {
            val: endVal, duration: 2, ease: 'power2.out',
            scrollTrigger: { trigger: el, start: 'top 92%', toggleActions: 'play none none none' },
            onUpdate() { el.textContent = obj.val.toFixed(decimals) + (suffix ? ' ' + suffix : ''); }
        });
    });

    // ─────────────────────────────────────────────────────────
    // 11. ROLE CARDS — slide from right
    // ─────────────────────────────────────────────────────────
    const roleCards = Array.from(document.querySelectorAll('a.group.p-6, a.group.p-4'))
        .filter(el => !inHero(el));

    if (roleCards.length) {
        gsap.fromTo(roleCards,
            { x: 50, opacity: 0 },
            {
                x: 0, opacity: 1, duration: 0.65, stagger: 0.14, ease: 'power3.out',
                scrollTrigger: {
                    trigger: roleCards[0].closest('.glass-panel') || roleCards[0],
                    start: 'top 86%',
                    toggleActions: 'play none none none',
                }
            }
        );
    }

    // ─────────────────────────────────────────────────────────
    // 12. FOOTER CASCADE
    // ─────────────────────────────────────────────────────────
    const footer = document.querySelector('footer');
    if (footer) {
        const footerCols = footer.querySelectorAll('.grid > div');
        gsap.fromTo(footerCols,
            { y: 35, opacity: 0 },
            {
                y: 0, opacity: 1, duration: 0.75, stagger: 0.1, ease: 'power3.out',
                scrollTrigger: { trigger: footer, start: 'top 92%', toggleActions: 'play none none none' }
            }
        );
    }

    // ─────────────────────────────────────────────────────────
    // 13. 3D TILT CARD — mouse-follow effect
    // ─────────────────────────────────────────────────────────
    document.querySelectorAll('.tilt-card').forEach(card => {
        card.style.transformStyle = 'preserve-3d';
        card.style.willChange = 'transform';

        card.addEventListener('mousemove', e => {
            const rect = card.getBoundingClientRect();
            const xPct = (e.clientX - rect.left) / rect.width  - 0.5;
            const yPct = (e.clientY - rect.top)  / rect.height - 0.5;
            gsap.to(card, {
                rotateX: yPct * -12, rotateY: xPct * 12,
                scale: 1.03, duration: 0.4, ease: 'power2.out', overwrite: 'auto',
                transformPerspective: 1000,
            });
        });

        card.addEventListener('mouseleave', () => {
            gsap.to(card, {
                rotateX: 0, rotateY: 0, scale: 1,
                duration: 0.55, ease: 'elastic.out(1, 0.6)', overwrite: 'auto',
            });
        });
    });

    // ─────────────────────────────────────────────────────────
    // 14. FLOATING BADGES — parallax on data-parallax elements
    //     (only y-movement, no opacity change)
    // ─────────────────────────────────────────────────────────
    document.querySelectorAll('[data-parallax]').forEach(el => {
        const speed = parseFloat(el.dataset.parallax) || 0.2;
        // Only vertical shift — never touch opacity
        gsap.to(el, {
            y: speed * 120,
            ease: 'none',
            scrollTrigger: {
                trigger: el.closest('[class*="min-h"]') || document.body,
                start: 'top top',
                end: 'bottom top',
                scrub: 1.5,
            }
        });
    });

    // ─────────────────────────────────────────────────────────
    // 15. SCAN LINE on hero (pure CSS animation via GSAP, no opacity on card)
    // ─────────────────────────────────────────────────────────
    const heroWrapper = document.querySelector('[class*="min-h-"]');
    if (heroWrapper) {
        const scanLine = document.createElement('div');
        scanLine.style.cssText = `
            position: absolute; left: 0; right: 0;
            height: 1px; top: 0; z-index: 5;
            background: linear-gradient(90deg, transparent, rgba(0,180,255,0.35), transparent);
            pointer-events: none;
        `;
        const heroPosition = window.getComputedStyle(heroWrapper).position;
        if (heroPosition === 'static') heroWrapper.style.position = 'relative';
        heroWrapper.appendChild(scanLine);

        gsap.to(scanLine, { top: '100%', duration: 3.5, ease: 'none', repeat: -1, delay: 1 });
    }

    // ─────────────────────────────────────────────────────────
    // 16. NAV COMPACT on scroll
    // ─────────────────────────────────────────────────────────
    const navbar = document.getElementById('navbar');
    if (navbar) {
        ScrollTrigger.create({
            trigger: document.body,
            start: 'top -60px',
            onEnter: () => {
                navbar.classList.add('nav-scrolled');
                gsap.to(navbar, { paddingTop: '0.4rem', paddingBottom: '0.4rem', duration: 0.35, ease: 'power2.out' });
            },
            onLeaveBack: () => {
                navbar.classList.remove('nav-scrolled');
                gsap.to(navbar, { paddingTop: '1rem', paddingBottom: '1rem', duration: 0.35, ease: 'power2.out' });
            },
        });
    }

    // ─────────────────────────────────────────────────────────
    // 17. GRID BACKGROUND parallax
    // ─────────────────────────────────────────────────────────
    const gridOverlay = document.getElementById('grid-overlay');
    if (gridOverlay) {
        gsap.to(gridOverlay, {
            backgroundPositionY: '25%',
            ease: 'none',
            scrollTrigger: { trigger: document.body, start: 'top top', end: 'bottom bottom', scrub: 2 }
        });
    }

    // ─────────────────────────────────────────────────────────
    // 18. ABOUT SECTION — blob parallax + text reveal
    // ─────────────────────────────────────────────────────────
    const aboutSection = document.querySelector('#about-vrms');
    if (aboutSection) {
        aboutSection.querySelectorAll('.absolute.rounded-full').forEach((blob, i) => {
            gsap.fromTo(blob,
                { y: 0 },
                {
                    y: i % 2 === 0 ? -35 : 35,
                    ease: 'none',
                    scrollTrigger: {
                        trigger: aboutSection, start: 'top bottom', end: 'bottom top', scrub: 2
                    }
                }
            );
        });

        gsap.fromTo(aboutSection.querySelectorAll('p'),
            { y: 22, opacity: 0 },
            {
                y: 0, opacity: 1, duration: 0.85, stagger: 0.18, ease: 'power2.out',
                scrollTrigger: { trigger: aboutSection, start: 'top 82%', toggleActions: 'play none none none' }
            }
        );
    }

});
