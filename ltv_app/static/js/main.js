/* ── Navbar: hamburger + mobile dropdowns ─────────────────────── */
document.addEventListener('DOMContentLoaded', function () {
    var toggle = document.querySelector('.nav-toggle');
    var navList = document.querySelector('.nav-list');

    if (!toggle || !navList) return;

    // hamburger open/close
    toggle.addEventListener('click', function () {
        var isOpen = navList.classList.toggle('open');
        toggle.classList.toggle('open', isOpen);
    });

    // mobile: tap dropdown triggers instead of hover
    navList.querySelectorAll('li.has-dropdown > span').forEach(function (trigger) {
        trigger.addEventListener('click', function () {
            var li = this.parentElement;
            // close any other open dropdowns
            navList.querySelectorAll('li.has-dropdown.open').forEach(function (el) {
                if (el !== li) el.classList.remove('open');
            });
            li.classList.toggle('open');
        });
    });

    // close nav when clicking outside
    document.addEventListener('click', function (e) {
        if (!e.target.closest('.navbar')) {
            navList.classList.remove('open');
            toggle.classList.remove('open');
            navList.querySelectorAll('li.has-dropdown.open').forEach(function (el) {
                el.classList.remove('open');
            });
        }
    });
});

/* ── Clickable table rows ─────────────────────────────────────── */
document.addEventListener('click', function (e) {
    var row = e.target.closest('tr.clickable-row');
    if (row && row.dataset.href) {
        window.location.href = row.dataset.href;
    }
});

/* ── Shared confirm modal (replaces native confirm()) ───────────── */
function showConfirmModal(message, onConfirm, options) {
    options = options || {};
    var modal = document.getElementById('confirmModal');
    if (!modal) { if (onConfirm) onConfirm(); return; }

    document.getElementById('confirmModalMessage').textContent = message;

    var okBtn = document.getElementById('confirmModalOk');
    var newOkBtn = okBtn.cloneNode(true);
    okBtn.parentNode.replaceChild(newOkBtn, okBtn);
    okBtn = newOkBtn;

    okBtn.className = 'btn ' + (options.variant === 'primary' ? 'btn-primary' : 'btn-danger');

    var typedInput = document.getElementById('confirmModalTypedInput');
    if (options.requireTyped) {
        typedInput.style.display = 'block';
        typedInput.value = '';
        okBtn.disabled = true;
        typedInput.oninput = function () {
            okBtn.disabled = typedInput.value !== options.requireTyped;
        };
    } else {
        typedInput.style.display = 'none';
        typedInput.oninput = null;
        okBtn.disabled = false;
    }

    okBtn.addEventListener('click', function () {
        closeConfirmModal();
        onConfirm();
    });
    modal.classList.add('active');
}
function closeConfirmModal() {
    var modal = document.getElementById('confirmModal');
    if (modal) modal.classList.remove('active');
    var typedInput = document.getElementById('confirmModalTypedInput');
    if (typedInput) { typedInput.value = ''; typedInput.style.display = 'none'; typedInput.oninput = null; }
}
document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeConfirmModal();
});
document.addEventListener('DOMContentLoaded', function () {
    var modal = document.getElementById('confirmModal');
    if (modal) {
        modal.addEventListener('click', function (e) {
            if (e.target === modal) closeConfirmModal();
        });
    }
});
