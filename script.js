let words = [];
const MAX_WORD_LENGTH = 10;

async function loadWords() {
  const response = await fetch('rzeczowniki.txt');
  const text = await response.text();
  words = text.split(/\r?\n/).map(w => w.trim()).filter(w => w.length && w.length <= MAX_WORD_LENGTH);
}

function filterWords(pattern) {
  let regex;
  try {
    const single = pattern.replace(/ /g, '.*');
    regex = new RegExp(`^${single}\\w*$`, 'i');
  } catch (e) {
    alert('Invalid regex pattern');
    return [];
  }
  return words.filter(w => regex.test(w)).sort((a, b) => a.length - b.length || a.localeCompare(b));
}

function displayWords(list) {
  const wordList = document.getElementById('word-list');
  wordList.innerHTML = '';
  list.forEach(w => {
    const li = document.createElement('li');
    li.textContent = w;
    li.addEventListener('click', () => window.open(`https://www.google.com/search?q=${encodeURIComponent(w)}`));
    wordList.appendChild(li);
  });
  document.getElementById('result-count').textContent = `Results: ${list.length}`;
}

document.getElementById('search').addEventListener('click', () => {
  const pattern = document.getElementById('pattern').value;
  if (pattern.toLowerCase() === 'q') {
    return;
  }
  const matched = filterWords(pattern);
  displayWords(matched);
  document.getElementById('pattern').value = '';
  document.getElementById('pattern').focus();
});

document.getElementById('pattern').addEventListener('keydown', e => {
  if (e.key === 'Enter') document.getElementById('search').click();
});

document.getElementById('copy').addEventListener('click', async () => {
  const list = document.getElementById('word-list').querySelectorAll('li');
  const text = Array.from(list).map(li => li.textContent).join('\n');
  try {
    await navigator.clipboard.writeText(text);
    alert(`Copied ${list.length} words to clipboard`);
  } catch {
    alert('Failed to copy to clipboard');
  }
});

window.addEventListener('load', async () => {
  await loadWords();
});
