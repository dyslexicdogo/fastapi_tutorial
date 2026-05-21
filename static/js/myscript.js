const sidebar = document.getElementById('sidebar');
const overlay = document.getElementById('sidebarOverlay');
const hamburger = document.getElementById('hamburgerBtn');
const closeBtn = document.getElementById('closeSidebarBtn');
const desktopToggle = document.getElementById('desktopSidebarToggle');
const navLinks = document.querySelectorAll('.sidebar-link');

let sidebarOpen = false;

function setSidebar(open) {
  sidebarOpen = open;
  if (open) {
    sidebar.classList.remove('-translate-x-full');
    sidebar.classList.add('translate-x-0');
    overlay.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
  } else {
    sidebar.classList.add('-translate-x-full');
    sidebar.classList.remove('translate-x-0');
    overlay.classList.add('hidden');
    document.body.style.overflow = '';
  }
}

setSidebar(false);

if (hamburger)    hamburger.addEventListener('click', () => setSidebar(true));
if (closeBtn)     closeBtn.addEventListener('click', () => setSidebar(false));
if (overlay)      overlay.addEventListener('click', () => setSidebar(false));
if (desktopToggle) desktopToggle.addEventListener('click', () => setSidebar(!sidebarOpen));

navLinks.forEach(link => {
  link.addEventListener('click', () => setSidebar(false));
});
