// Toast notification system
const toastContainer = document.createElement('div');
toastContainer.className = 'toast-container';
const toastTypes = ['error', 'success', 'warning', 'info']; // Add 'info' type for notifications
console.log('Creating toast container:', toastContainer);
document.body.appendChild(toastContainer);

/**
 * Show a toast notification
 * @param {string} message - The message to display
 * @param {string} type - The type of notification: 'error', 'success', 'warning', or 'info'
 * @param {number} duration - How long to show the notification in ms (default: 5000ms)
 */
function showToast(message, type = 'error', duration = 5000) {
    console.log('showToast called with message:', message, 'type:', type);
    // Create toast element
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    // Add icon based on type
    let icon = '';
    switch(type) {
        case 'error': icon = '❌'; break;
        case 'success': icon = '✅'; break;
        case 'warning': icon = '⚠️'; break;
        case 'info': icon = 'ℹ️'; break;
        default: icon = 'ℹ️';
    }
    
    // Create toast content
    toast.innerHTML = `
<div class="toast-content">
    <span class="toast-icon">${icon}</span>
    <span class="toast-message">${message}</span>
</div>
<span class="toast-close">×</span>
`;
    console.log('Toast HTML:', toast.innerHTML);
    
    // Add to container
    toastContainer.appendChild(toast);
    
    console.log('Toast added to container:', toast);
    // Add close button functionality
    const closeBtn = toast.querySelector('.toast-close');
    closeBtn.addEventListener('click', () => {
        toast.style.animation = 'toast-out 0.3s forwards';
        setTimeout(() => {
            toastContainer.removeChild(toast);
        }, 300);
    });
    
    // Auto-remove after duration
    setTimeout(() => {
        if (toast.parentNode === toastContainer) {
            toast.style.animation = 'toast-out 0.3s forwards';
            setTimeout(() => {
                if (toast.parentNode === toastContainer) {
                    toastContainer.removeChild(toast);
                }
            }, 300);
        }
    }, duration);
}

const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const preview = document.getElementById('preview');
const showNameToggle = document.getElementById('show-name-toggle');
const expirationToggle = document.getElementById('expiration-toggle');
const expirationToggleLabel = document.querySelector('label[for="expiration-toggle"]');
const tagsToggle = document.getElementById('tags-toggle');
const comparisonNameInput = document.getElementById('comparison-name');
const showNameInput = document.getElementById('show-name');
const tagsInput = document.getElementById('tags');
let groupedFiles = new Map(); // Maps column prefixes to files
let selectedFiles = new Set();
let columnPrefixes = [];
let columnCount = 2; // Initialize with minimum columns (2 empty columns by default)
let rowCount = 1;    // Initialize with one row
let maxColumns = 10; // Maximum allowed columns
let maxRows = 20;    // Maximum allowed rows
let columnNamePrefix = 'column'; // New dynamic column naming
let baseColumns = 0; // Track columns from uploaded files
let addedColumns = 0; // Track manually added columns
let columnIndexMap = new Map(); // Track column indices
let detectedColumns = 2; // Track actual columns from uploaded files
let minColumns = 2; // Define minimum required columns
let columnTracker = new Map(); // Track column assignments
let uploadInProgress = false;
// Variables for drag and drop column reordering
let dragSrcColumn = null;
let draggedColumnIndex = -1;
let isDragging = false;

// Add this new structure to organize files by row and column
let fileMatrix = []; // 2D array to store files by [row][column]

console.log('Upload.js initialized');

// Toggle visibility of show name field
showNameToggle.addEventListener('change', function() {
    const showNameContainer = document.getElementById('show-name-container');
    showNameContainer.style.display = this.checked ? 'block' : 'none';
    if (!this.checked) {
        showNameInput.value = '';
    }
});

// Toggle visibility of expiration settings
expirationToggle.addEventListener('change', function() {
    const expirationContainer = document.getElementById('expiration-container');
    expirationContainer.style.display = this.checked ? 'block' : 'none';
    if (!this.checked) {
        // Reset to defaults when unchecked
        document.getElementById('expiration-last-access').checked = true;
        document.getElementById('expiration-days').value = '7';
    }
});

// Toggle visibility of tags field
tagsToggle.addEventListener('change', function() {
    const tagsContainer = document.getElementById('tags-container');
    tagsContainer.style.display = this.checked ? 'block' : 'none';
    if (!this.checked) {
        tagsInput.value = '';
    }
});

dropZone.addEventListener('click', () => fileInput.click());

dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropZone.classList.add('dragover');
});

dropZone.addEventListener('dragenter', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
});

dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('dragover');
});

dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropZone.classList.remove('dragover');
    const droppedFiles = Array.from(e.dataTransfer.files);
    handleFiles(droppedFiles);
});

fileInput.addEventListener('change', (e) => {
    handleFiles(e.target.files);
});

// Add horizontal scroll handling
preview.addEventListener('wheel', (e) => {
    if (e.deltaY !== 0 && e.shiftKey) {
        e.preventDefault();
        preview.scrollLeft += e.deltaY;
    }
});

function handleFiles(files) {
    if (!files || files.length === 0) return;
    preview.innerHTML = '';
    preview.style.width = '100%';
    const uploadButton = document.getElementById('uploadButton');
    try {
        groupFiles(Array.from(files));
        uploadButton.style.display = 'block';
    } catch (error) {
        showError(error.message);
        uploadButton.style.display = 'none';
    }
}

