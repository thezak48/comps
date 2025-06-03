const { imageUrls, totalColumns, totalRows, imageNames, imageSizes } = compareData;
let absoluteIndex = 0;
const currentImage = document.getElementById('currentImage');
const navbar = document.querySelector('.navbar');
const currentImageInfoSpan = document.getElementById('currentImageInfo');
const currentRowSpan = document.getElementById('currentRow');
const currentColumnSpan = document.getElementById('currentColumn');
const mobileCurrentImageInfoSpan = document.getElementById('mobileCurrentImageInfo');
const mobileCurrentRowSpan = document.getElementById('mobileCurrentRow');
const mobileCurrentColumnSpan = document.getElementById('mobileCurrentColumn');
const mobileTotalRowsSpan = document.getElementById('mobileTotalRows');
const copyBBCodeBtn = document.querySelector('#copyBBCodeBtn')

/**
 * Sets a cookie with the given name, value, and expiration days
 * @param {string} name - The name of the cookie
 * @param {string} value - The value to store in the cookie
 * @param {number} days - Number of days until the cookie expires
 */
function setCookie(name, value, days) {
    const date = new Date();
    date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
    const expires = "expires=" + date.toUTCString();
    document.cookie = name + "=" + value + ";" + expires + ";path=/";
}

/**
 * Gets a cookie value by name
 * @param {string} name - The name of the cookie to retrieve
 * @returns {string} The cookie value or empty string if not found
 */
function getCookie(name) {
    const cookieName = name + "=";
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
        let cookie = cookies[i].trim();
        if (cookie.indexOf(cookieName) === 0) {
            return cookie.substring(cookieName.length, cookie.length);
        }
    }
    return "";
}

let currentRowIndex = 0;
let navbarVisible = true;

// Safely get DOM elements with error handling
const toggleFitSwitch = document.querySelector('#toggleFit') || { addEventListener: () => {}};
const toggleBorderSwitch = document.getElementById('toggleBorder') || { addEventListener: () => {} };

toggleFitSwitch.checked = false;
toggleBorderSwitch.checked = false;

// Check for saved view preference in cookie
const savedViewMode = getCookie('imageViewMode');
if (savedViewMode === 'original') {
    toggleFitSwitch.checked = true;
    // We'll apply this setting after the image is loaded
}

// Mobile controls
const mobileToggleFitSwitch = document.querySelector('#mobileToggleFit') || { addEventListener: () => {}};
const mobileToggleBorderSwitch = document.getElementById('mobileToggleBorder') || { addEventListener: () => {} };
mobileToggleFitSwitch.checked = toggleFitSwitch.checked; // Sync with desktop toggle

// Initialize scroll behavior with proper overflow handling
const imageViewer = document.querySelector('.image-viewer');

/**
 * Toggle the visibility of the navbar
 * @param {boolean} show - Whether to show (true) or hide (false) the navbar
 */
function toggleNavbarVisibility(show) {
    if (show === navbarVisible) return; // No change needed
    
    navbarVisible = show;
    
    if (show) {
        navbar.classList.remove('navbar-hidden');
        document.body.classList.remove('navbar-is-hidden');
    } else {
        navbar.classList.add('navbar-hidden');
        document.body.classList.add('navbar-is-hidden');
    }
}

// Add mouse movement detection to show navbar when mouse is near the top
document.addEventListener('mousemove', function(e) {
    // Only apply this in original size mode (when not fit)
    if (!currentImage.classList.contains('fit')) {
        const mouseY = e.clientY;
        
        // Show navbar when mouse is near the top of the screen (within 100px)
        if (mouseY < 100) {
            toggleNavbarVisibility(true);
            
            // Hide navbar again after 3 seconds of inactivity near the top
            clearTimeout(window.navbarTimeout);
            window.navbarTimeout = setTimeout(() => {
                // Only hide if we're still in original size mode
                if (!currentImage.classList.contains('fit')) {
                    toggleNavbarVisibility(false);
                }
            }, 3000);
        }
    }
});

function isInSameColumn(currentIndex, newIndex) {
    // Check if indices are valid
    if (newIndex < 0 || newIndex >= imageUrls.length) {
        return false;
    }

    const { column: currentColumn, row: currentRow } = calculatePosition(currentIndex);
    const { column: newColumn, row: newRow } = calculatePosition(newIndex);
    
    return newColumn >= 0 && newColumn < totalColumns && 
          newRow >= 0 && 
          newRow < totalRows;
}

