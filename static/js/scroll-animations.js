document.addEventListener('DOMContentLoaded', () => {
    gsap.registerPlugin(ScrollTrigger);

    // ==========================================
    // 1. Global Section Reveals
    // ==========================================
    // Select all major sections or containers
    const sections = gsap.utils.toArray('section, .py-24, .py-12, .min-h-\\[85vh\\]');

    sections.forEach(section => {
        gsap.fromTo(section, 
            { 
                opacity: 0, 
                y: 50 
            },
            {
                opacity: 1,
                y: 0,
                duration: 1,
                ease: "power3.out",
                scrollTrigger: {
                    trigger: section,
                    start: "top 80%", // Animation starts when top of section hits 80% of viewport
                    toggleActions: "play none none reverse"
                }
            }
        );
    });

    // ==========================================
    // 2. Heading "Rise & Unmask" with Glow
    // ==========================================
    const headings = gsap.utils.toArray('h1, h2, h3');
    
    headings.forEach(heading => {
        // Create a glow effect element if possible, or just animate the text
        // For "unmasking", we simulate it with clip-path or simple Y translation + opacity
        
        gsap.fromTo(heading,
            {
                y: 100,
                opacity: 0,
                clipPath: "inset(100% 0 0 0)"
            },
            {
                y: 0,
                opacity: 1,
                clipPath: "inset(0% 0 0 0)",
                duration: 1.2,
                ease: "power4.out",
                scrollTrigger: {
                    trigger: heading,
                    start: "top 90%",
                    toggleActions: "play none none reverse"
                }
            }
        );
    });

    // ==========================================
    // 3. Staggered Cards & Content
    // ==========================================
    // Target grids to stagger their children
    const grids = gsap.utils.toArray('.grid');

    grids.forEach(grid => {
        // Get direct children
        const children = grid.children;
        
        if(children.length > 0) {
            gsap.fromTo(children,
                {
                    y: 50,
                    opacity: 0,
                    scale: 0.95,
                    filter: "blur(10px)" // Motion blur simulation
                },
                {
                    y: 0,
                    opacity: 1,
                    scale: 1,
                    filter: "blur(0px)",
                    duration: 0.8,
                    stagger: 0.15, // Stagger effect
                    ease: "back.out(1.7)", // Physics-based easing
                    scrollTrigger: {
                        trigger: grid,
                        start: "top 85%",
                        toggleActions: "play none none reverse"
                    }
                }
            );
        }
    });

    // ==========================================
    // 4. Scroll-Linked Background Motion (Parallax)
    // ==========================================
    // Target background blobs and floating elements
    const parallaxElements = gsap.utils.toArray('.parallax-bg, .animate-float');

    parallaxElements.forEach((el, i) => {
        // Vary the speed based on index or random
        const speed = (i + 1) * 20; 
        
        gsap.to(el, {
            y: -speed, // Move up as we scroll down
            ease: "none",
            scrollTrigger: {
                trigger: document.body,
                start: "top top",
                end: "bottom bottom",
                scrub: 1 // Smooth scrubbing
            }
        });
    });

    // ==========================================
    // 5. Progress Line / Reading Indicator (Disabled per user request)
    // ==========================================
    /* 
    // Add a progress line at the top
    const progressLine = document.createElement('div');
    progressLine.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        height: 3px;
        background: linear-gradient(90deg, #00B4FF, #00E676);
        width: 0%;
        z-index: 9999;
        box-shadow: 0 0 10px rgba(0, 180, 255, 0.5);
    `;
    document.body.appendChild(progressLine);

    gsap.to(progressLine, {
        width: "100%",
        ease: "none",
        scrollTrigger: {
            trigger: document.body,
            start: "top top",
            end: "bottom bottom",
            scrub: 0.3
        }
    });
    */

    // ==========================================
    // 6. Image/Visual Reveals
    // ==========================================
    const images = gsap.utils.toArray('img, .tilt-card');
    
    images.forEach(img => {
        gsap.fromTo(img,
            {
                scale: 1.1,
                opacity: 0,
                filter: "grayscale(100%) blur(5px)"
            },
            {
                scale: 1,
                opacity: 1,
                filter: "grayscale(0%) blur(0px)",
                duration: 1.5,
                ease: "power2.out",
                scrollTrigger: {
                    trigger: img,
                    start: "top 80%",
                    toggleActions: "play none none reverse"
                }
            }
        );
    });

    // ==========================================
    // 7. 3D Tilt Effect (Mouse Follow)
    // ==========================================
    const tiltCards = document.querySelectorAll('.tilt-card');

    tiltCards.forEach(card => {
        card.addEventListener('mousemove', (e) => {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            
            // Calculate percentage from center (-1 to 1)
            const xPct = (x / rect.width - 0.5) * 2;
            const yPct = (y / rect.height - 0.5) * 2;
            
            // Tilt amount (degrees)
            const tiltX = yPct * -10; // Invert Y for natural tilt
            const tiltY = xPct * 10;
            
            gsap.to(card, {
                duration: 0.5,
                transformPerspective: 1000,
                rotateX: tiltX,
                rotateY: tiltY,
                scale: 1.05,
                ease: "power2.out",
                overwrite: "auto"
            });
        });
        
        card.addEventListener('mouseleave', () => {
            gsap.to(card, {
                duration: 0.5,
                rotateX: 0,
                rotateY: 0,
                scale: 1,
                ease: "power2.out",
                overwrite: "auto"
            });
        });
    });

});