function groupFiles(files) {
    groupedFiles.clear();
    selectedFiles.clear();
    fileMatrix = []; // Reset the file matrix
    
    // Initialize matrix with proper size
    fileMatrix = [];
    for (let r = 0; r < rowCount; r++) {
        fileMatrix[r] = [];
        for (let c = 0; c < columnCount; c++) {
            fileMatrix[r][c] = null;
        }
    }
    
    // Validate file count
    if (files.length > 30) {
        throw new Error('Maximum 30 files allowed');
    }

    // Remove any existing reordering instructions
    const existingInstructions = document.querySelector('.reordering-instructions');
    if (existingInstructions) {
        existingInstructions.remove();
    }

    // Parse filenames and check if they follow the pattern
    const filenameRegex = /^(.+?)(\d+)\.([^.]+)$/i;
    const fileGroups = new Map();
    let patternMatchCount = 0;

    files.forEach(file => {
        const match = file.name.match(filenameRegex);
        if (match) {
            patternMatchCount++;
            const [_, prefix, number, ext] = match;
            const columnPrefix = prefix.toLowerCase();
            const rowNumber = parseInt(number);

            if (!fileGroups.has(columnPrefix)) {
                fileGroups.set(columnPrefix, new Map());
            }
            fileGroups.get(columnPrefix).set(rowNumber, file);
        }
        selectedFiles.add(file);
    });

    // If all files match the pattern, use pattern grouping
    if (patternMatchCount === files.length) {
        // Get unique row numbers
        const rowNumbers = new Set();
        fileGroups.forEach((rowMap) => {
            rowMap.forEach((file, rowNum) => {
                rowNumbers.add(rowNum);
            });
        });
        
        // Update row count based on detected rows
        rowCount = Math.max(1, rowNumbers.size);
        
        // Initialize file matrix with proper size
        fileMatrix = [];
        for (let r = 0; r < rowCount; r++) {
            fileMatrix[r] = [];
            for (let c = 0; c < columnCount; c++) {
                fileMatrix[r][c] = null;
            }
        }
        
        // Validate column counts and consistency
        const columnSizes = Array.from(fileGroups.values()).map(group => group.size);
        columnPrefixes = Array.from(fileGroups.keys());
        detectedColumns = columnPrefixes.length;
        baseColumns = detectedColumns;
        columnCount = Math.max(minColumns, detectedColumns);

        // Place files in the matrix based on pattern
        fileGroups.forEach((rowMap, columnPrefix) => {
            const columnIndex = columnPrefixes.indexOf(columnPrefix);
            rowMap.forEach((file, rowNum) => {
                // Adjust row number to 0-indexed
                const rowIndex = rowNum - 1;
                if (rowIndex >= 0 && rowIndex < rowCount) {
                    // Ensure the row exists
                    if (!fileMatrix[rowIndex]) {
                        fileMatrix[rowIndex] = [];
                        for (let c = 0; c < columnCount; c++) {
                            fileMatrix[rowIndex][c] = null;
                        }
                    }
                    fileMatrix[rowIndex][columnIndex] = file;
                }
            });
        });
        
        // Store grouped files for backwards compatibility
        fileGroups.forEach((files, prefix) => {
            groupedFiles.set(prefix, Array.from(files.values()));
        });
    } else {
        // For arbitrary filenames, create columns based on file order
        columnCount = Math.min(Math.max(minColumns, files.length), maxColumns);
        baseColumns = 0;
        detectedColumns = columnCount;
        
        // Create column prefixes
        columnPrefixes = [];
        for (let i = 0; i < columnCount; i++) {
            columnPrefixes.push(`column${i+1}`);
            groupedFiles.set(`column${i+1}`, []);
        }
        
        // Initialize row count to 1 for arbitrary filenames
        rowCount = Math.ceil(files.length / columnCount);
        
        // Initialize file matrix with proper size
        fileMatrix = [];
        for (let r = 0; r < rowCount; r++) {
            fileMatrix[r] = [];
            for (let c = 0; c < columnCount; c++) {
                fileMatrix[r][c] = null;
            }
        }
        
        // Distribute files across rows and columns
        files.forEach((file, index) => {
            const rowIndex = Math.floor(index / columnCount);
            const columnIndex = index % columnCount;
            
            // Ensure we don't exceed matrix dimensions
            if (rowIndex < rowCount && columnIndex < columnCount) {
                fileMatrix[rowIndex][columnIndex] = file;
                
                // Also add to groupedFiles for backward compatibility
                const columnPrefix = columnPrefixes[columnIndex];
                if (!groupedFiles.has(columnPrefix)) {
                    groupedFiles.set(columnPrefix, []);
                }
                groupedFiles.get(columnPrefix).push(file);
            }
        });
        
        // Add a note about reordering for arbitrary filenames
        const instructionEl = document.createElement('div');
        instructionEl.className = 'reordering-instructions';
        instructionEl.innerHTML = `
            <div class="alert alert-info mt-2">
                <i class="fas fa-info-circle"></i> 
                Files have been arranged based on upload order. 
                <strong>Drag the column handles <i class="fas fa-grip-lines"></i> to reorder columns</strong> and 
                <strong>use the Add Row button to add new rows</strong> before uploading.
            </div>
        `;
        
        // Insert the instructions above the preview
        preview.parentNode.insertBefore(instructionEl, preview);
    }

    updatePreview();
}