function navigateToColumn(direction) {
    const currentPos = calculatePosition(absoluteIndex);
    const newColumn = currentPos.column + direction;
    const currentRow = currentPos.row;

    // Handle wrapping for right arrow
    if (direction > 0 && newColumn >= totalColumns) {
        // Wrap to first column in same row
        absoluteIndex = currentRow * totalColumns;
    }
    // Handle wrapping for left arrow
    else if (direction < 0 && newColumn < 0) {
        // Wrap to last column in same row
        absoluteIndex = (currentRow * totalColumns) + (totalColumns - 1);
    }
    // Normal column navigation within bounds
    else if (newColumn >= 0 && newColumn < totalColumns) {
        absoluteIndex = (currentRow * totalColumns) + newColumn;
    }
    
    updateDisplay();
    updateNavigation();
}

function calculatePosition(index) {
    return {
        column: index % totalColumns,
        row: Math.floor(index / totalColumns)
    };
}

document.addEventListener('keydown', (e) => {
    switch(e.key) {
        case 'ArrowLeft':
            e.preventDefault();
            navigateToColumn(-1);
           break;
        case 'ArrowRight':
            e.preventDefault();
            navigateToColumn(1);
           break;
        case 'ArrowUp':
            e.preventDefault();
            // Navigate up one row
            const prevRow = absoluteIndex - totalColumns;
            if (prevRow >= 0) {
                absoluteIndex = prevRow;
                updateDisplay();
                updateNavigation();
            }
           break;
        case 'ArrowDown':
            e.preventDefault();
            // Navigate down one row
            const nextRow = absoluteIndex + totalColumns;
            if (nextRow < imageUrls.length) {
                absoluteIndex = nextRow;
                updateDisplay();
                updateNavigation();
            }
           break;
    }
});

function navigate(direction) {
    const newIndex = absoluteIndex + direction;
    if (newIndex >= 0 && newIndex < imageUrls.length) {
        absoluteIndex = newIndex;
        updateDisplay();
        updateNavigation();
    }
}

function updateDisplay() {
    currentImage.src = `/uploads/${imageUrls[absoluteIndex]}`;
    currentImage.style.cursor = 'pointer';
    const currentImageName = imageNames[absoluteIndex] || 'Unknown';
    const currentImageSize = imageSizes[absoluteIndex] || '';
    currentImageInfoSpan.textContent = `${currentImageName} [${currentImageSize}]`;
    document.title = `Compare - ${currentImageName}`;
    
    // If we're in original size mode, hide the navbar initially
    if (!currentImage.classList.contains('fit')) {
        toggleNavbarVisibility(false);
    }
    
    // Update mobile info displays if they exist
    if (mobileCurrentImageInfoSpan) {
        mobileCurrentImageInfoSpan.textContent = `${currentImageName} [${currentImageSize}]`;
    }
    
    // Add touch swipe detection for mobile
    if ('ontouchstart' in window) {
        setupTouchNavigation();
    }
}

function updateNavigation() {
    // Ensure index is within bounds
    absoluteIndex = Math.max(0, Math.min(absoluteIndex, imageUrls.length - 1));
    const { column, row } = calculatePosition(absoluteIndex);
    currentRowSpan.textContent = row + 1;
    
    // Update mobile navigation elements if they exist
    if (mobileCurrentRowSpan) {
        mobileCurrentRowSpan.textContent = row + 1;
        mobileCurrentColumnSpan.textContent = column + 1;
    }
    currentColumnSpan.textContent = column + 1;
    updateDots();
}

function updateDots() {
    const { column, row } = calculatePosition(absoluteIndex);
    document.querySelectorAll('.dot').forEach(dot => {
        const dotColumn = parseInt(dot.dataset.column, 10);
        const dotRow = parseInt(dot.dataset.row, 10);
        dot.classList.toggle('active', dotColumn === column && dotRow === row);
    });
    
    document.querySelectorAll('.column-indicator').forEach(indicator => 
        indicator.classList.toggle('active', parseInt(indicator.dataset.column, 10) === column));
}

// Add dropdown navigation handlers
document.querySelectorAll('[data-row]').forEach(item => {
    item.addEventListener('click', (e) => {
        e.preventDefault();
        const newRow = parseInt(e.target.dataset.row, 10);
        const currentCol = absoluteIndex % totalColumns;
        
        // Validate new position
        const newIndex = (newRow * totalColumns) + currentCol;
        if (newIndex >= imageUrls.length) {
            return;
        }
        absoluteIndex = (newRow * totalColumns) + currentCol;
        updateDisplay();
        updateNavigation();
    });
});

