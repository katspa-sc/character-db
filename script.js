const FANDOM_SORT_ORDER = [
  "League",
  "Pokemon",
  "DBD Killers (Offline)",
  "DBD Survivors (Offline)",
  "Guilty Gear",
  "Hades",
  "League",
  "Mortal",
  "Street Fighter",
  "Tekken",
  "Wiedźmin",
  "Gothic",
];

document.addEventListener('DOMContentLoaded', () => {
  // --- Globals and DOM Elements ---
  let allCharacters = [];
  let allFandoms = {};
  const elements = {
      searchBox: document.getElementById('search-box'),
      fullSearchCheck: document.getElementById('full-search-check'),
      delimiterCheck: document.getElementById('delimiter-check'),
      showIgnoredCheck: document.getElementById('show-ignored-check'),
      showUsedCheck: document.getElementById('show-used-check'),
      fandomList: document.getElementById('fandom-list'),
      toggleFandomsBtn: document.getElementById('toggle-fandoms-btn'),
      resultsGrid: document.getElementById('results-grid'),
      statusMessage: document.getElementById('status-message'),
      modal: document.getElementById('image-modal'),
      modalImage: document.getElementById('modal-image'),
      modalCaption: document.getElementById('modal-caption'),
      modalClose: document.querySelector('.modal-close')
  };

  // --- State Management using localStorage ---
  const stateManager = {
      getFlag: (hash, type) => localStorage.getItem(`${type}_${hash}`) === 'true',
      setFlag: (hash, type, value) => localStorage.setItem(`${type}_${hash}`, value),
      isIgnored: (hash) => stateManager.getFlag(hash, 'ignored'),
      isUsed: (hash) => stateManager.getFlag(hash, 'used'),
      toggleIgnored: (hash) => stateManager.setFlag(hash, 'ignored', !stateManager.isIgnored(hash)),
      toggleUsed: (hash) => stateManager.setFlag(hash, 'used', !stateManager.isUsed(hash))
  };

  // --- Main Initialization ---
  async function initialize() {
      try {
          const response = await fetch('data/characters.json');
          if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
          allCharacters = await response.json();
          
          populateFandomFilters();
          addEventListeners();
          performSearch(); // Initial display
          elements.statusMessage.textContent = `${allCharacters.length} characters loaded.`;

      } catch (error) {
          elements.statusMessage.textContent = `Failed to load character data: ${error.message}`;
          console.error(error);
      }
  }

  function populateFandomFilters() {
    // 1. Get a unique list of all fandom display names
    const allFandomNames = [...new Set(allCharacters.map(c => c.fandom_display))];

    // 2. Sort the fandoms using our custom logic
    allFandomNames.sort((a, b) => {
        const indexA = FANDOM_SORT_ORDER.indexOf(a);
        const indexB = FANDOM_SORT_ORDER.indexOf(b);

        if (indexA !== -1 && indexB !== -1) {
            // Both fandoms are in our priority list, sort by their index
            return indexA - indexB;
        }
        if (indexA !== -1) {
            // Only 'a' is in the priority list, so it comes first
            return -1;
        }
        if (indexB !== -1) {
            // Only 'b' is in the priority list, so it comes first
            return 1;
        }
        // Neither fandom is in the priority list, sort them alphabetically
        return a.localeCompare(b);
    });

    // 3. Create and append the checkboxes in the new sorted order
    allFandomNames.forEach(fandom => {
        const internalName = allCharacters.find(c => c.fandom_display === fandom).fandom_internal;
        allFandoms[internalName] = true; // Initially all selected

        const label = document.createElement('label');
        label.innerHTML = `<input type="checkbox" data-fandom="${internalName}" checked> ${fandom}`;
        elements.fandomList.appendChild(label);
    });
}

  // --- Event Listeners ---
  function addEventListeners() {
      ['input', 'change'].forEach(evt => {
          elements.searchBox.addEventListener(evt, performSearch);
          elements.fandomList.addEventListener(evt, handleFandomToggle);
          elements.fullSearchCheck.addEventListener(evt, performSearch);
          elements.delimiterCheck.addEventListener(evt, performSearch);
          elements.showIgnoredCheck.addEventListener(evt, performSearch);
          elements.showUsedCheck.addEventListener(evt, performSearch);
      });

      elements.toggleFandomsBtn.addEventListener('click', toggleAllFandoms);
      elements.resultsGrid.addEventListener('click', handleGridClick);
      elements.modalClose.addEventListener('click', () => elements.modal.classList.remove('show'));
      elements.modal.addEventListener('click', (e) => {
           if(e.target === elements.modal) elements.modal.classList.remove('show');
      });
  }
  
  // --- Search and Filter Logic ---
  function performSearch() {
      const searchTerm = elements.searchBox.value.trim();
      const filters = {
          fullSearch: elements.fullSearchCheck.checked,
          addDelimiter: elements.delimiterCheck.checked,
          showIgnored: elements.showIgnoredCheck.checked,
          showUsed: elements.showUsedCheck.checked
      };

      let filteredCharacters = allCharacters;

      // Fandom Filter
      const selectedFandoms = Object.keys(allFandoms).filter(f => allFandoms[f]);
      if (selectedFandoms.length > 0 && selectedFandoms.length < Object.keys(allFandoms).length) {
          filteredCharacters = filteredCharacters.filter(c => selectedFandoms.includes(c.fandom_internal));
      }

      // Ignored/Used Filter
      if (!filters.showIgnored) {
          filteredCharacters = filteredCharacters.filter(c => !stateManager.isIgnored(c.hash));
      }
      if (!filters.showUsed) {
          filteredCharacters = filteredCharacters.filter(c => !stateManager.isUsed(c.hash));
      }

      // Name Search Filter
      if (searchTerm) {
          let patternStr = searchTerm;
          if (filters.addDelimiter && patternStr.length === 2) {
              patternStr = patternStr[0] + ' ' + patternStr[1];
          }

          // Simple regex substitutions from your python script
          patternStr = patternStr.replace(/ /g, '.*');
          patternStr = patternStr.replace(/h/gi, '(ch|h)');
          patternStr = patternStr.replace(/w/gi, '(v|w)');
          patternStr = patternStr.replace(/sz/gi, '(sz|sh)');
          patternStr = patternStr.replace(/cz/gi, '(cz|ch)');
          
          const regex = new RegExp(filters.fullSearch ? patternStr : `^${patternStr}`, 'i');
          filteredCharacters = filteredCharacters.filter(c => regex.test(c.name));
      }
      
      renderResults(filteredCharacters);
  }
  
  // --- Rendering ---
  function renderResults(characters) {
    elements.resultsGrid.innerHTML = ''; // Clear previous results
    if (characters.length === 0) {
        elements.statusMessage.textContent = 'No results found.';
        return;
    }
    
    elements.statusMessage.textContent = `${characters.length} result(s) found.`;
    
    characters.forEach(char => {
        const isIgnored = stateManager.isIgnored(char.hash);
        const isUsed = stateManager.isUsed(char.hash);

        const card = document.createElement('div');
        card.className = 'char-card';
        card.dataset.hash = char.hash;
        if (isIgnored) card.classList.add('is-ignored');
        if (isUsed) card.classList.add('is-used');

        // The HTML is now much simpler, with no fallbacks.
        card.innerHTML = `
          <!-- A single img tag pointing directly to the webp file -->
          <img src="thumbnails/${char.thumbnail}" alt="${char.name}" class="char-thumbnail" loading="lazy">

          <!-- The overlay for used/ignored status -->
          <div class="status-overlay"></div>
          
          <div class="char-info">
              <div class="char-name">${char.name}</div>
              <div class="char-fandom">${char.fandom_display}</div>
          </div>

          <button class="action-btn ignore-btn ${isIgnored ? 'active' : ''}" title="Toggle Ignore (I)">I</button>
          <button class="action-btn used-btn ${isUsed ? 'active' : ''}" title="Toggle Used (U)">U</button>
      `;
        elements.resultsGrid.appendChild(card);
    });
}

  // --- Event Handlers ---
  function handleFandomToggle(event) {
      if (event.target.type === 'checkbox') {
          const fandom = event.target.dataset.fandom;
          allFandoms[fandom] = event.target.checked;
          performSearch();
      }
  }

  function toggleAllFandoms() {
      const allChecked = Object.values(allFandoms).every(val => val);
      const checkboxes = elements.fandomList.querySelectorAll('input[type="checkbox"]');
      checkboxes.forEach(cb => {
          cb.checked = !allChecked;
          allFandoms[cb.dataset.fandom] = !allChecked;
      });
      performSearch();
  }
  
  function handleGridClick(event) {
      const card = event.target.closest('.char-card');
      if (!card) return;
      const hash = card.dataset.hash;

      if (event.target.classList.contains('ignore-btn')) {
          stateManager.toggleIgnored(hash);
      } else if (event.target.classList.contains('used-btn')) {
          stateManager.toggleUsed(hash);
      } else {
          // Click on card itself shows modal
          const char = allCharacters.find(c => c.hash === hash);
          elements.modalImage.src = `thumbnails/${char.thumbnail}`;
          elements.modalCaption.textContent = char.name;
          elements.modal.classList.add('show');
          return; // Prevent re-render if not necessary
      }
      // Re-render only the affected card for performance
      const char = allCharacters.find(c => c.hash === hash);
      const isIgnored = stateManager.isIgnored(char.hash);
      const isUsed = stateManager.isUsed(char.hash);

      card.classList.toggle('is-ignored', isIgnored);
      card.classList.toggle('is-used', isUsed);
      card.querySelector('.ignore-btn').classList.toggle('active', isIgnored);
      card.querySelector('.used-btn').classList.toggle('active', isUsed);

      // If filters are active, a full re-render might be needed to hide/show the card
      performSearch();
  }

  // --- Start the app ---
  initialize();
});