function detectColumnCount(files) {
    const prefixSet = new Set();
    const filenameRegex = /^(.+?)(\d+)\.([^.]+)$/;
    
    files.forEach(file => {
        const match = file.name.match(filenameRegex);
        if (match) {
            prefixSet.add(match[1].toLowerCase());
        }
    });
    
    return Math.max(minColumns, prefixSet.size);
}

function updatePreview() {
    preview.innerHTML = '';
    
    // Create top-level column controls
    const columnControlsBar = document.createElement('div');
    columnControlsBar.className = 'column-controls-bar';
    
    // Add column headers with drag handles
    for (let colIndex = 0; colIndex < columnCount; colIndex++) {
        const columnHeader = document.createElement('div');
        columnHeader.className = 'column-header';
        columnHeader.dataset.columnIndex = colIndex;
        columnHeader.style.width = `calc(100% / ${columnCount})`;
        
        const dragHandle = document.createElement('div');
        dragHandle.className = 'drag-handle';
        dragHandle.innerHTML = '<i class="fas fa-grip-lines"></i>';
        dragHandle.title = 'Drag to reorder this column in all rows';
        dragHandle.draggable = true;
        
        const columnLabel = document.createElement('div');
        columnLabel.className = 'column-label';
        columnLabel.textContent = `Column ${colIndex+1}`;
        
        const removeButton = document.createElement('button');
        removeButton.className = 'btn btn-sm btn-danger';
        removeButton.innerHTML = '<i class="fas fa-times"></i>';
        removeButton.title = 'Remove this column from all rows';
        removeButton.onclick = () => removeColumn(colIndex);
        removeButton.disabled = columnCount <= minColumns;
        
        columnHeader.appendChild(dragHandle);
        columnHeader.appendChild(columnLabel);
        
        // Only add remove button if we have more than minimum columns
        if (columnCount > minColumns) {
            columnHeader.appendChild(removeButton);
        }
        
        columnControlsBar.appendChild(columnHeader);
    }
    
    preview.appendChild(columnControlsBar);
    
    // Create rows
    for (let rowIndex = 0; rowIndex < rowCount; rowIndex++) {
        const rowContainer = document.createElement('div');
        rowContainer.className = 'row-container';
        rowContainer.dataset.rowIndex = rowIndex;
        
        // Add row header with controls
        const rowControls = document.createElement('div');
        rowControls.className = 'row-controls';
        
        const rowLabel = document.createElement('div');
        rowLabel.className = 'row-label';
        rowLabel.textContent = `Row ${rowIndex + 1}`;
        
        const removeRowBtn = document.createElement('button');
        removeRowBtn.className = 'btn btn-sm btn-danger';
        removeRowBtn.innerHTML = '<i class="fas fa-trash"></i> Remove Row';
        removeRowBtn.onclick = () => removeRow(rowIndex);
        removeRowBtn.disabled = rowCount <= 1; // Disable if only one row
        
        rowControls.appendChild(rowLabel);
        rowControls.appendChild(removeRowBtn);
        rowContainer.appendChild(rowControls);
        
        // Create row content container
        const rowColumnsContainer = document.createElement('div');
        rowColumnsContainer.className = 'row-columns';
        
        // Add columns to this row
        for (let colIndex = 0; colIndex < columnCount; colIndex++) {
            const columnDiv = createColumnElement(rowIndex, colIndex);
            rowColumnsContainer.appendChild(columnDiv);
        }
        
        rowContainer.appendChild(rowColumnsContainer);
        preview.appendChild(rowContainer);
    }
    
    // Add drag-and-drop column reordering to the column headers
    enableColumnReordering();
}

// Helper function to create a column element
function createColumnElement(rowIndex, colIndex) {
    const columnPrefix = columnPrefixes[colIndex] || `column${colIndex+1}`;
    const columnDiv = document.createElement('div');
    columnDiv.className = 'comparison-column';
    columnDiv.id = `column-${rowIndex}-${colIndex}`; 
    columnDiv.dataset.rowIndex = rowIndex;
    columnDiv.dataset.columnIndex = colIndex;
    
    // Create a container for files in this column
    const filesDiv = document.createElement('div');
    filesDiv.dataset.rowIndex = rowIndex;
    filesDiv.dataset.columnIndex = colIndex;
    filesDiv.className = 'column-files';
    columnDiv.appendChild(filesDiv);

    // Create a drop zone for this specific cell
    const cellDropZone = document.createElement('div');
    cellDropZone.className = 'cell-drop-zone';
    cellDropZone.dataset.rowIndex = rowIndex;
    cellDropZone.dataset.columnIndex = colIndex;
    cellDropZone.innerHTML = `
        <div class="drop-instructions">
            Drop image(s) here or <button class="btn btn-sm btn-outline-secondary cell-upload-btn">Select file(s)</button>
        </div>
    `;
    filesDiv.appendChild(cellDropZone);

    // Add file input for this cell
    const cellFileInput = document.createElement('input');
    cellFileInput.type = 'file';
    cellFileInput.accept = 'image/*';
    cellFileInput.multiple = true; // Allow multiple file selection
    cellFileInput.className = 'cell-file-input';
    cellFileInput.style.display = 'none';
    filesDiv.appendChild(cellFileInput);

    // Handle click on the cell upload button
    const cellUploadBtn = cellDropZone.querySelector('.cell-upload-btn');
    cellUploadBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        cellFileInput.click(); // This will now allow multiple file selection
    });

    // Handle file selection for this specific cell
    cellFileInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files.length > 0) {
            handleMultipleFilesForColumn(Array.from(e.target.files), rowIndex, colIndex);
        }
    });
    
    // If we have a file in this position, display it
    if (fileMatrix && fileMatrix[rowIndex] && fileMatrix[rowIndex][colIndex]) {
        displayFilePreview(fileMatrix[rowIndex][colIndex], filesDiv);
    }

    // Add drag and drop event listeners for this cell
    setupCellDragAndDrop(cellDropZone);
    
    return columnDiv;
}

