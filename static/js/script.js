/* ==========================================
   CAMPUSPULSE JAVASCRIPT
========================================== */

document.addEventListener("DOMContentLoaded", function () {

    console.log("CampusPulse Loaded Successfully!");

    /* ===========================
       Smooth Scrolling
    =========================== */

    document.querySelectorAll('a[href^="#"]').forEach(anchor => {

        anchor.addEventListener("click", function (e) {

            e.preventDefault();

            const target = document.querySelector(this.getAttribute("href"));

            if (target) {

                target.scrollIntoView({
                    behavior: "smooth"
                });

            }

        });

    });

    /* ===========================
       Hero Floating Animation
    =========================== */

    const dashboard = document.querySelector(".dashboard");

    if (dashboard) {

        let direction = 1;

        setInterval(() => {

            dashboard.style.transform =
                `translateY(${direction * 8}px)`;

            direction *= -1;

        }, 2000);

    }

    /* ===========================
       Statistics Counter
    =========================== */

    const counters = document.querySelectorAll(".card h2");

    counters.forEach(counter => {

        const target = counter.innerText;

        const number = parseInt(target.replace(/\D/g, ""));

        const suffix = target.replace(/[0-9]/g, "");

        let count = 0;

        const speed = number / 60;

        function updateCounter() {

            if (count < number) {

                count += speed;

                counter.innerText = Math.floor(count) + suffix;

                requestAnimationFrame(updateCounter);

            } else {

                counter.innerText = number + suffix;

            }

        }

        updateCounter();

    });

    /* ===========================
       Feature Card Hover
    =========================== */

    document.querySelectorAll(".feature-card").forEach(card => {

        card.addEventListener("mouseenter", () => {

            card.style.transform = "translateY(-12px) scale(1.03)";

        });

        card.addEventListener("mouseleave", () => {

            card.style.transform = "translateY(0px) scale(1)";

        });

    });

    /* ===========================
       Event Card Animation
    =========================== */

    document.querySelectorAll(".event").forEach((card, index) => {

        card.style.animation = `fadeUp .8s ease ${index * .2}s forwards`;

    });

    /* ===========================
       Scroll Reveal
    =========================== */

    const reveals = document.querySelectorAll(

        ".feature-card,.card,.dashboard,.event"

    );

    function revealOnScroll() {

        reveals.forEach(item => {

            const top = item.getBoundingClientRect().top;

            const windowHeight = window.innerHeight;

            if (top < windowHeight - 100) {

                item.style.opacity = "1";

                item.style.transform = "translateY(0px)";

            }

        });

    }

    reveals.forEach(item => {

        item.style.opacity = "0";

        item.style.transform = "translateY(40px)";

        item.style.transition = ".8s";

    });

    revealOnScroll();

    window.addEventListener("scroll", revealOnScroll);

    /* ===========================
       Navbar Background Change
    =========================== */

    const nav = document.querySelector("nav");

    window.addEventListener("scroll", () => {

        if (window.scrollY > 80) {

            nav.style.background = "rgba(7,17,45,.95)";

            nav.style.boxShadow = "0 10px 25px rgba(0,0,0,.3)";

        }

        else {

            nav.style.background = "rgba(7,17,45,.65)";

            nav.style.boxShadow = "none";

        }

    });

    /* ===========================
       Mouse Glow Effect
    =========================== */

    const glow = document.createElement("div");

    glow.style.position = "fixed";
    glow.style.width = "18px";
    glow.style.height = "18px";
    glow.style.borderRadius = "50%";
    glow.style.background = "rgba(255,193,7,.7)";
    glow.style.pointerEvents = "none";
    glow.style.filter = "blur(6px)";
    glow.style.zIndex = "9999";
    glow.style.transition = "transform .08s linear";

    document.body.appendChild(glow);

    document.addEventListener("mousemove", (e) => {

        glow.style.left = e.clientX - 9 + "px";

        glow.style.top = e.clientY - 9 + "px";

    });

    /* ===========================
       Button Ripple Effect
    =========================== */

    document.querySelectorAll(".btn1,.btn2,.login,.register").forEach(btn => {

        btn.addEventListener("click", function (e) {

            const circle = document.createElement("span");

            const size = Math.max(this.clientWidth, this.clientHeight);

            circle.style.width = size + "px";
            circle.style.height = size + "px";

            circle.style.position = "absolute";
            circle.style.borderRadius = "50%";
            circle.style.background = "rgba(255,255,255,.5)";
            circle.style.left = e.offsetX - size / 2 + "px";
            circle.style.top = e.offsetY - size / 2 + "px";
            circle.style.transform = "scale(0)";
            circle.style.animation = "ripple .6s linear";
            circle.style.pointerEvents = "none";

            this.appendChild(circle);

            setTimeout(() => {

                circle.remove();

            }, 600);

        });

    });

});

/* ==========================================
   Ripple Animation
========================================== */

const style = document.createElement("style");

style.innerHTML = `

@keyframes ripple{

0%{

transform:scale(0);

opacity:1;

}

100%{

transform:scale(4);

opacity:0;

}

}

`;

document.head.appendChild(style);