document.querySelectorAll('[data-column]').forEach(item => {
    item.addEventListener('click', (e) => {
        e.preventDefault();
        const newCol = parseInt(e.target.dataset.column, 10);
        const currentRow = Math.floor(absoluteIndex / totalColumns);
        
        // Validate new position
        const newIndex = (currentRow * totalColumns) + newCol;
        if (newIndex >= imageUrls.length) {
            return;
        }
        absoluteIndex = (currentRow * totalColumns) + newCol;
        updateDisplay();
        updateNavigation();
    });
});

// Add click handler for image navigation
currentImage.addEventListener('click', () => {
    const currentPos = calculatePosition(absoluteIndex);
    const nextIndex = absoluteIndex + 1;
    
    // If next index is in the same row, move to it
    if (Math.floor(nextIndex / totalColumns) === currentPos.row) {
        absoluteIndex = nextIndex;
    } else {
        // If at end of row, go back to first image in row
        absoluteIndex = currentPos.row * totalColumns;
    }
    
    // Update display and navigation
    updateDisplay();
    updateNavigation();
});

// Setup touch navigation for mobile devices
function setupTouchNavigation() {
    let touchStartX = 0;
    let touchEndX = 0;
    let touchStartY = 0;
    let touchEndY = 0;
    
    currentImage.addEventListener('touchstart', function(e) {
        touchStartX = e.changedTouches[0].screenX;
        touchStartY = e.changedTouches[0].screenY;
    }, false);
    
    currentImage.addEventListener('touchend', function(e) {
        touchEndX = e.changedTouches[0].screenX;
        touchEndY = e.changedTouches[0].screenY;
        handleSwipe();
    }, false);
    
    function handleSwipe() {
        const xDiff = touchStartX - touchEndX;
        const yDiff = touchStartY - touchEndY;
        
        // Determine if the swipe was primarily horizontal or vertical
        if (Math.abs(xDiff) > Math.abs(yDiff)) {
            if (xDiff > 50) {
                // Swipe left - go to next column
                navigateToColumn(1);
            } else if (xDiff < -50) {
                // Swipe right - go to previous column
                navigateToColumn(-1);
            }
        } else {
            if (yDiff > 50) {
                // Swipe up - go to previous row
                const prevRow = absoluteIndex - totalColumns;
                if (prevRow >= 0) {
                    absoluteIndex = prevRow;
                    updateDisplay();
                    updateNavigation();
                }
            } else if (yDiff < -50) {
                // Swipe down - go to next row
                const nextRow = absoluteIndex + totalColumns;
                if (nextRow < imageUrls.length) {
                    absoluteIndex = nextRow;
                    updateDisplay();
                    updateNavigation();
                }
            }
        }
    }
}

toggleFitSwitch.addEventListener('change', (event) => {
    const isImageFit = !event.target.checked;
    
    // Toggle fit class on image
    currentImage.classList.toggle('fit', isImageFit);
    
    // Toggle fit-mode class on image viewer
    imageViewer.classList.toggle('fit-mode', isImageFit);
    
    // Handle navbar visibility based on fit mode
    if (isImageFit) {
        // Always show navbar in fit mode
        toggleNavbarVisibility(true);
    } else {
        // Initially hide navbar in original size mode
        toggleNavbarVisibility(false);
    }
    
    // Save preference to cookie (30 day expiration)
    const viewMode = isImageFit ? 'fit' : 'original';
    setCookie('imageViewMode', viewMode, 30);

    // Handle cursor and scroll behavior
    if (isImageFit) {
        // Reset scroll position when switching to fit mode
        imageViewer.scrollTo(0, 0);
        currentImage.style.cursor = 'pointer';
    } else {
        // First reset scroll position
        imageViewer.scrollTo(0, 0);
        
        // Create a wrapper if it doesn't exist
        let imageContainer = document.querySelector('.image-container');
        if (!imageContainer) {
            imageContainer = document.createElement('div');
            imageContainer.className = 'image-container';
            
            // Move the image into the container
            const parent = currentImage.parentNode;
            parent.appendChild(imageContainer);
            imageContainer.appendChild(currentImage);
        }
        
        // Use a timeout to ensure the DOM has updated
        setTimeout(() => {
            // Ensure we're at the top of the image
            imageViewer.scrollTo(0, 0);
        }, 50);
        
        currentImage.style.cursor = 'move';
    }
});