// Helper function to display a file preview
function displayFilePreview(file, container) {
    // Get row and column indices from container's data attributes
    const rowIndex = parseInt(container.dataset.rowIndex);
    const colIndex = parseInt(container.dataset.columnIndex);
    
    if (!file || isNaN(rowIndex) || isNaN(colIndex)) return;
    
    console.log(`Displaying preview for row ${rowIndex}, column ${colIndex}`);
    
    // Clear any existing content in the container
    container.innerHTML = '';
    
    // Create a drop zone for this cell (will be replaced with the file preview)
    const cellDropZone = document.createElement('div');
    cellDropZone.className = 'cell-drop-zone';
    container.appendChild(cellDropZone);
    
    const reader = new FileReader();
    reader.onload = (e) => {
        const fileDiv = document.createElement('div');
        fileDiv.className = 'file-preview';
        fileDiv.innerHTML = `
            <img src="${e.target.result}" style="max-height: 100px;">
            <div class="file-label">${file.name}</div>
            <div class="replace-overlay"><i class="fas fa-exchange-alt"></i> Replace</div>
            <button class="btn btn-sm btn-primary replace-file-btn" title="Replace this image"><i class="fas fa-exchange-alt"></i></button>
            <button class="btn btn-sm btn-secondary edit-name-btn" title="Edit image name"><i class="fas fa-edit"></i></button>
        `;
        container.appendChild(fileDiv);
        container.removeChild(cellDropZone); // Remove the drop zone now that we have a file preview
        
        // Add remove button
        const removeBtn = document.createElement('button');
        removeBtn.className = 'btn btn-sm btn-danger remove-file-btn';
        removeBtn.innerHTML = '<i class="fas fa-times"></i>';
        removeBtn.title = 'Remove this file';
        fileDiv.appendChild(removeBtn);
        
        // Add event listener for replace button
        const replaceBtn = fileDiv.querySelector('.replace-file-btn');
        replaceBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const rowIndex = parseInt(container.closest('.comparison-column').dataset.rowIndex);
            const colIndex = parseInt(container.closest('.comparison-column').dataset.columnIndex);
            // Create and trigger a file input for replacement
            triggerFileInputForReplacement(rowIndex, colIndex);
        });
        
        // Add event listener for edit name button
        const editNameBtn = fileDiv.querySelector('.edit-name-btn');
        editNameBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const rowIndex = parseInt(container.closest('.comparison-column').dataset.rowIndex);
            const colIndex = parseInt(container.closest('.comparison-column').dataset.columnIndex);
            const fileLabel = fileDiv.querySelector('.file-label');
            const currentName = fileLabel.textContent;
            
            // Replace label with input field
            fileLabel.innerHTML = `
                <input type="text" class="name-edit-input" value="${currentName}">
                <div class="edit-actions">
                    <button class="btn btn-sm btn-success save-name-btn"><i class="fas fa-check"></i></button>
                    <button class="btn btn-sm btn-danger cancel-name-btn"><i class="fas fa-times"></i></button>
                </div>
            `;
            
            // Focus the input field
            const input = fileLabel.querySelector('.name-edit-input');
            input.focus();
            input.select();
            
            setupNameEditHandlers(fileLabel, rowIndex, colIndex, currentName);
        });
        
        // Handle remove button click
        removeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const rowIndex = parseInt(container.closest('.comparison-column').dataset.rowIndex);
            const colIndex = parseInt(container.closest('.comparison-column').dataset.columnIndex);
            removeFileFromCell(rowIndex, colIndex);
        });
        
        // Setup drag and drop for the newly created file preview
        setupImageCellDragAndDrop(fileDiv);
    };
    reader.readAsDataURL(file);
}

// Function to trigger file input for replacement
function triggerFileInputForReplacement(rowIndex, colIndex) {
    // Create a temporary file input
    const tempFileInput = document.createElement('input');
    tempFileInput.type = 'file';
    tempFileInput.accept = 'image/*';
    tempFileInput.style.display = 'none';
    document.body.appendChild(tempFileInput);
    
    // Add event listener for file selection
    tempFileInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files.length > 0) {
            const file = e.target.files[0];
            // Remove the old file first
            removeFileFromCell(rowIndex, colIndex);
            // Then add the new file
            handleCellFileUpload(file, rowIndex, colIndex);
        }
        // Remove the temporary input
        document.body.removeChild(tempFileInput);
    });
    
    // Trigger the file input
    tempFileInput.click();
}

