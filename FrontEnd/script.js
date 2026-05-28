document.addEventListener("DOMContentLoaded", () => {
    // Animate bar chart heights
    const bars = document.querySelectorAll('.bar');
    setTimeout(() => {
        bars.forEach(bar => {
            const height = bar.getAttribute('data-height');
            bar.style.height = height;
        });
    }, 300);

    // Number counter animation function
    const animateValue = (obj, start, end, duration, prefix = '') => {
        let startTimestamp = null;
        const step = (timestamp) => {
            if (!startTimestamp) startTimestamp = timestamp;
            const progress = Math.min((timestamp - startTimestamp) / duration, 1);
            // Easing function: easeOutQuart
            const easeProgress = 1 - Math.pow(1 - progress, 4);
            const currentVal = Math.floor(easeProgress * (end - start) + start);
            
            // Format number with commas
            obj.innerHTML = prefix + currentVal.toLocaleString();
            
            if (progress < 1) {
                window.requestAnimationFrame(step);
            } else {
                obj.innerHTML = prefix + end.toLocaleString();
            }
        };
        window.requestAnimationFrame(step);
    };

    // Animate numbers for bars
    const barValues = document.querySelectorAll('.bar-value');
    barValues.forEach(val => {
        const target = parseInt(val.getAttribute('data-val'), 10);
        animateValue(val, 0, target, 2000);
    });

    // Animate total orders
    const totalOrdersEl = document.querySelector('.total-orders-value');
    const totalOrders = parseInt(totalOrdersEl.getAttribute('data-val'), 10);
    animateValue(totalOrdersEl, 0, totalOrders, 2000);

    // Animate circular progress
    const circularProgress = document.querySelector('.circular-progress');
    let angle = 0;
    const targetAngle = (totalOrders / 500) * 360; // Assuming 500 is max capacity for 100%
    const animateCircle = setInterval(() => {
        angle += 3;
        if (angle >= targetAngle) {
            clearInterval(animateCircle);
        } else {
            circularProgress.style.background = `conic-gradient(var(--color-orders) ${angle}deg, rgba(255, 255, 255, 0.05) ${angle}deg)`;
        }
    }, 15);

    // Animate total customers
    const totalCustomersEl = document.querySelector('.total-customers-value');
    const totalCustomers = parseInt(totalCustomersEl.getAttribute('data-val'), 10);
    animateValue(totalCustomersEl, 0, totalCustomers, 2000);

    // Animate total expenses
    const totalExpenseEl = document.querySelector('.total-expense-value');
    const totalExpense = parseInt(totalExpenseEl.getAttribute('data-val'), 10);
    animateValue(totalExpenseEl, 0, totalExpense, 2000, '$');
});
