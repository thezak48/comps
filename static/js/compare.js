const { imageUrls, totalColumns, totalRows, imageNames, imageSizes } = compareData;
let absoluteIndex = 0;

// Get both desktop and mobile elements
const currentImage = document.getElementById('currentImage');
const currentImageInfoSpan = document.getElementById('currentImageInfo');
const currentRowSpan = document.getElementById('currentRow');
const currentColumnSpan = document.getElementById('currentColumn');
const mobileCurrentImageInfoSpan = document.getElementById('mobileCurrentImageInfo') || { textContent: '' };
const mobileCurrentRowSpan = document.getElementById('mobileCurrentRow');
const mobileCurrentColumnSpan = document.getElementById('mobileCurrentColumn');
const mobileTotalRowsSpan = document.getElementById('mobileTotalRows');
const copyBBCodeBtn = document.querySelector('#copyBBCodeBtn')
const toggleFitSwitch = document.querySelector('#toggleFit') || { addEventListener: () => {}};
const toggleBorderSwitch = document.getElementById('toggleBorder') || { addEventListener: () => {} };
const imageRenderingSelect = document.getElementById('imageRendering') || { addEventListener: () => {} };

// Initialize state from cookies
toggleFitSwitch.checked = false;
toggleBorderSwitch.checked = false;

// Check for saved rendering preference
const savedRendering = getCookie('imageRendering') || 'auto';
imageRenderingSelect.value = savedRendering;

function setCookie(name, value, days) {
    const date = new Date();
    date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
    const expires = "expires=" + date.toUTCString();
    document.cookie = name + "=" + value + ";" + expires + ";path=/";
}

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

const mobileToggleFitSwitch = document.querySelector('#mobileToggleFit') || { addEventListener: () => {}};
const mobileToggleBorderSwitch = document.getElementById('mobileToggleBorder') || { addEventListener: () => {} };
mobileToggleFitSwitch.checked = toggleFitSwitch.checked;

const imageViewer = document.querySelector('.image-viewer');

function isInSameColumn(currentIndex, newIndex) {
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

    if (direction > 0 && newColumn >= totalColumns) {
        absoluteIndex = currentRow * totalColumns;
    }
    else if (direction < 0 && newColumn < 0) {
        absoluteIndex = (currentRow * totalColumns) + (totalColumns - 1);
    }
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
            const prevRow = absoluteIndex - totalColumns;
            if (prevRow >= 0) {
                absoluteIndex = prevRow;
                updateDisplay();
                updateNavigation();
            }
           break;
        case 'ArrowDown':
            e.preventDefault();
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

    if (mobileCurrentImageInfoSpan) {
        mobileCurrentImageInfoSpan.textContent = `${currentImageName} [${currentImageSize}]`;
    }
    
    if ('ontouchstart' in window) {
        setupTouchNavigation();
    }
}