// Function to set up event handlers for name editing
function setupNameEditHandlers(fileLabel, rowIndex, colIndex, originalName) {
    const input = fileLabel.querySelector('.name-edit-input');
    const saveBtn = fileLabel.querySelector('.save-name-btn');
    const cancelBtn = fileLabel.querySelector('.cancel-name-btn');
    
    // Save button handler
    saveBtn.addEventListener('click', () => {
        const newName = input.value.trim();
        if (newName) {
            // Update the file matrix with custom name
            if (fileMatrix[rowIndex] && fileMatrix[rowIndex][colIndex]) {
                // Store the custom name in the file object
                fileMatrix[rowIndex][colIndex].customName = newName;
            }
            
            // Update the UI
            fileLabel.innerHTML = newName;
        } else {
            // If empty, revert to original
            fileLabel.innerHTML = originalName;
        }
    });
    
    // Cancel button handler
    cancelBtn.addEventListener('click', () => {
        fileLabel.innerHTML = originalName;
    });
    
    // Handle Enter key press
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            saveBtn.click();
        } else if (e.key === 'Escape') {
            e.preventDefault();
            cancelBtn.click();
        }
    });
}

// Function to handle multiple files being uploaded to a single column
function handleMultipleFilesForColumn(files, rowIndex, colIndex) {
    if (!files || files.length === 0) return;
    
    // Handle the first file in the current cell
    handleCellFileUpload(files[0], rowIndex, colIndex);
    
    // If there are more files, create new rows for each additional file
    if (files.length > 1) {
        // Find empty cells in this column that we can use before creating new rows
        const emptyCellIndices = findEmptyCellsInColumn(colIndex);
        let newRowsNeeded = files.length - 1 - emptyCellIndices.length;
        
        if (emptyCellIndices.length > 0) {
            showToast(`Using ${Math.min(emptyCellIndices.length, files.length - 1)} existing empty cell(s) in column ${colIndex + 1}`, 'info', 3000);
        }
        
        if (newRowsNeeded > 0) {
            showToast(`Creating ${newRowsNeeded} new row(s) for additional images`, 'info', 3000);
        }
        
        // First use existing empty cells
        let fileIndex = 1; // Start with the second file (first one is already handled)
        
        // Use existing empty cells first
        for (let i = 0; i < emptyCellIndices.length && fileIndex < files.length; i++) {
            const emptyRowIndex = emptyCellIndices[i];
            handleCellFileUpload(files[fileIndex], emptyRowIndex, colIndex);
            fileIndex++;
        }
        
        // Then create new rows if needed
        while (fileIndex < files.length) {
            if (rowCount < maxRows) {
                // Add a new row
                fileMatrix[rowCount] = [];
                for (let c = 0; c < columnCount; c++) {
                    fileMatrix[rowCount][c] = null;
                }
                
                // Place the file in the same column but new row
                fileMatrix[rowCount][colIndex] = files[fileIndex];
                
                // Add to selected files set
                selectedFiles.add(files[fileIndex]);
                
                // Increment row count
                rowCount++;
                fileIndex++;
            } else {
                showToast(`Maximum of ${maxRows} rows reached. Some images were not added.`, 'warning');
                break;
            }
        }
        
        // Update the UI to show the new rows with files
        updatePreview();
        
        // Show success message
        showToast(`Added ${files.length} images to column ${colIndex + 1}`, 'success');
    }
}

// Helper function to find empty cells in a specific column
function findEmptyCellsInColumn(colIndex) {
    const emptyCells = [];
    
    // Skip the first row if that's where the initial upload is happening
    for (let r = 0; r < rowCount; r++) {
        // Check if this cell is empty
        if (fileMatrix[r] && fileMatrix[r][colIndex] === null) {
            emptyCells.push(r);
        }
    }
    
    return emptyCells;
}

// Function to handle file upload to a specific cell
function handleCellFileUpload(file, rowIndex, colIndex) {
    // Update the file matrix
    if (!fileMatrix[rowIndex]) {
        fileMatrix[rowIndex] = [];
        for (let c = 0; c < columnCount; c++) {
            fileMatrix[rowIndex][c] = null;
        }
    }
    fileMatrix[rowIndex][colIndex] = file;
    
    // Add to selected files set
    selectedFiles.add(file);
    
    // Update the UI
    const cellDropZone = document.querySelector(`.comparison-column[data-row-index="${rowIndex}"][data-column-index="${colIndex}"] .column-files`);
    if (cellDropZone) {
        displayFilePreview(file, cellDropZone);
        
        // Setup drag and drop for the newly created file preview
        const fileDiv = cellDropZone.querySelector('.file-preview');
        if (fileDiv) {
            setupImageCellDragAndDrop(fileDiv);
        }
    }
}

// Function to remove a file from a cell
function removeFileFromCell(rowIndex, colIndex) {
    if (fileMatrix[rowIndex] && fileMatrix[rowIndex][colIndex]) {
        const file = fileMatrix[rowIndex][colIndex];
        
        // Remove from selected files if it's not used elsewhere
        let fileUsedElsewhere = false;
        for (let r = 0; r < fileMatrix.length; r++) {
            for (let c = 0; c < fileMatrix[r].length; c++) {
                if ((r !== rowIndex || c !== colIndex) && fileMatrix[r][c] === file) {
                    fileUsedElsewhere = true;
                    break;
                }
            }
        }
        if (!fileUsedElsewhere) {
            selectedFiles.delete(file);
        }
        
        // Clear the cell
        fileMatrix[rowIndex][colIndex] = null;
        
        // Update the UI
        updatePreview();
    }
}

