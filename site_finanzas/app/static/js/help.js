(function () {
    // Initialize Bootstrap tooltips on all hint elements
    document.querySelectorAll('.mtr-hint[data-bs-toggle="tooltip"]').forEach(function (el) {
        new bootstrap.Tooltip(el, { trigger: 'hover focus click' });
    });

    // Onboarding modal: auto-show and dismiss via fetch
    var onboardingEl = document.getElementById('onboardingModal');
    if (onboardingEl) {
        var onboardingModal = new bootstrap.Modal(onboardingEl, {
            backdrop: 'static',
            keyboard: false
        });
        onboardingModal.show();
        onboardingEl.addEventListener('hidden.bs.modal', function () {
            var csrf = document.querySelector('meta[name="csrf-token"]');
            fetch('/onboarding/dismiss', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrf ? csrf.content : '',
                    'Content-Type': 'application/json'
                }
            }).catch(function () {});
        });
    }
})();
