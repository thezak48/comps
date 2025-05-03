const { imageUrls, totalColumns, totalRows, imageNames, imageSizes } = compareData;
let absoluteIndex = 0;
const currentImage = document.getElementById('currentImage');
const currentImageInfoSpan = document.getElementById('currentImageInfo');
const currentRowSpan = document.getElementById('currentRow');
const currentColumnSpan = document.getElementById('currentColumn');
let currentRowIndex = 0;

// Safely get DOM elements with error handling
const toggleFitBtn = document.getElementById('toggleFit') || { addEventListener: () => {} };
const toggleBorderBtn = document.getElementById('toggleBorder') || { addEventListener: () => {} };

let isImageFit = true;
currentImage.classList.add('fit');
let showBorder = false;

// Initialize scroll behavior with proper overflow handling
const imageViewer = document.querySelector('.image-viewer');
imageViewer.style.overflow = 'auto';

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
}

function updateNavigation() {
    // Ensure index is within bounds
    absoluteIndex = Math.max(0, Math.min(absoluteIndex, imageUrls.length - 1));
    const { column, row } = calculatePosition(absoluteIndex);
    currentRowSpan.textContent = row + 1;
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

toggleFitBtn.addEventListener('click', () => {
    isImageFit = !isImageFit;
    currentImage.classList.toggle('fit', isImageFit);
    
    // Always keep overflow auto to prevent cutoff
    imageViewer.style.overflow = 'auto';
    
    // Reset scroll position when switching to fit mode
    if (isImageFit) {
        imageViewer.scrollTo(0, 0);
        currentImage.style.cursor = 'pointer';
    } else {
        currentImage.style.cursor = 'move';
    }
    toggleFitBtn.textContent = isImageFit ? 'Original Size' : 'Fit to Screen';
});

toggleBorderBtn.addEventListener('click', () => {
    showBorder = !showBorder;
    currentImage.style.border = showBorder ? '1px solid #ccc' : 'none';
    toggleBorderBtn.classList.toggle('active');
});

// Initialize display
updateDisplay();
updateNavigation();
