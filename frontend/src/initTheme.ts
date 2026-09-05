try {
  const theme = localStorage.getItem('hydenlyne_theme_preference');
  const isLight = theme === 'light';
  document.documentElement.dataset.theme = isLight ? 'light' : 'dark';
  document.documentElement.classList.add(isLight ? 'light' : 'dark');
} catch {
  document.documentElement.dataset.theme = 'dark';
  document.documentElement.classList.add('dark');
}
