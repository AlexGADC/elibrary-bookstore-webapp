// =====================================================================
// home.js - the image carousel (slideshow) on the home page.
//
// The slides are written in home.html by the server. This script makes them move:
//   - next / previous arrows and one round button per slide
//   - changes slide by itself every few seconds, with a Pause / Play button
//   - waits while the mouse is over it or a button inside it has focus
//   - left / right arrow keys, and swiping on a touch screen
// =====================================================================

document.addEventListener('DOMContentLoaded', () => {
    const carousel = document.getElementById('featuredCarousel');
    if (!carousel) {
        return;
    }

    const track = document.getElementById('carouselTrack');
    const slides = Array.from(track.children);
    const previousButton = document.getElementById('carouselPrev');
    const nextButton = document.getElementById('carouselNext');
    const dotsContainer = document.getElementById('carouselDots');
    const toggleButton = document.getElementById('carouselToggle');

    const AUTOPLAY_DELAY = 5000;  // milliseconds between slides
    const SWIPE_DISTANCE = 50;    // pixels a finger must travel to count as a swipe

    let currentIndex = 0;
    let autoplayTimer = null;
    let pausedByVisitor = false;  // true after the visitor presses Pause

    // With a single slide there is nothing to move
    if (slides.length < 2) {
        previousButton.hidden = true;
        nextButton.hidden = true;
        toggleButton.hidden = true;
        return;
    }

    // One round button per slide
    const dots = slides.map((slide, index) => {
        const dot = document.createElement('button');
        dot.type = 'button';
        dot.className = 'carousel-dot';
        dot.setAttribute('aria-label', `Show book ${index + 1} of ${slides.length}`);
        dot.addEventListener('click', () => {
            showSlide(index);
            restartAutoplay();
        });
        dotsContainer.appendChild(dot);
        return dot;
    });

    function showSlide(index) {
        // Wrap around: after the last slide comes the first, and the other way round
        currentIndex = (index + slides.length) % slides.length;

        track.style.transform = `translateX(-${currentIndex * 100}%)`;

        slides.forEach((slide, slideIndex) => {
            const isCurrent = slideIndex === currentIndex;
            slide.classList.toggle('is-active', isCurrent);
            slide.setAttribute('aria-hidden', String(!isCurrent));
            // "inert" keeps the keyboard out of the slides that are not on screen
            slide.inert = !isCurrent;
        });

        dots.forEach((dot, dotIndex) => {
            const isCurrent = dotIndex === currentIndex;
            dot.classList.toggle('is-active', isCurrent);
            dot.setAttribute('aria-current', isCurrent ? 'true' : 'false');
        });
    }

    function showNext() {
        showSlide(currentIndex + 1);
    }

    function showPrevious() {
        showSlide(currentIndex - 1);
    }

    function stopAutoplay() {
        clearInterval(autoplayTimer);
        autoplayTimer = null;
    }

    function startAutoplay() {
        if (pausedByVisitor || autoplayTimer) {
            return;
        }
        autoplayTimer = setInterval(showNext, AUTOPLAY_DELAY);
    }

    function restartAutoplay() {
        stopAutoplay();
        startAutoplay();
    }

    nextButton.addEventListener('click', () => {
        showNext();
        restartAutoplay();
    });

    previousButton.addEventListener('click', () => {
        showPrevious();
        restartAutoplay();
    });

    // The Pause / Play button stops the slideshow until the visitor starts it again
    toggleButton.addEventListener('click', () => {
        pausedByVisitor = !pausedByVisitor;

        if (pausedByVisitor) {
            stopAutoplay();
            toggleButton.textContent = 'Play';
            toggleButton.setAttribute('aria-label', 'Play the slideshow');
        } else {
            startAutoplay();
            toggleButton.textContent = 'Pause';
            toggleButton.setAttribute('aria-label', 'Pause the slideshow');
        }
    });

    // Wait while the visitor is reading a slide
    carousel.addEventListener('mouseenter', stopAutoplay);
    carousel.addEventListener('mouseleave', startAutoplay);
    carousel.addEventListener('focusin', stopAutoplay);
    carousel.addEventListener('focusout', startAutoplay);

    // Pause while the browser tab is in the background
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            stopAutoplay();
        } else {
            startAutoplay();
        }
    });

    carousel.addEventListener('keydown', (event) => {
        if (event.key === 'ArrowRight') {
            showNext();
            restartAutoplay();
        } else if (event.key === 'ArrowLeft') {
            showPrevious();
            restartAutoplay();
        }
    });

    // Swiping on phones and tablets
    let touchStartX = null;

    carousel.addEventListener('touchstart', (event) => {
        touchStartX = event.touches[0].clientX;
    }, { passive: true });

    carousel.addEventListener('touchend', (event) => {
        if (touchStartX === null) {
            return;
        }

        const distance = event.changedTouches[0].clientX - touchStartX;
        touchStartX = null;

        if (Math.abs(distance) < SWIPE_DISTANCE) {
            return;
        }

        if (distance < 0) {
            showNext();
        } else {
            showPrevious();
        }
        restartAutoplay();
    }, { passive: true });

    showSlide(0);
    startAutoplay();
});