// Mobile toggle fit switch
mobileToggleFitSwitch.addEventListener('change', (event) => {
    const isImageFit = !event.target.checked;
    
    // Toggle fit class on image
    currentImage.classList.toggle('fit', isImageFit);
    
    // Toggle fit-mode class on image viewer
    imageViewer.classList.toggle('fit-mode', isImageFit);
    
    // Sync with desktop toggle
    toggleFitSwitch.checked = !isImageFit;
    
    // Handle navbar visibility based on fit mode
    if (isImageFit) {
        // Always show navbar in fit mode
        toggleNavbarVisibility(true);
    } else {
        // Initially hide navbar in original size mode
        toggleNavbarVisibility(false);
    }
    
    // Save preference to cookie (30 day expiration)
    const viewMode = isImageFit ? 'fit' : 'original';
    setCookie('imageViewMode', viewMode, 30);

    // Handle cursor and scroll behavior
    if (isImageFit) {
        // Reset scroll position when switching to fit mode
        imageViewer.scrollTo(0, 0);
        currentImage.style.cursor = 'pointer';
    } else {
        // First reset scroll position
        imageViewer.scrollTo(0, 0);
        
        // Create a wrapper if it doesn't exist
        let imageContainer = document.querySelector('.image-container');
        if (!imageContainer) {
            imageContainer = document.createElement('div');
            imageContainer.className = 'image-container';
            
            // Move the image into the container
            const parent = currentImage.parentNode;
            parent.appendChild(imageContainer);
            imageContainer.appendChild(currentImage);
        }
        
        currentImage.style.cursor = 'move';
    }
});

toggleBorderSwitch.addEventListener('change', (event) => {
    const showBorder = event.target.checked;
    currentImage.style.border = showBorder ? '1px solid #ccc' : 'none';
    
    // Sync with mobile toggle
    if (mobileToggleBorderSwitch) {
        mobileToggleBorderSwitch.checked = showBorder;
    }
});

// Mobile toggle border switch
mobileToggleBorderSwitch.addEventListener('change', (event) => {
    const showBorder = event.target.checked;
    currentImage.style.border = showBorder ? '1px solid #ccc' : 'none';
    
    // Sync with desktop toggle
    toggleBorderSwitch.checked = showBorder;
});

// BBCode Share functionality
document.getElementById('shareBBCodeBtn').addEventListener('click', function() {
    showBBCodeModal();
});

function showBBCodeModal() {
    generateBBCode();
    const bbcodeModal = new bootstrap.Modal(document.getElementById('bbcodeModal'));
    bbcodeModal.show();
}

// Mobile BBCode Share functionality
document.getElementById('mobileShareBBCodeBtn')?.addEventListener('click', function() {
    showBBCodeModal();
});

function generateBBCode() {
    // Get all unique column names (custom names)
    const columnNames = [];
    for (let col = 0; col < totalColumns; col++) {
        // Get the image name from the first row of each column
        const index = col;
        const name = imageNames[index] || `Column ${col+1}`;
        // Extract just the filename without extension and path
        const simpleName = name.split('/').pop().split('\\').pop().split('.')[0];
        columnNames.push(simpleName);
    }
    
    // Generate the BBCode
    let bbcode = `[comparison=${columnNames.join(', ')}]\n`;
    
    // Add all image URLs for all rows
    for (let row = 0; row < totalRows; row++) {
        // Add all columns in this row
        for (let col = 0; col < totalColumns; col++) {
            // Calculate the index in the flat array
            const index = (row * totalColumns) + col;
            
            // Make sure the index is valid
            if (index < imageUrls.length) {
                bbcode += `${window.location.origin}/uploads/${imageUrls[index]}\n`;
            }
        }
        
        // Add a blank line between rows for readability (except after the last row)
        if (row < totalRows - 1) {
            bbcode += '\n';
        }
    }
    
    bbcode += '[/comparison]';
    document.getElementById('bbcodeText').value = bbcode;
}

copyBBCodeBtn.addEventListener('click', async () => {
    const bbcode = document.querySelector('#bbcodeText').value;
    try {
        await navigator.clipboard.writeText(bbcode);
        copyBBCodeBtn.innerHTML = '<i class="fa fa-check"></i> Copied to Clipboard';
        copyBBCodeBtn.classList.replace('btn-primary', 'btn-success');
    }
    catch (e) {
        console.error(e);
        copyBBCodeBtn.innerHTML = '<i class="fa fa-xmark"></i> Failed to Copy to Clipboard';
        copyBBCodeBtn.classList.replace('btn-primary', 'btn-danger');
    }
})

// Initialize display
updateDisplay();
updateNavigation();

// Apply saved view mode preference after initialization
document.addEventListener('DOMContentLoaded', () => {
    const savedViewMode = getCookie('imageViewMode');
    if (savedViewMode === 'original') {
        // Apply original size mode
        currentImage.classList.remove('fit');
        imageViewer.classList.remove('fit-mode');
        toggleFitSwitch.checked = true;
        mobileToggleFitSwitch.checked = true;
        currentImage.style.cursor = 'move';
    }
});
