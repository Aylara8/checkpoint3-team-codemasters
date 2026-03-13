document.addEventListener('DOMContentLoaded', () => {
    // 1. DELETE RESOURCE (FIXED)
    document.addEventListener('click', async (e) => {
        const btn = e.target.closest('.delete-res-btn');
        if (!btn) return;

        const resId = btn.getAttribute('data-id');
        const cardCol = document.getElementById(`resource-col-${resId}`);
        
        if (!confirm('Permanently delete this resource?')) return;

        try {
            const response = await fetch(`/api/delete/${resId}`, { method: 'POST' });
            const data = await response.json();
            if (data.success) {
                cardCol.classList.add('fade-out'); // Add CSS for this!
                setTimeout(() => cardCol.remove(), 400);
            }
        } catch (err) { alert('Error deleting item'); }
    });

    // 2. AJAX RATING
    document.addEventListener('click', async (e) => {
        const star = e.target.closest('.star-rating');
        if (!star) return;
        const resId = star.dataset.resId;
        const val = star.dataset.value;

        const response = await fetch(`/api/rate/${resId}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({rating: val})
        });
        if (response.ok) location.reload(); // Quick UI refresh
    });
});

// UX: Quick focus search with "/" key
document.addEventListener('keydown', (e) => {
    if (e.key === '/' && document.activeElement.tagName !== 'INPUT') {
        e.preventDefault();
        document.querySelector('input[name="q"]').focus();
    }
});

// UX: Fade in cards one by one
document.addEventListener('DOMContentLoaded', () => {
    const cards = document.querySelectorAll('.resource-card');
    cards.forEach((card, index) => {
        setTimeout(() => {
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, index * 100);
    });
});

function checkStrength(password) {
    let strength = 0;
    if (password.length >= 8) strength += 25;
    if (password.match(/[A-Z]/)) strength += 25;
    if (password.match(/[0-9]/)) strength += 25;
    if (password.match(/[!@#$%^&*]/)) strength += 25;

    let bar = document.getElementById('strength-bar');
    bar.style.width = strength + '%';
    
    if (strength <= 50) bar.className = "progress-bar bg-danger";
    else if (strength <= 75) bar.className = "progress-bar bg-warning";
    else bar.className = "progress-bar bg-success";
}