// Setup drag and drop for a specific cell
function setupCellDragAndDrop(cellDropZone) {
    let rowIndex, colIndex;
    
    // Try to get indices directly from the cell drop zone
    rowIndex = parseInt(cellDropZone.dataset.rowIndex);
    colIndex = parseInt(cellDropZone.dataset.columnIndex);
    
    // Validate indices
    if (isNaN(rowIndex) || isNaN(colIndex)) {
        console.error('Invalid row or column index for cell drop zone');
        return;
    }

    cellDropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.stopPropagation();
        cellDropZone.classList.add('cell-dragover');
    });

    cellDropZone.addEventListener('dragleave', () => {
        cellDropZone.classList.remove('cell-dragover');
    });

    cellDropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        e.stopPropagation();
        cellDropZone.classList.remove('cell-dragover');
        
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            // Handle multiple files being dropped
            handleMultipleFilesForColumn(Array.from(e.dataTransfer.files), rowIndex, colIndex);
        }
    });
    
    // Make the entire cell clickable to trigger file upload
    cellDropZone.addEventListener('click', (e) => {
        e.preventDefault();
        const cellFileInput = document.querySelector(`.comparison-column[data-row-index="${rowIndex}"][data-column-index="${colIndex}"] .cell-file-input`);
        if (cellFileInput) {
            cellFileInput.click();
        }
    });
}

// Setup drag and drop for a cell that already has an image
function setupImageCellDragAndDrop(fileDiv) {
    let rowIndex, colIndex;
    
    // Try to get indices from the closest parent elements
    const columnElement = fileDiv.closest('.comparison-column');
    if (columnElement) {
        rowIndex = parseInt(columnElement.dataset.rowIndex);
        colIndex = parseInt(columnElement.dataset.columnIndex);
    } else {
        // Fallback to getting indices from the file div itself
        rowIndex = parseInt(fileDiv.dataset.rowIndex);
        colIndex = parseInt(fileDiv.dataset.columnIndex);
    }

    if (isNaN(rowIndex) || isNaN(colIndex)) {
        console.error('Invalid row or column index');
        return;
    }

    fileDiv.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.stopPropagation();
        e.dataTransfer.dropEffect = 'copy';
        fileDiv.classList.add('file-dragover');
    });

    fileDiv.addEventListener('dragleave', () => {
        fileDiv.classList.remove('file-dragover');
    });

    fileDiv.addEventListener('drop', (e) => {
        e.preventDefault();
        e.stopPropagation();
        fileDiv.classList.remove('file-dragover');
        
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            const file = e.dataTransfer.files[0]; // Take only the first file
            // Remove the old file first
            removeFileFromCell(rowIndex, colIndex);
            // Then add the new file
            handleCellFileUpload(file, rowIndex, colIndex);
        }
    });
    
    // Make the image clickable to trigger file replacement
    const img = fileDiv.querySelector('img');
    if (img) {
        img.title = "Click to replace this image";
        img.addEventListener('click', (e) => {
            e.stopPropagation();
            triggerFileInputForReplacement(rowIndex, colIndex);
        });
    }
}

// Function to enable column reordering via drag and drop
function enableColumnReordering() {
    const columnHeaders = document.querySelectorAll('.column-header');
    
    columnHeaders.forEach(header => {
        const dragHandle = header.querySelector('.drag-handle');
        if (!dragHandle) return;
        
        // Drag start event
        dragHandle.addEventListener('dragstart', (e) => {
            dragSrcColumn = header;
            draggedColumnIndex = parseInt(header.dataset.columnIndex);
            header.classList.add('dragging');
            e.dataTransfer.effectAllowed = 'move';
            // Required for Firefox
            e.dataTransfer.setData('text/plain', header.dataset.columnIndex);
            preview.classList.add('reordering');
        });
        
        // Drag end event
        dragHandle.addEventListener('dragend', (e) => {
            header.classList.remove('dragging');
            dragSrcColumn = null;
            draggedColumnIndex = -1;
            preview.classList.remove('reordering');
            
            // Remove all drag-over classes
            document.querySelectorAll('.drag-over').forEach(el => {
                el.classList.remove('drag-over');
            });
        });
        
        // Make the entire header a drop target
        header.addEventListener('dragover', (e) => {
            e.preventDefault();
            if (!dragSrcColumn || header === dragSrcColumn) return;
            header.classList.add('drag-over');
        });
        
        header.addEventListener('dragleave', (e) => {
            header.classList.remove('drag-over');
        });
        
        header.addEventListener('drop', (e) => {
            e.preventDefault();
            header.classList.remove('drag-over');
            
            if (!dragSrcColumn || header === dragSrcColumn) return;
            
            const targetIndex = parseInt(header.dataset.columnIndex);
            
            // Perform the column reordering
            reorderColumns(draggedColumnIndex, targetIndex);
        });
    });
}