function updateNavigation() {
    absoluteIndex = Math.max(0, Math.min(absoluteIndex, imageUrls.length - 1));
    const { column, row } = calculatePosition(absoluteIndex);
    currentRowSpan.textContent = row + 1;
    
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

document.querySelectorAll('[data-row]').forEach(item => {
    item.addEventListener('click', (e) => {
        e.preventDefault();
        const newRow = parseInt(e.target.dataset.row, 10);
        const currentCol = absoluteIndex % totalColumns;
        
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
        
        const newIndex = (currentRow * totalColumns) + newCol;
        if (newIndex >= imageUrls.length) {
            return;
        }
        absoluteIndex = (currentRow * totalColumns) + newCol;
        updateDisplay();
        updateNavigation();
    });
});

// Add mobile dropdown handlers
document.querySelectorAll('#mobileRowDropdown .dropdown-item').forEach(item => {
    item.addEventListener('click', (e) => {
        e.preventDefault();
        const newRow = parseInt(e.target.dataset.row, 10);
        const currentCol = absoluteIndex % totalColumns;
        absoluteIndex = (newRow * totalColumns) + currentCol;
        updateDisplay();
        updateNavigation();
    });
});

document.querySelectorAll('#mobileColumnDropdown .dropdown-item').forEach(item => {
    item.addEventListener('click', (e) => {
        e.preventDefault();
        const newCol = parseInt(e.target.dataset.column, 10);
        const currentRow = Math.floor(absoluteIndex / totalColumns);
        absoluteIndex = (currentRow * totalColumns) + newCol;
        updateDisplay();
        updateNavigation();
    });
});

currentImage.addEventListener('click', () => {
    const currentPos = calculatePosition(absoluteIndex);
    const nextIndex = absoluteIndex + 1;
    
    if (Math.floor(nextIndex / totalColumns) === currentPos.row) {
        absoluteIndex = nextIndex;
    } else {
        absoluteIndex = currentPos.row * totalColumns;
    }
    
    updateDisplay();
    updateNavigation();
});

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
        
        if (Math.abs(xDiff) > Math.abs(yDiff)) {
            if (xDiff > 50) {
                navigateToColumn(1);
            } else if (xDiff < -50) {
                navigateToColumn(-1);
            }
        } else {
            if (yDiff > 50) {
                const prevRow = absoluteIndex - totalColumns;
                if (prevRow >= 0) {
                    absoluteIndex = prevRow;
                    updateDisplay();
                    updateNavigation();
                }
            } else if (yDiff < -50) {
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
    
    currentImage.classList.toggle('fit', isImageFit);
    imageViewer.classList.toggle('fit-mode', isImageFit);
    
    const viewMode = isImageFit ? 'fit' : 'original';
    setCookie('imageViewMode', viewMode, 30);

    if (isImageFit) {
        imageViewer.scrollTo(0, 0);
        currentImage.style.cursor = 'pointer';
    } else {
        imageViewer.scrollTo(0, 0);
        
        let imageContainer = document.querySelector('.image-container');
        if (!imageContainer) {
            imageContainer = document.createElement('div');
            imageContainer.className = 'image-container';
            
            const parent = currentImage.parentNode;
            parent.appendChild(imageContainer);
            imageContainer.appendChild(currentImage);
        }
        
        setTimeout(() => {
            imageViewer.scrollTo(0, 0);
        }, 50);
        
        currentImage.style.cursor = 'move';
    }
});

mobileToggleFitSwitch.addEventListener('change', (event) => {
    const isImageFit = !event.target.checked;
    
    currentImage.classList.toggle('fit', isImageFit);
    imageViewer.classList.toggle('fit-mode', isImageFit);
    
    toggleFitSwitch.checked = !isImageFit;
    
    const viewMode = isImageFit ? 'fit' : 'original';
    setCookie('imageViewMode', viewMode, 30);

    if (isImageFit) {
        imageViewer.scrollTo(0, 0);
        currentImage.style.cursor = 'pointer';
    } else {
        imageViewer.scrollTo(0, 0);
        
        let imageContainer = document.querySelector('.image-container');
        if (!imageContainer) {
            imageContainer = document.createElement('div');
            imageContainer.className = 'image-container';
            
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
    
    if (mobileToggleBorderSwitch) {
        mobileToggleBorderSwitch.checked = showBorder;
    }
});

mobileToggleBorderSwitch.addEventListener('change', (event) => {
    const showBorder = event.target.checked;
    currentImage.style.border = showBorder ? '1px solid #ccc' : 'none';
    
    toggleBorderSwitch.checked = showBorder;
});

// Image rendering controls
imageRenderingSelect.addEventListener('change', (event) => {
    const renderingMode = event.target.value;
    currentImage.style.imageRendering = renderingMode;
    
    const mobileSelect = document.getElementById('mobileImageRendering');
    if (mobileSelect) {
        mobileSelect.value = renderingMode;
    }
    
    setCookie('imageRendering', renderingMode, 30);
});

document.getElementById('mobileImageRendering')?.addEventListener('change', (event) => {
    imageRenderingSelect.value = event.target.value;
    imageRenderingSelect.dispatchEvent(new Event('change'));
});

document.getElementById('shareBBCodeBtn').addEventListener('click', function() {
    showBBCodeModal();
});

function showBBCodeModal() {
    generateBBCode();
    const bbcodeModal = new bootstrap.Modal(document.getElementById('bbcodeModal'));
    bbcodeModal.show();
}

document.getElementById('mobileShareBBCodeBtn')?.addEventListener('click', function() {
    showBBCodeModal();
});

function generateBBCode() {
    const columnNames = [];
    for (let col = 0; col < totalColumns; col++) {
        const index = col;
        const name = imageNames[index] || `Column ${col+1}`;
        const simpleName = name.split('/').pop().split('\\').pop().split('.')[0];
        columnNames.push(simpleName);
    }
    
    let bbcode = `[comparison=${columnNames.join(', ')}]\n`;
    
    for (let row = 0; row < totalRows; row++) {
        for (let col = 0; col < totalColumns; col++) {
            const index = (row * totalColumns) + col;
            
            if (index < imageUrls.length) {
                bbcode += `${window.location.origin}/uploads/${imageUrls[index]}\n`;
            }
        }
        
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

updateDisplay();
updateNavigation();

document.addEventListener('DOMContentLoaded', () => {
    const savedViewMode = getCookie('imageViewMode');
    if (savedViewMode === 'original') {
        currentImage.classList.remove('fit');
        imageViewer.classList.remove('fit-mode');
    }
    
    currentImage.style.imageRendering = savedRendering;
});
