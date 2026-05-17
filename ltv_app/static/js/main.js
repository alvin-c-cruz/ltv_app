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

/* ── Confirmation dialog ──────────────────────────────────────── */
function confirmation_message() {
    return prompt("Type YES to proceed.", "") === 'YES';
}