function reorderColumns(fromIndex, toIndex) {
    if (fromIndex === toIndex) return;
    
    console.log(`Reordering column from ${fromIndex} to ${toIndex}`);
    
    // Save the column prefixes change
    const movedPrefix = columnPrefixes[fromIndex];
    columnPrefixes.splice(fromIndex, 1);
    columnPrefixes.splice(toIndex, 0, movedPrefix);
    
    // Reorder files in the file matrix for ALL rows
    for (let r = 0; r < fileMatrix.length; r++) {
        if (!fileMatrix[r]) continue;
        
        // Save the column of files we're moving
        const filesInMovedColumn = fileMatrix[r][fromIndex];
        
        // Remove the column
        fileMatrix[r].splice(fromIndex, 1);
        
        // Insert at the new position
        fileMatrix[r].splice(toIndex, 0, filesInMovedColumn);
    }
    
    // Also update the legacy groupedFiles for backwards compatibility
    if (groupedFiles.size > 0) {
        const entries = Array.from(groupedFiles.entries());
        const sortedEntries = [];
        
        // Reorder the entries according to the new column order
        for (let i = 0; i < columnPrefixes.length; i++) {
            const prefix = columnPrefixes[i];
            const entry = entries.find(([key]) => key === prefix);
            if (entry) {
                sortedEntries.push(entry);
            }
        }
        
        // Recreate groupedFiles with the new order
        groupedFiles = new Map(sortedEntries);
    }
    
    console.log('New column order:', columnPrefixes);
    
    // Update the UI
    updatePreview();
}

// Function to add a new row
function addRow() {
    if (rowCount >= maxRows) {
        showError(`Maximum ${maxRows} rows allowed`);
        return;
    }
    
    // Add a new row to our data structure
    fileMatrix[rowCount] = [];
    for (let c = 0; c < columnCount; c++) {
        fileMatrix[rowCount][c] = null;
    }
    rowCount++;
    
    // Update the UI to show the new row
    updatePreview();
    console.log(`Added row, now have ${rowCount} rows`);
}

// Function to remove a row
function removeRow(rowIndex) {
    if (rowCount <= 1) {
        showError('Cannot remove the last row');
        return;
    }
    
    // Remove the row from our data structure
    fileMatrix.splice(rowIndex, 1);
    rowCount--;
    
    // Update the UI
    updatePreview();
    console.log(`Removed row ${rowIndex + 1}, now have ${rowCount} rows`);
}

function isColumnRemovable(columnPrefix) {
    const isBaseColumn = columnPrefixes.indexOf(columnPrefix) < baseColumns;
    const totalRemaining = columnCount - 1;
    return !isBaseColumn || (isBaseColumn && baseColumns > minColumns);
}

function getColumnTooltip(columnPrefix) {
    const isBaseColumn = columnPrefixes.indexOf(columnPrefix) < baseColumns;
    if (isBaseColumn) {
        if (baseColumns <= minColumns) {
            return 'Cannot remove base columns below minimum';
        }
        return 'Remove base column';
    }
    return 'Remove added column';
}

// Update the column addition function for consistency
function addColumn() {
    if (columnCount >= maxColumns) {
        showError(`Maximum ${maxColumns} columns allowed`);
        return;
    }
    
    // Add a new column prefix
    columnPrefixes.push(`column${columnCount+1}`);
    
    // Add a new column to each row in the file matrix
    for (let r = 0; r < rowCount; r++) {
        if (!fileMatrix[r]) {
            fileMatrix[r] = [];
            for (let c = 0; c < columnCount; c++) {
                fileMatrix[r][c] = null;
            }
        }
        fileMatrix[r].push(null);
    }
    
    // Add an empty array for new column in groupedFiles
    if (groupedFiles.size > 0) {
        groupedFiles.set(`column${columnCount+1}`, []);
    }
    
    // Update column count
    columnCount++;
    
    // Update the UI
    updatePreview();
}

// Function to remove a column
function removeColumn(columnIndex) {
    console.log(`Attempting to remove column at index: ${columnIndex}`);
    
    // Check minimum column requirements
    if (columnCount <= minColumns) {
        showError(`Cannot remove column: Minimum ${minColumns} columns required`);
        return;
    }
    
    // Validate column index
    if (columnIndex < 0 || columnIndex >= columnCount) {
        console.error('Invalid column index:', columnIndex);
        showError('Invalid column');
        return;
    }
    
    // Remove the column from prefixes array
    columnPrefixes.splice(columnIndex, 1);
    
    // Update column count
    columnCount--;
    
    // Remove the column from each row in the file matrix
    for (let r = 0; r < fileMatrix.length; r++) {
        if (fileMatrix[r]) {
            fileMatrix[r].splice(columnIndex, 1);
        }
    }
    
    // Update groupedFiles if it's being used
    if (groupedFiles.size > 0) {
        // Remove the deleted column
        groupedFiles.delete(`column${columnIndex+1}`);
        
        // Rename remaining columns to maintain sequential numbering
        const newGroupedFiles = new Map();
        for (let i = 0; i < columnCount; i++) {
            const oldKey = `column${i >= columnIndex ? i+2 : i+1}`;
            const newKey = `column${i+1}`;
            
            if (groupedFiles.has(oldKey)) {
                newGroupedFiles.set(newKey, groupedFiles.get(oldKey));
            }
        }
        groupedFiles = newGroupedFiles;
    }
    
    // Regenerate column prefixes with correct numbering
    columnPrefixes = [];
    for (let i = 0; i < columnCount; i++) {
        columnPrefixes.push(`column${i+1}`);
    }
    
    console.log(`Column removed. New column count: ${columnCount}`);
    console.log('New column prefixes:', columnPrefixes);
    
    // Update the UI
    updatePreview();
}

function updateColumnControls() {
    document.querySelectorAll('.column-controls button').forEach(button => {
        const columnPrefix = button.closest('.comparison-column').id.split('-')[1];
        button.disabled = !isColumnRemovable(columnPrefix);
        button.title = getColumnTooltip(columnPrefix);
    });
}

// Replace the old showError function with our toast notification system
function showError(message) {
    console.log('showError called with message:', message);
    showToast(message, 'error');
}

function showSuccess(message) {
    console.log('showSuccess called with message:', message);
    showToast(message, 'success');
}

function validateMetadata() {
    const comparisonName = comparisonNameInput.value.trim();
    if (!comparisonName) {
        showError('Please enter a comparison name');
        return false;
    }
    if (columnCount < minColumns) {
        showError(`Minimum of ${minColumns} columns required`);
        return false;
    }
    return true;
}

function getMetadata() {
    return {
        name: comparisonNameInput.value.trim(),
        show_name: showNameInput.value.trim(),
        expiration_type: expirationToggle.checked ? getSelectedExpirationType() : 'from_last_access',
        expiration_days: expirationToggle.checked ? getSelectedExpirationDays() : 7,
        tags: tagsInput.value.trim()
    };
}

function getSelectedExpirationType() {
    const expirationTypeRadios = document.querySelectorAll('input[name="expiration-type"]');
    for (const radio of expirationTypeRadios) {
        if (radio.checked) {
            return radio.value;
        }
    }
    return 'from_last_access'; // Default to 'from_last_access'
}

function getSelectedExpirationDays() {
    const expirationDaysSelect = document.getElementById('expiration-days');
    return parseInt(expirationDaysSelect.value) || 7; // Default to 7 if parsing fails
}

function clearMetadata() {
    comparisonNameInput.value = '';
    showNameInput.value = '';
    document.getElementById('expiration-last-access').checked = true;
    document.getElementById('expiration-days').value = '7';
    tagsInput.value = '';
}

document.getElementById('uploadButton').addEventListener('click', async () => {
    const formData = new FormData();
    
    if (uploadInProgress) {
        alert('Upload already in progress');
        return;
    }

    if (selectedFiles.size === 0) {
        showError('Please select or drag some images first');
        return;
    }

    if (!validateMetadata()) {
        return;
    }
    const metadata = getMetadata();

    if (selectedFiles.size > 30) {
        showError('Maximum 30 files allowed');
        return;
    }

    if (columnCount < minColumns) {
        showError('Minimum number of columns required');
        return;
    }

    uploadInProgress = true;
    const uploadButton = document.getElementById('uploadButton');
    uploadButton.disabled = true;
    uploadButton.textContent = 'Uploading...';

    for (const file of selectedFiles) {
        formData.append('files', file);
    }

    // Add custom names to form data
    const customNames = {};
    fileMatrix.forEach((row, rowIndex) => {
        row.forEach((file, colIndex) => {
            if (file && file.customName) customNames[file.name] = file.customName;
        });
    });
    formData.append('custom_names', JSON.stringify(customNames));

    // Add column order information to the form data
    formData.append('column_order', JSON.stringify(columnPrefixes));

    // Add row count to the form data
    formData.append('row_count', rowCount);

    // Create file position data
    const filePositions = [];
    for (let r = 0; r < fileMatrix.length; r++) {
        if (!fileMatrix[r]) continue;
        
        for (let c = 0; c < fileMatrix[r].length; c++) {
            const file = fileMatrix[r][c];
            if (file) {
                filePositions.push({
                    filename: file.name,
                    row: r,
                    column: c
                });
            }
        }
    }
    formData.append('file_positions', JSON.stringify(filePositions));

    formData.append('name', metadata.name);
    formData.append('show_name', metadata.show_name);
    formData.append('expiration_type', metadata.expiration_type);
    formData.append('expiration_days', metadata.expiration_days);
    formData.append('tags', metadata.tags);

    try {
        const response = await fetch('/upload/', {
            method: 'POST',
            body: formData
        });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        console.log('Upload response received:', response);
        const data = await response.json();
        console.log('Upload response data:', data);
        showSuccess('Upload successful! Redirecting to comparison view...');
        clearMetadata();
        window.location.href = `/compare/${data.comparison_id}`;
    } catch (error) {
        console.error('Upload failed:', error);
        showError('Upload failed: ' + error.message);
    } finally {
        console.log('Upload completed');
        uploadInProgress = false;
        uploadButton.disabled = false;
        uploadButton.textContent = 'Compare Images';
        uploadButton.style.display = 'block';
    }
});

// Call this after the page loads
window.addEventListener('DOMContentLoaded', function() {
    document.getElementById('uploadButton').style.display = 'block';
    // Initialize the first row in the file matrix
    fileMatrix[0] = [];
    for (let i = 0; i < columnCount; i++) {
        fileMatrix[0][i] = null;
    }
        
    // Initialize with empty columns
    for (let i = 0; i < columnCount; i++) {
        columnPrefixes.push(`column${i+1}`);
    }
    updatePreview(); // Initialize with empty cells
    
    // Initialize tooltips
    if (typeof bootstrap !== 'undefined') {
        const tooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
        tooltips.forEach(tooltip => new bootstrap.Tooltip(tooltip));
    }
    
    // Test toast notification system
    setTimeout(() => {
        showToast('Upload form ready. Drag and drop images or click to select files.', 'success', 3000);
        showToast('Tip: You can upload multiple images to a column at once - they will fill empty cells or create new rows', 'info', 5000);
    }, 500);
});
